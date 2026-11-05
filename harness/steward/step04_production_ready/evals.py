"""Local evals for the production-ready Steward (Step 4).

Follows the guide's ``evals.py``: run fixed queries (one fresh session each) and score the answers
with local evaluators. Foundry evaluators are left out: they need Microsoft Foundry. Every span goes
to halo_traces/traces.jsonl, as in console_app.py, and a failed check prints its reason.

The shell is disabled and skill scripts are auto-approved for this unattended run, so no query
stops on an approval prompt. Nothing here writes files or commits, save the results history below.

The last four queries are regression cases from MAF's improvement loop (Kyle, 2026-10-30, the plan
"fix Steward's four failures with MAF's improvement loop"): each is a failure the improvement loop's
eval gate and Kyle's Part 3 verdicts found, checked with MAF's own tool_call_args_match (the tools
Steward must call) beside a check of the answer. A case stays here once it passes.

Beside that default set: ``small`` (step 4's small asks, with ``--gate`` the improvement loop's gate), ``steps``
(each workflow step scored on its own) and ``memory`` (step 5: a note saved in one request is recalled in the next).

Every set exits 1 when any case fails (``small --gate``: when the checks drop below the baseline), 0 otherwise. A case
whose run raises fails with the exception's type and first line (run_completed), and the set goes on to the next case.
Every set run also appends one JSON line to storage/evals/history.jsonl (record_history); the report and the exit
code never depend on it.

``--options NAME`` runs a set with a named settings set from eval_options.json (per-step model options, the
STEWARD_<STEP>_THINK / _TEMPERATURE / _SEED that steward_workflow reads at build); the report's first line names it.

The small and steps sets, and T1's heldout set, are versioned files in harness/steward/evals/ (load_eval_sets; how a set
is added: that folder's README.md). ``validate`` checks them with no model; ``bar <set>`` reads the history for its bar.

``--transport in-process|responses|ag-ui`` (an asks set: small, heldout) says how each case reaches Steward: in this
process (the default, run_steward), or against the running Responses host (hosted.py, 127.0.0.1:43120) or AG-UI host
(ag_ui_app.py, 127.0.0.1:43122), its cards answered over the wire with the same policy (eval_transports.py). Every case
records its transport and timings in the history; ``compare-transports [--set NAME] [--last N] [--set-version V]``
prints the per-case table of the three, from the history, running nothing (one version of the set: V, or its current
one, with a line naming the runs of other versions it leaves out).

Run:
    python harness/steward/step04_production_ready/evals.py [small [--gate] | steps | memory | heldout] [--options NAME]
    python harness/steward/step04_production_ready/evals.py small --transport ag-ui
    python harness/steward/step04_production_ready/evals.py compare-transports --last 3
    python harness/steward/step04_production_ready/evals.py validate
    python harness/steward/step04_production_ready/evals.py bar <set>
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import contextlib
from collections.abc import Callable, Iterable
from contextlib import AsyncExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentResponse,
    ConversationSplit,
    EvalResults,
    ExpectedToolCall,
    LocalEvaluator,
    evaluate_agent,
    evaluator,
    tool_call_args_match,
)
from agent_framework.observability import configure_otel_providers
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_transports  # noqa: E402
from halo_traces import HaloJsonlSpanExporter  # noqa: E402
from steward_workflow import APPROVE_PLAN, build_steward  # noqa: E402

# Versioned eval sets (the plan "Steward's dev path: evals that grow with his skills", 2026-11-05, step 1): each set is
# one file in harness/steward/evals/, <tier>-<name>.yaml, holding its name, tier, version, owner, runner, bar, the
# change each version made, and its cases (an ask, a fixture: the sample project and an optional plant step, the terms
# an on-topic answer names, a precondition and its checks by name). The sets are read here at import; validate_sets
# (python evals.py validate, run by test_harness and so by the gate) checks every file. How a set is added and
# versioned: harness/steward/evals/README.md.
EVAL_SETS_DIR = Path(__file__).resolve().parents[1] / "evals"
# Baselines and the fingerprint of each set version's cases: {name: {version: {"cases": sha256, ...}}}.
EVAL_BASELINES = EVAL_SETS_DIR / "baselines.json"
EVAL_RUNNERS = ("asks", "steps")
_SET_KEYS = {"name", "tier", "version", "owner", "runner", "split", "bar", "changes", "cases"}
# num_repetitions: opt-in, and only for a non-gating set (tier ext, e.g. a flakiness check); a gating tier runs each
# case once.
_SET_OPTIONAL = {"num_repetitions"}
_CASE_KEYS = {"id", "ask", "fixture", "subject", "precondition", "checks"}
# Handed to MAF's evaluate_agent as they are: expected_output, and expected_tool_calls as ExpectedToolCall(name,
# arguments) scored by MAF's tool_call_args_match.
_CASE_OPTIONAL = {"expected_output", "expected_tool_calls"}
# A set's conversation split (MAF's ConversationSplit): full for multi-step cases (every step after the ask is scored).
SPLITS = {"full": ConversationSplit.FULL, "last_turn": ConversationSplit.LAST_TURN}
_BAR_KEYS = {"passed", "of", "runs_in_a_row"}
_FIXTURE_KEYS = {"project", "plant"}
# The plant steps a fixture may name: each the name of a context manager in this module, looked up when it is entered
# (so a test's monkeypatch of it holds). It makes the ask's precondition in the working copy only, and puts it back.
PLANTS = {
    "discount_bug": "discount_bug_planted",
    "readme_run_tests_removed": "readme_run_tests_removed",
    "fahrenheit_bug": "fahrenheit_bug_planted",
    "failing_test_added": "without_unit_test_planted",
}
# The RESULT checks: each measures the sample project as an ask's run left it (no model, deterministic), by the name of
# its measurement function in this module, looked up when it runs. Every case needs one, and its precondition is one.
RESULT_CHECKS = {
    "item_count_works": "item_count_result",
    "discount_test_passes": "discount_test_result",
    "readme_says_how_to_run_tests": "readme_run_tests_result",
    "steps_overall": "discount_test_result",
    "fahrenheit_to_celsius_works": "fahrenheit_to_celsius_result",
    "boiling_point_test_passes": "boiling_point_test_result",
    "metres_per_unit_renamed": "metres_per_unit_result",
    "readme_lists_length_units": "readme_length_units_result",
    "without_unit_test_passes": "without_unit_test_result",
}
# The process checks each runner scores by name (besides the result checks), and the steps runner's whole set.
ASKS_PROCESS_CHECKS = (
    "plan_is_approval", "check_covers_writes", "edit_keeps_file_whole", "commit_by_tool", "commit_message_specific",
    "no_nudge_in_reply", "answer_on_topic",
)
STEPS_CHECKS = ("plan_step", "execute_step", "steps_overall")
# The result checks the asks runner scores (steps_overall is the steps runner's).
ASKS_RESULT_CHECKS = tuple(name for name in RESULT_CHECKS if name not in STEPS_CHECKS)


class EvalSetError(ValueError):
    """An eval set file that cannot be used: its problems, one per line."""


@dataclass(frozen=True)
class EvalCase:
    """One case of a set: the ask, its fixture (project and plant), its subject terms, precondition and checks."""

    id: str
    ask: str
    project: str
    plant: str | None
    subject: tuple[str, ...]
    precondition: str
    checks: tuple[str, ...]
    expected_output: str | None = None
    expected_tool_calls: tuple[ExpectedToolCall, ...] = ()


@dataclass(frozen=True)
class EvalSet:
    """One versioned eval set, as its file holds it."""

    name: str
    tier: str
    version: int
    owner: str
    runner: str
    split: str
    bar: dict[str, int]
    changes: dict[int, str]
    cases: tuple[EvalCase, ...]
    fingerprint: str
    path: Path
    num_repetitions: int = 1

    @property
    def asks(self) -> list[str]:
        return [case.ask for case in self.cases]

    @property
    def eval_name(self) -> str:
        """The name MAF's results carry: <set>@v<version>."""
        return f"{self.name}@v{self.version}"

    def case(self, case_id: str) -> EvalCase:
        return next(case for case in self.cases if case.id == case_id)


def cases_fingerprint(cases: Any) -> str:
    """The sha256 of a set's cases as parsed (keys sorted): any change to a case or a check changes it."""
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _schema_problems(raw: Any, path: Path) -> list[str]:
    """What is wrong with a set file's shape and names (no fixture is entered here)."""
    if not isinstance(raw, dict):
        return ["not a mapping"]
    problems = [f"unknown key {key!r}" for key in sorted(set(raw) - _SET_KEYS - _SET_OPTIONAL)]
    problems += [f"missing key {key!r}" for key in sorted(_SET_KEYS - set(raw))]
    if problems:
        return problems
    name, tier, version, runner = raw["name"], raw["tier"], raw["version"], raw["runner"]
    if not (isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]*", name)):
        problems.append(f"name {name!r} is not a lower-case word")
    if not (isinstance(tier, str) and re.fullmatch(r"T\d|ext", tier)):
        problems.append(f"tier {tier!r} is not T0 to T9 or ext")
    if raw["split"] not in SPLITS:
        problems.append(f"split {raw['split']!r} is not one of {sorted(SPLITS)}")
    if "num_repetitions" in raw:
        reps = raw["num_repetitions"]
        if tier != "ext":
            problems.append("num_repetitions is for a non-gating set (tier ext) only: a gating tier runs each case once")
        elif not (isinstance(reps, int) and not isinstance(reps, bool) and reps >= 1):
            problems.append(f"num_repetitions {reps!r} is not a whole number from 1")
    if not (isinstance(version, int) and not isinstance(version, bool) and version >= 1):
        problems.append(f"version {version!r} is not a whole number from 1")
    if not (isinstance(raw["owner"], str) and raw["owner"].strip()):
        problems.append("owner is empty")
    if runner not in EVAL_RUNNERS:
        problems.append(f"runner {runner!r} is not one of {list(EVAL_RUNNERS)}")
    if isinstance(name, str) and isinstance(tier, str) and path.name != f"{tier.lower()}-{name}.yaml":
        problems.append(f"the file is named {path.name}, not {tier.lower()}-{name}.yaml")
    changes = raw["changes"]
    if not (isinstance(changes, dict) and all(isinstance(k, int) and isinstance(v, str) and v.strip() for k, v in changes.items())):
        problems.append("changes is not a mapping of version numbers to what each changed")
    elif version not in changes:
        problems.append(f"changes says nothing of version {version}")
    cases = raw["cases"]
    if not (isinstance(cases, list) and cases):
        return [*problems, "cases is not a non-empty list"]
    bar = raw["bar"]
    if not (isinstance(bar, dict) and set(bar) == _BAR_KEYS and all(isinstance(v, int) and v >= 1 for v in bar.values())):
        problems.append(f"bar is not {{passed, of, runs_in_a_row}}, each a whole number from 1: {bar!r}")
    elif not bar["passed"] <= bar["of"] == len(cases):
        problems.append(f"bar {bar['passed']}/{bar['of']} does not fit its {len(cases)} cases")
    known = set(ASKS_PROCESS_CHECKS) | set(ASKS_RESULT_CHECKS) if runner == "asks" else set(STEPS_CHECKS)
    seen: set[str] = set()
    for n, case in enumerate(cases, 1):
        where = f"case {n}"
        if not isinstance(case, dict):
            problems.append(f"{where} is not a mapping")
            continue
        where = f"case {case.get('id', n)!r}"
        problems += [f"{where}: unknown key {key!r}" for key in sorted(set(case) - _CASE_KEYS - _CASE_OPTIONAL)]
        problems += [f"{where}: missing key {key!r}" for key in sorted(_CASE_KEYS - set(case))]
        if not _CASE_KEYS <= set(case) <= _CASE_KEYS | _CASE_OPTIONAL:
            continue
        if "expected_output" in case and not (isinstance(case["expected_output"], str) and case["expected_output"].strip()):
            problems.append(f"{where}: expected_output is not text")
        calls = case.get("expected_tool_calls", [])
        if not (isinstance(calls, list) and all(
            isinstance(c, dict) and isinstance(c.get("name"), str) and set(c) <= {"name", "arguments"}
            and isinstance(c.get("arguments", {}), dict) for c in calls
        )):
            problems.append(f"{where}: expected_tool_calls is not a list of {{name, arguments}}")
        if case["id"] in seen:
            problems.append(f"{where}: the id is used twice")
        seen.add(case["id"])
        if not (isinstance(case["ask"], str) and case["ask"].strip()):
            problems.append(f"{where}: the ask is empty")
        fixture = case["fixture"]
        if not (isinstance(fixture, dict) and set(fixture) == _FIXTURE_KEYS):
            problems.append(f"{where}: fixture is not {{project, plant}}")
        else:
            if fixture["project"] not in SAMPLE_PROJECTS or not (_REPO / fixture["project"]).is_dir():
                problems.append(f"{where}: fixture project {fixture['project']!r} is not one of {list(SAMPLE_PROJECTS)}")
            if fixture["plant"] is not None and fixture["plant"] not in PLANTS:
                problems.append(f"{where}: plant {fixture['plant']!r} is not one of {sorted(PLANTS)}")
        subject = case["subject"]
        if not (isinstance(subject, list) and subject and all(isinstance(t, str) and t and t == t.lower() for t in subject)):
            problems.append(f"{where}: subject is not a list of lower-case terms (the checks compare lower-cased text)")
        checks = case["checks"]
        if not (isinstance(checks, list) and checks and all(isinstance(c, str) for c in checks)):
            problems.append(f"{where}: checks is not a list of check names")
            continue
        if unknown := [c for c in checks if c not in known]:
            problems.append(f"{where}: no {runner} check named {unknown}")
        if len(set(checks)) != len(checks):
            problems.append(f"{where}: a check is named twice")
        if not any(c in RESULT_CHECKS for c in checks):
            problems.append(f"{where}: no RESULT check, only process checks ({sorted(RESULT_CHECKS)})")
        if runner == "steps" and sorted(checks) != sorted(STEPS_CHECKS):
            problems.append(f"{where}: the steps runner scores exactly {list(STEPS_CHECKS)}")
        if case["precondition"] not in RESULT_CHECKS or case["precondition"] not in checks:
            problems.append(f"{where}: precondition {case['precondition']!r} is not one of its own result checks")
    return problems


def load_eval_set(path: Path) -> EvalSet:
    """A set file read and its shape checked; EvalSetError names every problem."""
    import yaml  # noqa: PLC0415

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise EvalSetError(f"{path.name}: {error}") from error
    if problems := _schema_problems(raw, path):
        raise EvalSetError("\n".join(f"{path.name}: {problem}" for problem in problems))
    cases = tuple(
        EvalCase(
            id=c["id"], ask=" ".join(c["ask"].split()), project=c["fixture"]["project"], plant=c["fixture"]["plant"],
            subject=tuple(c["subject"]), precondition=c["precondition"], checks=tuple(c["checks"]),
            expected_output=c.get("expected_output"),
            expected_tool_calls=tuple(ExpectedToolCall(t["name"], t.get("arguments")) for t in c.get("expected_tool_calls", [])),
        )
        for c in raw["cases"]
    )
    return EvalSet(
        name=raw["name"], tier=raw["tier"], version=raw["version"], owner=raw["owner"], runner=raw["runner"],
        split=raw["split"], bar=dict(raw["bar"]), changes=dict(raw["changes"]), cases=cases,
        fingerprint=cases_fingerprint(raw["cases"]), path=path, num_repetitions=raw.get("num_repetitions", 1),
    )


def load_eval_sets(folder: Path = EVAL_SETS_DIR) -> dict[str, EvalSet]:
    """Every set file in the folder, by set name; EvalSetError on the first that cannot be used, or a name used twice."""
    sets: dict[str, EvalSet] = {}
    for path in sorted(folder.glob("*.yaml")):
        eval_set = load_eval_set(path)
        if eval_set.name in sets:
            raise EvalSetError(f"{path.name}: the set name {eval_set.name!r} is also {sets[eval_set.name].path.name}'s")
        sets[eval_set.name] = eval_set
    return sets

STEWARD_EVAL_QUERIES = [
    "Use get_repo_status and tell me which git branch the workspace is on.",
    "Map harness/steward/working/sample-project with the codebase-map skill. Which file is the module and "
    "which is the test file?",
    "Read harness/steward/working/sample-project/inventory.py and "
    "harness/steward/working/sample-project/test_inventory.py and explain why test_percent_discount fails. "
    "Don't change any files.",
    # MAF improvement-loop regression cases (layer per MAF's evaluation reference)
    "Map harness/steward/working/sample-project.",  # case 2: instructions / skill
    "What percentage of harness/steward/working/sample-project's lines are tests?",  # case 3: tool selection
    "Research Microsoft Agent Framework, Ollama and mem0 and summarize the latest news.",  # case 1: tool selection
    "Explore harness/steward/working/sample-project with the CodeExplorer agent and summarize it.",  # case 4
]

# The tools each query must call, one list per query (MAF's expected_tool_calls); the names and the
# agent_name argument are the ones Steward's traces record.
STEWARD_EXPECTED_TOOL_CALLS: list[list[ExpectedToolCall]] = [
    [],
    [],
    [],
    [ExpectedToolCall("load_skill"), ExpectedToolCall("run_skill_script")],
    [ExpectedToolCall("execute_code")],
    [ExpectedToolCall("background_agents_start_task", {"agent_name": "WebResearchAgent"})],
    [ExpectedToolCall("background_agents_start_task", {"agent_name": "CodeExplorer"})],
]


@evaluator(name="repo_status_grounded")
def repo_status_grounded(query: str, response: str) -> dict[str, object]:
    """Check that the branch answer names a real branch from the repo."""
    if "branch" not in query.lower():
        return {"passed": True, "reason": "Not the repo-status eval item."}
    # The branch the workspace is really on (2026-11-01: "main" was hard-coded, and failed on a line of work).
    import subprocess  # noqa: PLC0415

    from agent import _WORKING_DIR  # noqa: PLC0415

    branch = subprocess.run(["git", "branch", "--show-current"], cwd=_WORKING_DIR, capture_output=True, text=True).stdout.strip()
    passed = bool(branch) and branch in response
    return {"passed": passed, "reason": f"Names {branch}." if passed else f"Expected {branch}: {response[:140]}"}


@evaluator(name="codebase_map_names_files")
def codebase_map_names_files(query: str, response: str) -> dict[str, object]:
    """Check that the codebase map names the module and its test file."""
    if "codebase-map" not in query.lower():
        return {"passed": True, "reason": "Not the codebase-map eval item."}
    text = response.lower()
    found = [name for name in ("inventory.py", "test_inventory.py") if name in text]
    return {"passed": len(found) == 2, "reason": f"Found files: {found}."}


@evaluator(name="bug_diagnosis")
def bug_diagnosis(query: str, response: str) -> dict[str, object]:
    """Check that the diagnosis names the percent-vs-fraction bug."""
    if "test_percent_discount" not in query.lower():
        return {"passed": True, "reason": "Not the bug-diagnosis eval item."}
    text = response.lower()
    passed = "100" in text or "fraction" in text or "percentage" in text
    return {"passed": passed, "reason": "Explains the percent/fraction mix-up." if passed else response[:160]}


@evaluator(name="map_names_files")
def map_names_files(query: str, response: str) -> dict[str, object]:
    """Case 2: the codebase map names the module and its test file."""
    if query != STEWARD_EVAL_QUERIES[3]:
        return {"passed": True, "reason": "Not the map case."}
    text = response.lower()
    found = [name for name in ("inventory.py", "test_inventory.py") if name in text]
    return {"passed": len(found) == 2, "reason": f"Found files: {found}."}


@evaluator(name="test_share_counted")
def test_share_counted(query: str, response: str) -> dict[str, object]:
    """Case 3: the share is counted, not estimated, over the project's code files, as Kyle counted it in Part 3.

    His count (24 of 45 lines, 53.3%) was right on 2026-10-29 until 87947b5 took inventory.py from 21 lines to
    20, so the expected share is counted from the files on disk (the cookbook: validators check the artefacts).
    """
    if "percentage" not in query.lower():
        return {"passed": True, "reason": "Not the line-count case."}
    from agent import _WORKING_DIR  # noqa: PLC0415

    project = _WORKING_DIR / "harness" / "steward" / "working" / "sample-project"
    counts = {p.name: len(p.read_text(encoding="utf-8").splitlines()) for p in project.glob("*.py")}
    tests = sum(n for name, n in counts.items() if name.startswith("test_"))
    share = f"{100 * tests / sum(counts.values()):.1f}"
    passed = share in response
    return {"passed": passed, "reason": f"Reports {share}%." if passed else f"Expected {share}% ({counts}): {response[:120]}"}


@evaluator(name="research_covers_topics")
def research_covers_topics(query: str, response: str) -> dict[str, object]:
    """Case 1: the combined summary covers all three topics."""
    if "research" not in query.lower():
        return {"passed": True, "reason": "Not the research case."}
    text = response.lower()
    missing = [topic for topic in ("agent framework", "ollama", "mem0") if topic not in text]
    return {"passed": not missing, "reason": f"Missing topics: {missing}." if missing else "All three topics."}


@evaluator(name="explorer_names_files")
def explorer_names_files(query: str, response: str) -> dict[str, object]:
    """Case 4: the summary names the two files CodeExplorer reads."""
    if "codeexplorer" not in query.lower():
        return {"passed": True, "reason": "Not the CodeExplorer case."}
    text = response.lower()
    found = [name for name in ("inventory.py", "test_inventory.py") if name in text]
    return {"passed": len(found) == 2, "reason": f"Found files: {found}."}


# MAF's own results for a call it never ran: a tool not offered (_tools.py:2226) and arguments that fail validation
# (_tools.py:2041). The steps set at f7b5120 (2026-11-05 06:41Z): EXPLORE called run_shell, which it is not offered,
# MAF answered 'Error: Requested function "run_shell" not found.', and plan_step failed "Changed things while planning".
NOT_RUN_RESULTS = ('Error: Requested function "', "Error: Argument parsing failed.")


def _calls_in_order(conversation: list[Any]) -> list[tuple[str, Any, str]]:
    """Every tool call in the run, in order, with its arguments and its outcome: "ran", "card" (left on an
    approval card), "refused" (the plan-mode gate's corrective feedback) or "not run" (MAF never ran it:
    NOT_RUN_RESULTS)."""
    from agent import PLAN_MODE_REFUSAL, PLAN_MODE_TODOS_NOT_DONE  # noqa: PLC0415

    markers = (PLAN_MODE_REFUSAL.split("{name}")[0], PLAN_MODE_TODOS_NOT_DONE)
    results = {
        content.call_id: str(content.result or "")
        for message in conversation or []
        for content in getattr(message, "contents", None) or []
        if content.type == "function_result"
    }
    refused = {call_id for call_id, result in results.items() if result.startswith(markers)}
    not_run = {call_id for call_id, result in results.items() if result.startswith(NOT_RUN_RESULTS)}
    calls: list[tuple[str, Any, str]] = []
    for message in conversation or []:
        for content in getattr(message, "contents", None) or []:
            if content.type == "function_call":
                outcome = "refused" if content.call_id in refused else "not run" if content.call_id in not_run else "ran"
                calls.append((content.name, content.parse_arguments(), outcome))
            elif content.type == "function_approval_request" and content.function_call is not None:
                calls.append((content.function_call.name, content.function_call.parse_arguments(), "card"))
    return calls


def isolated_memory(stack: AsyncExitStack) -> Any:
    """A throwaway file-memory store for one eval run: MAF's FileSystemAgentFileStore over a temp folder under
    storage/, removed when the run ends. Nothing an eval does reaches Steward's real
    memory, and his real memory does not steer the eval (live 2026-11-02: eval runs saved their plans into
    agent-file-memory/steward, and a later run's commit message described that work, not its own).
    """
    from agent import _WORKING_DIR  # noqa: PLC0415
    from agent_framework import FileSystemAgentFileStore  # noqa: PLC0415

    parent = _WORKING_DIR / "storage"
    parent.mkdir(exist_ok=True)
    return FileSystemAgentFileStore(stack.enter_context(tempfile.TemporaryDirectory(dir=parent)))


def isolated_memory_store(stack: AsyncExitStack) -> Any:
    """A throwaway automatic-memory store for one eval run (step 5), as isolated_memory is for file memory."""
    from agent import _WORKING_DIR, steward_memory_store  # noqa: PLC0415

    parent = _WORKING_DIR / "storage"
    parent.mkdir(exist_ok=True)
    return steward_memory_store(stack.enter_context(tempfile.TemporaryDirectory(dir=parent)))


async def run_steward(query: str, approve: set[str], **build: Any) -> tuple[Agent[Any], AgentResponse[Any]]:
    """One query through Steward's workflow, as the Agent tab's service runs it (define once: build_steward), driven
    as an agent (Learn, "Using Workflows as Agents"), in a fresh build. The plan card and the tools in ``approve`` are
    approved, every other card denied; EXECUTE's work is in the response (intermediate output). Always an eval's build
    (eval_build): no Atlas door and no note writes, so no card reaches the user's SecondBrain (live 2026-11-04)."""
    build["eval_build"] = True
    async with AsyncExitStack() as stack:
        build.setdefault("file_memory_store", isolated_memory(stack))  # his real memory stays out of the eval
        build.setdefault("memory_store", isolated_memory_store(stack))
        agent, workflow = await build_steward(stack, **build)
        async with agent:
            steward = workflow.as_agent(name="Steward")
            # No session, as MAF's own sample runs a workflow agent with cards (workflow_as_agent_human_in_the_loop.py):
            # the workflow keeps its state, and a session would feed the run's history back in with each card answer.
            response = await _run_answering_cards(steward, None, query, {APPROVE_PLAN, *approve})
    return steward, response


SAMPLE_PROJECT = "harness/steward/working/sample-project"
# T1's held-out project (t1-heldout.yaml): a different module, never tuned on.
SAMPLE_PROJECT_2 = "harness/steward/working/sample-project-2"
# Every sample project an eval set's fixture names (validate_sets: none other).
SAMPLE_PROJECTS = (SAMPLE_PROJECT, SAMPLE_PROJECT_2)
# The one shell command an eval approves (the evals run real commands on his PC): pytest, or python -m pytest, with
# only -q, -rA or -p no:cacheprovider, on a sample project or a test file (and test) in it. Nothing else: no second
# command, no pipe, no redirect.
_SAMPLE_PYTEST = re.compile(
    r"(?:[\w.:/-]*python(?:3)?(?:\.exe)?\s+-m\s+)?pytest"
    r"(?:\s+(?:-q|-rA|-p\s+no:cacheprovider))*"
    r"\s+(?:\./)?(?:" + "|".join(re.escape(p) for p in SAMPLE_PROJECTS) + r")(?:/[\w-]+\.py(?:::[\w:]+)?)?/?"
    r"(?:\s+(?:-q|-rA|-p\s+no:cacheprovider))*"
)


def is_sample_project_pytest(command: str) -> bool:
    """Whether a shell command is only a sample project's pytest (_SAMPLE_PYTEST), backslashes read as slashes."""
    return bool(_SAMPLE_PYTEST.fullmatch(str(command or "").strip().replace("\\", "/")))


def card_approved(call: Any, approve: set[str]) -> bool:
    """An eval's answer to a card, as the user would give it: Approve for the tools in ``approve``, and for a run_shell
    card only when its command is the sample project's pytest; Deny for everything else (audit 2026-11-04: the
    steps set approved every shell command)."""
    if call is None:
        return False
    if call.name == "run_shell":
        return is_sample_project_pytest(str((call.parse_arguments() or {}).get("command", "")))
    return call.name in approve


def sample_project_as_committed(project: str = SAMPLE_PROJECT) -> None:
    """A sample project put back to its committed text before a run snapshots it. The runs' own resets put back
    what was on disk when they began, so a damaged file outlived every run (2026-11-04: inventory.py, cut to a
    stand-in at 10:14, was the "original" of each eval after it)."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    subprocess.run(["git", "checkout", "HEAD", "--", project], cwd=_WORKING_DIR, check=True, capture_output=True)


# Small run 1 (2026-11-04, head 0016cf4): the item_count ask left a stray inventory.py at the repository root, outside
# the sample project the resets put back, so it outlived the run. A run's reset now also removes every untracked file
# (git ls-files --others --exclude-standard: not ignored, not tracked) that was not there when the run began; what was
# untracked before it, and everything ignored, is left alone.
def untracked_files() -> set[str]:
    """The repository's untracked, not-ignored files (repository-relative, "/"-separated)."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    listed = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=_WORKING_DIR, check=True, capture_output=True,
        timeout=60,
    ).stdout.decode("utf-8", errors="replace")
    return {name for name in listed.split("\0") if name}


def remove_new_untracked(before: set[str]) -> list[str]:
    """Delete the untracked files that are not in ``before`` (a run's own new files); the names removed, sorted."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    removed = sorted(untracked_files() - before)
    for name in removed:
        (_WORKING_DIR / name).unlink(missing_ok=True)
    if removed:
        logger.info("Removed the run's new untracked files: %s", removed)
    return removed


@contextmanager
def discount_bug_planted() -> Any:
    """The discount bug, planted in the working copy for the run and put back after it, whatever happens.

    The gate says "The evals plant the discount bug in the working copy only", and nothing did: once the
    committed sample project was fixed (87947b5, 2026-10-29), the bug-diagnosis case asked about a test
    that passes. The committed file stays fixed, so the gate's sample tests stay green.
    """
    from agent import _WORKING_DIR  # noqa: PLC0415

    module = _WORKING_DIR / "harness" / "steward" / "working" / "sample-project" / "inventory.py"
    original = module.read_bytes()
    fixed, planted = b"subtotal * (1 - discount_percent / 100)", b"subtotal * (1 - discount_percent)"
    if fixed not in original:
        raise RuntimeError(f"{module} no longer holds the fixed discount line; update discount_bug_planted.")
    module.write_bytes(original.replace(fixed, planted))
    try:
        yield
    finally:
        module.write_bytes(original)


# The README's own how-to, from its "Run the tests:" line through the code fence closing the command (c17cd62).
README_RUN_TESTS = ("Run the tests:", "python -m unittest -v")


@contextmanager
def readme_run_tests_removed() -> Any:
    """The README's how-to-run-the-tests lines taken out of the working copy for the README ask, put back after it.

    Bar run B (2026-11-04 22:09Z, head 06657a1): the committed README already says "Run the tests:" and "python -m
    unittest -v" (since c17cd62), so "Add one line ... that says how to run its tests" asked for what was there, and he
    rightly asked instead of planning. Like discount_bug_planted, the ask's precondition is made in the working copy
    only: the block goes (the blank line before it too), its line endings kept, and the committed file never changes.
    """
    from agent import _WORKING_DIR  # noqa: PLC0415

    readme = _WORKING_DIR / SAMPLE_PROJECT / "README.md"
    original = readme.read_bytes()
    lines = original.decode("utf-8").splitlines(keepends=True)
    start = next((n for n, line in enumerate(lines) if line.strip() == README_RUN_TESTS[0]), None)
    command = next((n for n, line in enumerate(lines) if line.strip() == README_RUN_TESTS[1]), None)
    if start is None or command is None or command < start:
        raise RuntimeError(f"{readme} no longer holds its run-the-tests lines; update readme_run_tests_removed.")
    end = command + 1
    if end < len(lines) and lines[end].strip().startswith("```"):
        end += 1  # the fence closing the command
    while start > 0 and not lines[start - 1].strip():
        start -= 1  # the blank lines before the block
    readme.write_bytes("".join(lines[:start] + lines[end:]).encode("utf-8"))
    try:
        yield
    finally:
        readme.write_bytes(original)


@contextmanager
def _text_replaced(relative: str, old: str, new: str, plant: str) -> Any:
    """One line's text replaced in a sample project's file in the working copy for one ask, put back after it, whatever
    happens; the file's line endings kept (a "\\n" in ``old`` or ``new`` is read as the file's own). A file that no
    longer holds ``old`` once raises, naming the plant to update."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    path = _WORKING_DIR / relative
    original = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    old_bytes, new_bytes = (text.encode("utf-8").replace(b"\n", newline) for text in (old, new))
    if original.count(old_bytes) != 1:
        raise RuntimeError(f"{path} no longer holds {old!r} once; update {plant}.")
    path.write_bytes(original.replace(old_bytes, new_bytes))
    try:
        yield
    finally:
        path.write_bytes(original)


# T1's plants (t1-heldout.yaml), each in sample-project-2's working copy only: the committed project stays green.
FAHRENHEIT_LINE = ("return celsius * 9 / 5 + 32", "return celsius * 5 / 9 + 32")
WITHOUT_UNIT_TEST = (
    '\n    def test_format_quantity_without_unit(self) -> None:\n'
    '        self.assertEqual(format_quantity(3, ""), "3.00")\n'
)
_NO_PLACES_TEST = '        self.assertEqual(format_quantity(3, "m", places=0), "3 m")\n'


def fahrenheit_bug_planted() -> Any:
    """The fix_bug case's bug: celsius_to_fahrenheit scales by 5/9, so test_boiling_point fails (freezing still passes)."""
    return _text_replaced(f"{SAMPLE_PROJECT_2}/units.py", *FAHRENHEIT_LINE, "fahrenheit_bug_planted")


def without_unit_test_planted() -> Any:
    """The failing_test case's test: format_quantity(3, "") must be "3.00", with no trailing space; it fails as committed."""
    return _text_replaced(
        f"{SAMPLE_PROJECT_2}/test_units.py", _NO_PLACES_TEST, _NO_PLACES_TEST + WITHOUT_UNIT_TEST, "without_unit_test_planted"
    )


def exit_code(results: Iterable[EvalResults]) -> int:
    """A set's exit code: 0 when every result passed, 1 when any case failed or errored, or nothing was scored (MAF's
    EvalResults.all_passed, agent_framework/_evaluation.py:457, the check its raise_for_status makes for CI)."""
    return 0 if all(result.all_passed for result in results) else 1


# Live 2026-11-04, evals.py small: Ollama raised "error parsing tool call" in the first ask (the malformed-call retry
# gave up), the exception left the set through the workflow as an ExceptionGroup, and nothing was reported. A case
# whose run raises is recorded here, by its query, and scored as failed by run_completed; the set goes on.
CASE_ERRORS: dict[str, str] = {}


# Rounds of cards an eval answers in one run (each round answers every card then open). Live 2026-11-04 (evals.py
# small, the item_count ask): REPAIR's write took the 8th and last answer, the 9th card (the re-check) was never
# answered, and the case failed silently. 20 fits a plan, several writes, a repair, its re-check and a commit; a run
# still asking after that is looping, and fails with CardsUnanswered's reason (run_completed).
CARD_ROUNDS = 20


class CardsUnanswered(RuntimeError):
    """A run still raising cards after CARD_ROUNDS rounds: the eval stopped answering, and the case fails with this."""

    def __init__(self) -> None:
        super().__init__(f"the eval stopped answering cards after {CARD_ROUNDS} rounds")


def raised(error: BaseException, what: str = "the run") -> str:
    """A raising run's reason: the exception's type and first line, from inside the task group it came through."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    if isinstance(error, CardsUnanswered):
        return str(error)
    first = next(iter(str(error).strip().splitlines()), "")
    return f"{what} raised {type(error).__name__}: {first}" if first else f"{what} raised {type(error).__name__}"


def plant_step(plant: str | None) -> Callable[[], Any]:
    """A fixture's plant step by its name in PLANTS (None: nothing planted), its context manager looked up in this
    module when it is entered, so a test's monkeypatch of discount_bug_planted holds."""
    if plant is None:
        return contextlib.nullcontext
    return lambda: globals()[PLANTS[plant]]()


def fixture_entered(stack: contextlib.ExitStack, query: str, fixture: Callable[[], Any]) -> bool:
    """A case's fixture (discount_bug_planted) entered on ``stack``. One that raises fails that case only, with its
    reason in CASE_ERRORS (run_completed), and returns False: the case is not run, and the set goes on and records its
    history (audit 2026-11-04: a raising plant left the small set through run_small_asks, so nothing was scored)."""
    try:
        stack.enter_context(fixture())
    except Exception as error:
        CASE_ERRORS[query] = raised(error, "the case's fixture")
        return False
    return True


# The transport the asks sets' cases go over (cli's --transport; eval_transports.TRANSPORTS): in-process runs
# run_steward here; responses and ag-ui drive the running host. Each case's timings (eval_transports.CaseClock.timings:
# transport, time to the first text or reasoning event, total time, each card and whether it resumed, stream errors),
# by its query, for the history (history_entry).
TRANSPORT_IN_USE = "in-process"
CASE_TIMINGS: dict[str, dict[str, Any]] = {}
# The running case's clock (run_case sets it; the in-process card loop notes its text and cards on it).
_CLOCK: eval_transports.CaseClock | None = None


async def run_case(query: str, approve: set[str], **build: Any) -> tuple[Agent[Any] | None, AgentResponse[Any]]:
    """One case of a set through run_steward, or over TRANSPORT_IN_USE's host (eval_transports.run_over) with the same
    cards approved (card_approved: the plan, ``approve`` and the sample project's pytest). A run that raises (an
    Exception: a cancellation or Ctrl+C still stops the set), or a transport that could not finish it (a dropped stream,
    a refused resume), is recorded in CASE_ERRORS, so the case is scored, and fails, with the rest; a transport's case
    is scored on what came back. Its timings go in CASE_TIMINGS either way."""
    global _CLOCK
    CASE_ERRORS.pop(query, None)
    _CLOCK = clock = eval_transports.CaseClock(transport=TRANSPORT_IN_USE)
    try:
        if TRANSPORT_IN_USE == "in-process":
            return await run_steward(query, approve, **build)
        answers = {APPROVE_PLAN, *approve}
        response, failure = await eval_transports.run_over(
            TRANSPORT_IN_USE, query, lambda call: card_approved(call, answers), clock, CARD_ROUNDS
        )
        if failure:
            CASE_ERRORS[query] = f"the {TRANSPORT_IN_USE} transport: {failure}"
        return None, response
    except Exception as error:
        CASE_ERRORS[query] = raised(error)
        return None, AgentResponse(messages=[])
    finally:
        clock.ended = clock.ended or time.monotonic()
        CASE_TIMINGS[query] = clock.timings()
        _CLOCK = None


@evaluator(name="run_completed")
def run_completed(query: str) -> dict[str, object]:
    """A case whose run raised fails with the exception; a case that ran is not this check's ("Not this case.")."""
    if query not in CASE_ERRORS:
        return {"passed": True, "reason": "Not this case."}
    return {"passed": False, "reason": CASE_ERRORS[query]}


# Results history (2026-11-04, for SecondBrain's evals shelf): every set run appends one JSON line to
# storage/evals/history.jsonl in this repo (storage/ is gitignored), the newest EVAL_HISTORY_KEEP lines kept. The
# printed report and the exit code never depend on it: a write that fails is a warning on the log, nothing more.
_REPO = Path(__file__).resolve().parents[3]
# Every eval set, by name, read at import: a set file that cannot be used stops evals.py here, naming its problems.
EVAL_SETS = load_eval_sets()
EVAL_HISTORY = _REPO / "storage" / "evals" / "history.jsonl"
EVAL_HISTORY_KEEP = 500
# The settings set this run uses (cli's --options), as {"name", "values"}; None when it uses none.
OPTIONS_IN_USE: dict[str, Any] | None = None
# The repo's HEAD as the run began (cli sets it): live 2026-11-05, main was pulled to 2681f88 during a run of e94cb90's
# code and the run was recorded as 2681f88's.
GIT_HEAD_AT_START: str | None = None
logger = logging.getLogger(__name__)


def _git_head() -> str | None:
    """This repo's HEAD, short (a read: git rev-parse), or None when git cannot say."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return (head.stdout.strip() or None) if head.returncode == 0 else None


def history_entry(name: str, results: dict[str, Any], code: int, progress: list[str] | None = None) -> dict[str, Any]:
    """One run's line: the set, its version and tier (from its file; None for a set with no file), its settings set, its
    transport (TRANSPORT_IN_USE; each case run through run_case also carries its "timings", CASE_TIMINGS), its counts (applicable_checks for the checks), the exit code, each
    case with its failed checks (a step's cases carry the step's name), the repo's HEAD and the model's name; a steps
    run also carries its CHECK and REPAIR progress lines (StewardProgress events, in order) as "progress"."""
    items = [(step, item) for step, result in results.items() for item in result.items]
    checks_passed, checks_total = applicable_checks(item for _, item in items)
    eval_set = EVAL_SETS.get(name)  # None for the sets with no file (regression, memory)
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "set": name,
        "set_version": eval_set.version if eval_set else None,
        "tier": eval_set.tier if eval_set else None,
        "options": OPTIONS_IN_USE,
        "transport": TRANSPORT_IN_USE,
        "passed": sum(result.passed for result in results.values()),
        "total": sum(result.total for result in results.values()),
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "exit_code": code,
        "cases": [
            {
                **({"step": step} if step else {}),
                "input": (item.input_text or "")[:80],
                "passed": item.status == "pass",
                "failed_checks": [
                    {"name": score.name, "reason": str((score.sample or {}).get("reason", ""))}
                    for score in item.scores
                    if score.passed is False
                ],
                **({"timings": CASE_TIMINGS[item.input_text]} if item.input_text in CASE_TIMINGS else {}),
            }
            for step, item in items
        ],
        "git_head": GIT_HEAD_AT_START or _git_head(),  # the code the run loaded, not what is on disk when it ends
        "model": os.environ.get("OLLAMA_MODEL") or None,  # the model's name only; never a key
        **({"progress": list(progress)} if progress else {}),
    }


def record_history(
    name: str, results: dict[str, Any], code: int, path: Path | None = None, progress: list[str] | None = None,
) -> None:
    """Append the run's line to the history (EVAL_HISTORY), keeping the newest EVAL_HISTORY_KEEP lines; written to a
    temp file and moved into place. Any failure is a logged warning: the report and the exit code are never touched."""
    path = path or EVAL_HISTORY
    try:
        line = json.dumps(history_entry(name, results, code, progress), default=str)
        old = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        kept = [*(old_line for old_line in old if old_line.strip()), line][-EVAL_HISTORY_KEEP:]
        path.parent.mkdir(parents=True, exist_ok=True)
        written = path.with_suffix(".tmp")
        written.write_text("\n".join(kept) + "\n", encoding="utf-8")
        written.replace(path)
    except Exception as exc:  # noqa: BLE001 - the history never changes a set's report or exit code
        logger.warning("Eval history not written (%s): %s", path, exc)


async def main() -> int:
    """Run the local Steward evals; the exit code is exit_code's."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    local = LocalEvaluator(
        repo_status_grounded,
        codebase_map_names_files,
        bug_diagnosis,
        map_names_files,
        test_share_counted,
        research_covers_topics,
        explorer_names_files,
        tool_call_args_match,
        run_completed,
    )
    responses: list[AgentResponse[Any]] = []
    steward = None
    diagnosis = STEWARD_EVAL_QUERIES[2]  # the case the planted bug is for
    with contextlib.ExitStack() as fixtures:
        planted = fixture_entered(fixtures, diagnosis, discount_bug_planted)
        for query in STEWARD_EVAL_QUERIES:
            if query == diagnosis and not planted:
                responses.append(AgentResponse(messages=[]))  # failed by run_completed with the fixture's reason
                continue
            ran, response = await run_case(query, set(), enable_shell=False, auto_approve_skill_scripts=True)
            steward = ran or steward
            responses.append(response)
    results = await evaluate_agent(
        agent=steward,
        queries=STEWARD_EVAL_QUERIES,
        responses=responses,
        expected_tool_calls=STEWARD_EXPECTED_TOOL_CALLS,
        evaluators=local,
        # The question is the first user message and the answer every step after it (the plan card's answer and
        # EXECUTE's nudges are user messages; the default, the last turn, would score only the end).
        conversation_split=ConversationSplit.FULL,
    )
    print(f"Local evals: {results[0].passed}/{results[0].total} passed")
    for item in results[0].items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            if score.passed is False:
                print(f"      {score.name}: {(score.sample or {}).get('reason', '')}")
    code = exit_code(results)
    record_history("regression", {"": results[0]}, code)
    return code


def _called(conversation: list[Any]) -> list[str]:
    return [c.name for m in conversation or [] for c in getattr(m, "contents", None) or [] if c.type == "function_call"]


async def _noting_text(updates: Any) -> Any:
    """The run's updates as they stream, the first text or reasoning one noted on the case's clock (first_event_s)."""
    async for update in updates:
        if _CLOCK is not None and _CLOCK.first_event is None and any(
            c.type in ("text", "text_reasoning") and (getattr(c, "text", None) or "") for c in update.contents or []
        ):
            _CLOCK.text()
        yield update


async def _run_answering_cards(agent: Agent[Any], session: Any, query: str, approve: set[str]) -> AgentResponse[Any]:
    """A run whose approval cards are answered: approved for the tools in ``approve``, denied otherwise, as the
    console's Approve and Deny do (harness/console/observers/tool_approval.py).

    The response holds the answers too, each as the user's message after the turn that raised its cards, as the
    conversation has them. An approved write is in the run only there: the card is a function_approval_request, and
    the call it approves rides on the answer (written_python_files counts approved answers, never bare cards); the
    resumed run streams the write's outcome, not the call again. Live 2026-11-04 (evals.py small, the item_count ask):
    EXECUTE wrote inventory.py on an approved card and the checks passed, yet check_covers_writes and
    edit_keeps_file_whole found no write, because the answers were sent and never kept."""
    from agent_framework import Message  # noqa: PLC0415

    updates = [u async for u in _noting_text(agent.run(query, session=session, stream=True))]
    messages = list(AgentResponse.from_updates(updates).messages)
    answered: set[str] = set()
    for rounds in range(CARD_ROUNDS + 1):
        requests = [
            c for u in updates for c in u.contents
            if c.type == "function_approval_request" and c.function_call.call_id not in answered
        ]
        if not requests:
            break
        if rounds == CARD_ROUNDS:
            raise CardsUnanswered
        answered.update(request.function_call.call_id for request in requests)
        answers = [request.to_function_approval_response(approved=card_approved(request.function_call, approve)) for request in requests]
        answer = Message(role="user", contents=answers)
        cards = [_CLOCK.card(request.function_call.name, reply.approved) for request, reply in zip(requests, answers)] if _CLOCK else []
        try:
            turn = [u async for u in _noting_text(agent.run(answer, session=session, stream=True))]
        except BaseException:
            for card in cards:
                card["resumed"] = False
            raise
        for card in cards:
            card["resumed"] = True
        updates += turn
        messages += [answer, *AgentResponse.from_updates(turn).messages]
    return AgentResponse(messages=messages)


# Piece 5 (Kyle's build order, 2026-11-01): the workflow's steps scored one by one on a single run. The bug is
# planted, Steward plans its fix, the plan and his writes are approved as the user would (shell commands too; any
# other card, a commit, is denied), and each step is scored on what it did: PLAN's plan, each EXECUTE turn's write,
# and overall the report's check line and the fix on disk. MAF's evaluate_workflow runs every evaluator on every
# step and takes a resumed step's query from the user's card answer (_evaluation.py), so the steps are grouped by
# their executor ids here and each group is scored by its own LocalEvaluator. Run alone: python evals.py steps.
# The ask is the T0 set "steps" (t0-steps.yaml), its one case.
STEPS_SET = EVAL_SETS["steps"]
STEPS_QUERY = STEPS_SET.cases[0].ask
# What the plan must name, read from its steps (the cookbook: "Validators should check the artefacts themselves"). Run
# 15: a bug-fix plan passed while planning a new inventory.py instead of the discount line, because nothing checked it.
# The case's subject terms.
STEPS_MUST_NAME = STEPS_SET.cases[0].subject
# Whether the run fixed the bug, and why (discount_test_result: test_percent_discount passes as the run left the
# project). The steps set at 7a2dd79 (2026-11-05 07:13Z): his fix wrote "discount_percent/100", the tests passed, and
# the old byte check for "discount_percent / 100" read it as not fixed.
STEPS_FIXED: list[tuple[bool, str]] = [(False, "The run did not reach the fix.")]


def step_conversations(events: list[Any], approve: set[str] | None = None) -> dict[str, list[list[Any]]]:
    """Each AgentExecutor step's conversations, keyed by its executor id, from a run's events (one per completion).

    With ``approve`` (the eval's own answers, card_approved), each card a step raised and the eval approved goes into
    the conversation of that step's next completion as its function_approval_response, unless already there. MAF's
    AgentExecutor completes once, after its last card, with only the messages since that card (_agent_executor.py,
    _run_agent_and_emit). The steps set at a3a3519 (2026-11-05 06:05Z): EXECUTE's approved file_access_replace fixed
    inventory.py, two run_shell cards followed, and execute_step read "No write to inventory.py. Calls: ['todos_complete']".
    """
    from agent_framework import AgentExecutorResponse, Message  # noqa: PLC0415

    steps: dict[str, list[list[Any]]] = {}
    approved: dict[str, list[Any]] = {}
    for event in events:
        if event.type == "request_info" and approve is not None:
            card = event.data
            if getattr(card, "type", None) == "function_approval_request" and card_approved(card.function_call, approve):
                approved.setdefault(event.source_executor_id, []).append(card)
            continue
        if event.type != "executor_completed" or not event.executor_id:
            continue
        for sent in event.data if isinstance(event.data, list) else [event.data]:
            if isinstance(sent, AgentExecutorResponse):
                conversation = list(sent.full_conversation or sent.agent_response.messages)
                present = {
                    c.function_call.call_id
                    for m in conversation
                    for c in m.contents or []
                    if c.type == "function_approval_response" and c.function_call is not None
                }
                answers = [c.to_function_approval_response(True) for c in approved.pop(event.executor_id, []) if c.function_call.call_id not in present]
                if answers:
                    conversation = [Message(role="user", contents=answers), *conversation]
                steps.setdefault(event.executor_id, []).append(conversation)
    return steps


def plan_that_reached_the_card(conversations: list[list[Any]]) -> list[list[Any]]:
    """The steps set's v2 scoring (t0-steps.yaml): PLAN's completions read as one conversation, so plan_step scores
    only the last plan, the one ReadPlan sent to the card (a reply it asked again for is followed by another
    completion), and still sees every call made in any of them. Under v1 each completion was its own plan, and a
    re-asked plan that then reached the card failed. The earlier completions keep their calls and results but not their
    words, so the plan scored is the last completion's own reply (an empty last reply reached no card, and fails).
    No completion: nothing to score."""
    from agent_framework import Message  # noqa: PLC0415

    if not conversations:
        return []
    earlier = [
        Message(role=message.role, contents=[c for c in message.contents or [] if c.type != "text"])
        for conversation in conversations[:-1]
        for message in conversation
    ]
    return [[*(message for message in earlier if message.contents), *conversations[-1]]]


def _last_said(conversation: list[Any]) -> str:
    return next(
        (m.text for m in reversed(conversation or []) if getattr(m, "role", None) == "assistant" and (m.text or "").strip()), ""
    )


@evaluator(name="plan_step")
def plan_step(query: str, response: str, conversation: list[Any]) -> dict[str, object]:
    """PLAN: an approval with steps that name the work, and nothing changed while planning."""
    import steward_workflow as wf  # noqa: PLC0415
    from agent import _CHANGES_THINGS  # noqa: PLC0415

    acted = [name for name, _, outcome in _calls_in_order(conversation) if name in _CHANGES_THINGS and outcome == "ran"]
    if acted:
        return {"passed": False, "reason": f"Changed things while planning: {acted}"}
    last = _last_said(conversation)
    plan = wf.steward_plan_in(last)
    if plan is None or plan.type.value != "approval":
        return {"passed": False, "reason": f"No approval plan with steps: {last[:200]!r}"}
    said = " ".join([plan.questions[0].message, *plan.steps]).lower()
    missing = [term for term in STEPS_MUST_NAME if term not in said]
    if missing:
        return {"passed": False, "reason": f"The plan does not name {missing}: {plan.steps}"}
    return {"passed": True, "reason": f"Planned {len(plan.steps)} steps: {plan.steps}"}


@evaluator(name="execute_step")
def execute_step(query: str, response: str, conversation: list[Any]) -> dict[str, object]:
    """EXECUTE (each turn, a repair too): an approved write to the module the plan is about."""
    import steward_workflow as wf  # noqa: PLC0415

    written = wf.written_python_files(conversation)
    ok = any(name.endswith("inventory.py") for name in written)
    calls = [name for name, _, _ in _calls_in_order(conversation)]
    return {"passed": ok, "reason": f"Wrote {written}." if ok else f"No write to inventory.py. Calls: {calls[:14]}"}


@evaluator(name="steps_overall")
def steps_overall(query: str, response: str) -> dict[str, object]:
    """Overall: the report carries the check's pass, and the discount line is fixed on disk."""
    if "Checks passed" not in (response or ""):
        return {"passed": False, "reason": f"The report has no passed checks: {(response or '')[-240:]!r}"}
    fixed, why = STEPS_FIXED[0]
    if not fixed:
        return {"passed": False, "reason": f"Not fixed: {why}"}
    return {"passed": True, "reason": f"Checks passed, and {why}"}


async def _run_workflow_answering_cards(workflow: Any, query: str, approve: set[str]) -> list[Any]:
    """Every event of one run, its cards answered: approved for the names in ``approve``, denied otherwise."""
    events = [e async for e in workflow.run(query, stream=True)]
    answered: set[str] = set()
    for rounds in range(CARD_ROUNDS + 1):
        pending = [e for e in events if e.type == "request_info" and e.request_id not in answered]
        if not pending:
            break
        if rounds == CARD_ROUNDS:
            raise CardsUnanswered
        responses = {}
        for card in pending:
            answered.add(card.request_id)
            responses[card.request_id] = card.data.to_function_approval_response(card_approved(card.data.function_call, approve))
        events += [e async for e in workflow.run(stream=True, responses=responses)]
    return events


async def steps_main() -> int:
    """One run of the workflow on the planted bug, each step scored by its own evaluator; the exit code is exit_code's."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    import steward_workflow as wf  # noqa: PLC0415
    from agent_framework import ConversationSplit, EvalItem, FileAccessProvider, Message  # noqa: PLC0415

    # The plan and the writes; a shell card only for the sample project's pytest (card_approved), every other denied.
    approve = {wf.APPROVE_PLAN, *FileAccessProvider._WRITE_TOOL_NAMES}  # noqa: SLF001
    async with AsyncExitStack() as stack:
        agent, workflow = await wf.build_steward(
            stack, auto_approve_skill_scripts=True, file_memory_store=isolated_memory(stack),
            memory_store=isolated_memory_store(stack), eval_build=True,
        )
        async with agent:
            sample_project_as_committed()
            CASE_ERRORS.pop(STEPS_QUERY, None)
            events = []
            untracked_before = untracked_files()
            with contextlib.ExitStack() as fixtures:
                fixtures.callback(remove_new_untracked, untracked_before)  # last out: after the bug is put back
                if fixture_entered(fixtures, STEPS_QUERY, plant_step(STEPS_SET.cases[0].plant)):  # else overall fails with its reason
                    try:
                        events = await _run_workflow_answering_cards(workflow, STEPS_QUERY, approve)
                    except Exception as error:  # the run raised: overall fails with it (run_completed); the bug is put back
                        CASE_ERRORS[STEPS_QUERY] = raised(error)
                    STEPS_FIXED[0] = discount_test_result()
                else:
                    STEPS_FIXED[0] = (False, "The bug was not planted, so nothing ran.")
    steps = step_conversations(events, approve)
    outputs = [str(e.data) for e in events if e.type == "output"]
    user = Message(role="user", contents=[STEPS_QUERY])

    def items(conversations: list[list[Any]]) -> list[Any]:
        return [EvalItem([user, *c], split_strategy=SPLITS[STEPS_SET.split]) for c in conversations]

    # The run's report is all its outputs: the checks' result comes before the commit card's answer (AskCommit), and
    # the eval denies the commit, so the last output alone was "The commit ... was not approved" (a3a3519).
    report = [EvalItem([user, Message(role="assistant", contents=["\n\n".join(outputs)])], split_strategy=ConversationSplit.FULL)]
    scored = {
        wf.PLAN_STEP: await LocalEvaluator(plan_step).evaluate(
            items(plan_that_reached_the_card(steps.get(wf.PLAN_STEP, []))), eval_name="plan"
        ),
        wf.EXECUTE_STEP: await LocalEvaluator(execute_step).evaluate(items(steps.get(wf.EXECUTE_STEP, [])), eval_name="execute"),
        "overall": await LocalEvaluator(steps_overall, run_completed).evaluate(report, eval_name="overall"),
    }
    code = exit_code(scored.values())
    print(f"Workflow steps: {'PASS' if code == 0 else 'FAIL'}")
    for step, result in scored.items():
        print(f"  {step}: {result.passed}/{result.total}")
        for item in result.items:
            for score in item.scores:
                if (score.sample or {}).get("reason") != "Not this case.":
                    print(f"      [{'pass' if score.passed else 'fail'}] {(score.sample or {}).get('reason', '')}")
    record_history("steps", scored, code, progress=[str(e.data) for e in events if e.type == wf.PROGRESS])
    return code


# Step 4: evals as small single asks (the cookbook's evaluation flywheel: today's failures labelled, grouped, and
# each given a check; MAF's guide evals.py: run each query yourself with its cards answered, then
# evaluate_agent(..., responses=...)). Each ask runs once through the workflow as the Agent tab runs it
# (run_steward), the plan and the writes approved as the user would, the commit card denied: nothing is committed.
# A check that is not its ask's passes ("Not this case."), as the guide's evaluators do. Run: python evals.py small.

# Live 2026-11-02 (run 1): order_total already had a docstring, so he rightly asked a clarification; and fixing
# the planted discount bug puts inventory.py back to its committed text, so the check finds nothing changed and no
# commit follows. The commit and check-coverage cases therefore ride on new code, which the tests still pass.
# The asks, their checks and their subjects are the set files' (harness/steward/evals/, read by load_eval_sets): the
# small asks are the T0 set "small" (t0-small.yaml), and every set the asks runner runs is in the maps below.
SMALL_SET = EVAL_SETS["small"]
SMALL_ASK_NEW_CODE = SMALL_SET.case("item_count").ask
SMALL_ASK_DISCOUNT = SMALL_SET.case("discount").ask
SMALL_ASK_README = SMALL_SET.case("readme").ask
SMALL_ASKS = SMALL_SET.asks
_ASK_CASES = [case for eval_set in EVAL_SETS.values() if eval_set.runner == "asks" for case in eval_set.cases]
# Which of today's failures each ask checks (the cookbook's axial codes, one check each).
SMALL_ASK_CHECKS: dict[str, set[str]] = {case.ask: set(case.checks) for case in _ASK_CASES}
# What an on-topic answer and a specific commit message name, per ask.
SMALL_ASK_SUBJECT: dict[str, tuple[str, ...]] = {case.ask: case.subject for case in _ASK_CASES}
# Each ask's fixture: (its sample project, its plant step or None).
CASE_FIXTURES: dict[str, tuple[str, str | None]] = {case.ask: (case.project, case.plant) for case in _ASK_CASES}
VAGUE_COMMIT_MESSAGES = {"update", "updates", "changes", "change", "fix", "fixes", "wip", "checkpoint", "commit", "work"}
# The files each run wrote, as they stood on disk when the run ended (read before the planted bug is put back): only
# writes that happened, the file changed on disk. An approved card can still be refused by his write middleware
# (whole_write_problem, the Unicode-punctuation check) or fail in MAF's tool ("already exists"); the workflow-as-agent
# response carries no tool results (MAF's WorkflowAgent forwards assistant messages only), so the disk says.
SMALL_ASK_FILES: dict[str, dict[str, str]] = {}
SMALL_ASK_ORIGINALS: dict[str, str] = {}
# Each ask's result checks, measured on the sample project after its run and before the reset (deterministic, no
# model): {query: {check name: (passed, reason)}}. The cookbook's answer-level checks: the artefact does the job.
SMALL_ASK_RESULTS: dict[str, dict[str, tuple[bool, str]]] = {}


def _not_this_case(name: str, query: str) -> dict[str, object] | None:
    return None if name in SMALL_ASK_CHECKS.get(query, set()) else {"passed": True, "reason": "Not this case."}


def _assistant_text(conversation: list[Any]) -> str:
    return "\n".join(m.text or "" for m in conversation or [] if getattr(m, "role", None) == "assistant")


def _cards_named(conversation: list[Any], name: str) -> list[Any]:
    return [
        c for m in conversation or [] for c in getattr(m, "contents", None) or []
        if c.type == "function_approval_request" and c.function_call is not None and c.function_call.name == name
    ]


@evaluator(name="plan_is_approval")
def plan_is_approval(query: str, conversation: list[Any]) -> dict[str, object]:
    """Failure 1, the plan labelled as a clarification: the run reaches the plan card (approve_plan)."""
    import steward_workflow as wf  # noqa: PLC0415

    if skip := _not_this_case("plan_is_approval", query):
        return skip
    ok = bool(_cards_named(conversation, wf.APPROVE_PLAN))
    return {"passed": ok, "reason": "The plan came as an approval card." if ok else f"No plan card: {_assistant_text(conversation)[:160]!r}"}


@evaluator(name="check_covers_writes")
def check_covers_writes(query: str, response: str, conversation: list[Any]) -> dict[str, object]:
    """Failure 2, a write missed behind a later card: the check ran the tests of every .py file the run wrote."""
    import steward_workflow as wf  # noqa: PLC0415

    if skip := _not_this_case("check_covers_writes", query):
        return skip
    written = wf.written_python_files(conversation)
    if query in SMALL_ASK_FILES:  # a run's writes that happened on disk (an approved card can still be refused)
        written = [f for f in written if f in SMALL_ASK_FILES[query]]
    if not written:
        return {"passed": False, "reason": "No approved .py write in the run."}
    missed = [f for f in written if f"$ pytest -q {Path(f).parent.as_posix()}" not in (response or "").replace("\\", "/")]
    return {"passed": not missed, "reason": f"The check covered {written}." if not missed else f"Not checked: {missed}"}


@evaluator(name="edit_keeps_file_whole")
def edit_keeps_file_whole(query: str) -> dict[str, object]:
    """Failure 3, a broken edit (tabs): every .py file the run wrote (and that changed on disk) still parses, gained no
    tab indentation, and still has every top-level function and class it had (audit 2026-11-04: a file cut to a stub
    that parses passed)."""
    import ast  # noqa: PLC0415

    if skip := _not_this_case("edit_keeps_file_whole", query):
        return skip
    files = SMALL_ASK_FILES.get(query, {})
    if not files:
        return {"passed": False, "reason": "The run wrote no .py file."}
    for name, text in files.items():
        try:
            tree = ast.parse(text)
        except SyntaxError as error:
            return {"passed": False, "reason": f"{name} no longer parses: {error}"}
        before = SMALL_ASK_ORIGINALS.get(name, "")
        if "\n\t" in text and "\n\t" not in before:
            return {"passed": False, "reason": f"{name} gained tab indentation."}
        if lost := sorted(_top_level_names(before) - _top_level_names(tree)):
            return {"passed": False, "reason": f"{name} lost its {lost}."}
    return {"passed": True, "reason": f"{sorted(files)} parse, indentation and top-level definitions kept."}


def _top_level_names(source: Any) -> set[str]:
    """The names of a module's top-level functions and classes (source text or a parsed tree); none when it does not parse."""
    import ast  # noqa: PLC0415

    try:
        tree = ast.parse(source) if isinstance(source, str) else source
    except SyntaxError:
        return set()
    kinds = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return {node.name for node in tree.body if isinstance(node, kinds)}


@evaluator(name="commit_by_tool")
def commit_by_tool(query: str, response: str, conversation: list[Any]) -> dict[str, object]:
    """Failure 4, "proceed?" instead of git_commit: after "Checks passed" his own git_commit raises the card, and the
    door's commit (atlas_git_commit, a real card in SecondBrain) is not used."""
    if skip := _not_this_case("commit_by_tool", query):
        return skip
    if "Checks passed" not in (response or ""):
        return {"passed": False, "reason": f"The checks did not pass, so no commit step: {(response or '')[-200:]!r}"}
    if any(name == "atlas_git_commit" for name in _called(conversation)):
        return {"passed": False, "reason": "Committed through the door (atlas_git_commit): deny that card in SecondBrain."}
    ok = bool(_cards_named(conversation, "git_commit"))
    return {"passed": ok, "reason": "git_commit raised the card." if ok else f"No git_commit card: {_assistant_text(conversation)[-200:]!r}"}


@evaluator(name="commit_message_specific")
def commit_message_specific(query: str, conversation: list[Any]) -> dict[str, object]:
    """Failure 5, a vague commit message: the card's message names the change, not a word like "update"."""
    if skip := _not_this_case("commit_message_specific", query):
        return skip
    cards = _cards_named(conversation, "git_commit")
    if not cards:
        return {"passed": False, "reason": "No git_commit card to read."}
    message = str((cards[-1].function_call.parse_arguments() or {}).get("message", "")).strip()
    vague = message.lower().strip(" .!") in VAGUE_COMMIT_MESSAGES
    named = any(term in message.lower() for term in SMALL_ASK_SUBJECT[query])
    ok = not vague and named
    return {"passed": ok, "reason": f"Message {message!r}."}


@evaluator(name="no_nudge_in_reply")
def no_nudge_in_reply(query: str, conversation: list[Any]) -> dict[str, object]:
    """Failure 6, the loop's nudge in his reply: no assistant text repeats a harness message meant for him."""
    import steward_workflow as wf  # noqa: PLC0415
    from agent import PLAN_REPLY_NUDGE, PLAN_TODOS_NUDGE, REQUIRED_TOOLS_NUDGE, TODOS_ALREADY_SHOWN, TOOLS_OFF_ANSWER_NOW  # noqa: PLC0415

    if skip := _not_this_case("no_nudge_in_reply", query):
        return skip
    said = _assistant_text(conversation)
    harness_texts = [
        PLAN_REPLY_NUDGE, PLAN_TODOS_NUDGE, REQUIRED_TOOLS_NUDGE, TODOS_ALREADY_SHOWN, TOOLS_OFF_ANSWER_NOW,
        wf.PLAN_IS_APPROVAL, wf.PLAN_AGAIN, wf.COMMIT_NOW,
        "open todo item(s) that must be addressed before you can finish",  # MAF's todos_remaining_message
    ]
    echoed = [text[:60] for text in harness_texts if text.split("{")[0][:60] in said]
    return {"passed": not echoed, "reason": "No harness message in his replies." if not echoed else f"Echoed: {echoed}"}


@evaluator(name="answer_on_topic")
def answer_on_topic(query: str, conversation: list[Any]) -> dict[str, object]:
    """Failure 7, an off-topic final answer: his own last reply names what was asked. The workflow's own outputs
    (ask_commit's "Checks passed", report, and commit's COMMIT_NOT_APPROVED, which quotes the commit message) are the
    harness's, not his: audit 2026-11-04, the denied commit's sentence named item_count and passed this check for him."""
    if skip := _not_this_case("answer_on_topic", query):
        return skip
    last = _stewards_last_reply(conversation).lower()
    ok = any(term in last for term in SMALL_ASK_SUBJECT[query])
    return {"passed": ok, "reason": "On topic." if ok else f"Last reply misses {SMALL_ASK_SUBJECT[query]}: {last[:160]!r}"}


def _stewards_last_reply(conversation: list[Any]) -> str:
    """His own last reply: his words in the last round that has any (back to the user's message before it: the ask or
    a card's answer), not the workflow's harness steps' (MAF's WorkflowAgent names each output's executor as its
    author_name; the Responses wire names none, so their texts are known by their words, _harness_says).

    Live 2026-11-05 (the Responses transport, 0/3 on answer_on_topic): the last text was ask_commit's "Checks passed",
    which came with no step name; and on the README ask his round's last pass said only "All pending todo items have
    been completed." after the README line (the host's _only_his_own_words splits a pass from the next, where
    in-process the round is one message)."""
    import steward_workflow as wf  # noqa: PLC0415

    harness_steps = {wf.COMMIT_STEP, wf.REPORT_STEP, wf.REPAIR_STEP, "ask_commit"}
    said: list[str] = []
    for message in reversed(conversation or []):
        role = getattr(message, "role", None)
        if role == "user":
            if said:
                break
            continue
        text = (getattr(message, "text", "") or "").strip()
        if role != "assistant" or not text:
            continue
        if getattr(message, "author_name", None) in harness_steps or _harness_says(text):
            if said:
                break
            continue
        said.append(text)
    return "\n".join(reversed(said))


def _harness_says(text: str) -> bool:
    """Whether a text is one of the workflow's own outputs: the checks' result (ask_commit, report: checks_text), a
    repair's failing checks (repair_text), the commit's result (agent.git_commit) or COMMIT_NOT_APPROVED. Read from the
    functions and sentences themselves, so a changed wording changes this with it."""
    import steward_workflow as wf  # noqa: PLC0415
    from agent import NOTHING_TO_COMMIT  # noqa: PLC0415

    marker = "987654321"
    forms = [
        wf.checks_text(wf.CheckReport(int(marker), True, "", "")),
        wf.checks_text(wf.CheckReport(int(marker), False, "", "")),
        wf.repair_text(wf.CheckReport(int(marker), False, "", "")),
    ]
    starts = [re.escape(form.strip()).replace(marker, r"\d+") for form in forms]
    not_approved = [re.escape(part) for part in wf.COMMIT_NOT_APPROVED.split("{message}")]
    patterns = [
        *(rf"{start}(?:\s.*)?" for start in starts),
        rf"{not_approved[0]}.*{not_approved[1]}",
        re.escape(NOTHING_TO_COMMIT),
        r"Committed [0-9a-f]{4,40}: .*",  # agent.git_commit's result
        r"git (?:add|commit) failed: .*",
    ]
    return any(re.fullmatch(pattern, text, re.DOTALL) for pattern in patterns)


# Result checks (audit 2026-11-04, the cookbook's answer-level checks): the process checks above can all pass on a run
# whose work does not do the job. These run the sample project as it stands after the ask, before the reset.
ITEM_COUNT_PROBE = "from inventory import Item, item_count\nprint(item_count([Item('a', 1.0, 2), Item('b', 2.0, 3)]))\n"
ITEM_COUNT_EXPECTED = "5"


def discount_test_result() -> tuple[bool, str]:
    """The sample project's tests (pytest, as the workflow's check runs them): passed only when test_percent_discount
    itself is among the passes."""
    from agent import _WORKING_DIR  # noqa: PLC0415
    from steward_workflow import _CHECK_RUNNING  # noqa: PLC0415

    command = [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", SAMPLE_PROJECT]
    try:
        done = subprocess.run(
            command, cwd=_WORKING_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
            env={**os.environ, _CHECK_RUNNING: "1"},
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"The sample project's tests did not run: {error}"
    ok = any(
        line.startswith("PASSED ") and line.split()[1].endswith("::test_percent_discount") for line in done.stdout.splitlines()
    )
    tail = (done.stdout + done.stderr).strip().splitlines()[-1:] or [""]
    return ok, ("test_percent_discount passes." if ok else f"test_percent_discount does not pass (exit {done.returncode}): {tail[0][:160]}")


def item_count_result() -> tuple[bool, str]:
    """inventory.item_count, imported in a fresh Python, returns the total quantity of two Items (2 + 3)."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    try:
        done = subprocess.run(
            [sys.executable, "-c", ITEM_COUNT_PROBE], cwd=_WORKING_DIR / SAMPLE_PROJECT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"item_count was not run: {error}"
    got = done.stdout.strip()
    if done.returncode == 0 and got == ITEM_COUNT_EXPECTED:
        return True, f"item_count returns the total quantity ({got})."
    said = (done.stderr.strip().splitlines() or [got])[-1]
    return False, f"item_count of quantities 2 and 3 gave {got or 'nothing'}, not {ITEM_COUNT_EXPECTED}: {said[:160]}"


def readme_run_tests_result() -> tuple[bool, str]:
    """The README ask's result: sample-project's README says how to run its tests (it names unittest or pytest)."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    text = (_WORKING_DIR / SAMPLE_PROJECT / "README.md").read_text(encoding="utf-8")
    ok = bool(re.search(r"\b(unittest|pytest)\b", text, re.IGNORECASE))
    return ok, ("The README says how to run the tests." if ok else "The README names neither unittest nor pytest.")


def _fresh_bytecode(cache: str) -> dict[str, str]:
    """The environment for a measurement's Python: its bytecode cache in ``cache`` (a new folder), so no .pyc from
    before reads as the module. A plant and its fix can be the same size within the same second (the fix_bug case's
    5 / 9 and 9 / 5), and Python's cache, checked by size and mtime, then ran the planted code (the gate, 2026-11-05)."""
    return {**os.environ, "PYTHONPYCACHEPREFIX": cache}


def _module_probe(project: str, code: str, expected: str, what: str) -> tuple[bool, str]:
    """``code`` run in a fresh Python in a sample project: passed when it prints ``expected``."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    try:
        with tempfile.TemporaryDirectory() as cache:
            done = subprocess.run(
                [sys.executable, "-c", code], cwd=_WORKING_DIR / project, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60, env=_fresh_bytecode(cache),
            )
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"{what} was not run: {error}"
    got = done.stdout.strip()
    if done.returncode == 0 and got == expected:
        return True, f"{what}: {got}."
    said = (done.stderr.strip().splitlines() or [got])[-1]
    return False, f"{what} gave {got or 'nothing'}, not {expected}: {said[:160]}"


def _project_tests(project: str) -> tuple[int, set[str], str]:
    """A sample project's tests run as the workflow's check runs them: (exit code, the passed tests' names, the last
    line); exit -1 when pytest did not run."""
    from agent import _WORKING_DIR  # noqa: PLC0415
    from steward_workflow import _CHECK_RUNNING  # noqa: PLC0415

    command = [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", project]
    try:
        with tempfile.TemporaryDirectory() as cache:
            done = subprocess.run(
                command, cwd=_WORKING_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=300, env={**_fresh_bytecode(cache), _CHECK_RUNNING: "1"},
            )
    except (OSError, subprocess.SubprocessError) as error:
        return -1, set(), str(error)
    passed = {line.split()[1].rsplit("::", 1)[-1] for line in done.stdout.splitlines() if line.startswith("PASSED ")}
    tail = (done.stdout + done.stderr).strip().splitlines()[-1:] or [""]
    return done.returncode, passed, tail[0][:160]


def _test_passes(project: str, test: str) -> tuple[bool, str]:
    code, passed, tail = _project_tests(project)
    ok = test in passed
    return ok, (f"{test} passes." if ok else f"{test} does not pass (exit {code}): {tail}")


def fahrenheit_to_celsius_result() -> tuple[bool, str]:
    """T1 add_function: units.fahrenheit_to_celsius gives 100, 0 and -40 for 212, 32 and -40."""
    probe = (
        "from units import fahrenheit_to_celsius as f\n"
        "print(all(abs(f(a) - b) < 1e-9 for a, b in ((212, 100), (32, 0), (-40, -40))))\n"
    )
    return _module_probe(SAMPLE_PROJECT_2, probe, "True", "fahrenheit_to_celsius of 212, 32 and -40")


def boiling_point_test_result() -> tuple[bool, str]:
    """T1 fix_bug: test_boiling_point passes on sample-project-2 as the run left it."""
    return _test_passes(SAMPLE_PROJECT_2, "test_boiling_point")


def metres_per_unit_result() -> tuple[bool, str]:
    """T1 refactor: LENGTH_IN_METRES is named nowhere in the project's code, units.py binds METRES_PER_UNIT at its top
    level, and every test passes."""
    import ast  # noqa: PLC0415

    from agent import _WORKING_DIR  # noqa: PLC0415

    project = _WORKING_DIR / SAMPLE_PROJECT_2
    if left := sorted(p.name for p in project.glob("*.py") if "LENGTH_IN_METRES" in p.read_text(encoding="utf-8")):
        return False, f"LENGTH_IN_METRES is still named in {left}."
    try:
        tree = ast.parse((project / "units.py").read_text(encoding="utf-8"))
    except SyntaxError as error:
        return False, f"units.py no longer parses: {error}"
    bound: set[str] = set()
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        bound |= {target.id for target in targets if isinstance(target, ast.Name)}
    if "METRES_PER_UNIT" not in bound:
        return False, "units.py binds no METRES_PER_UNIT at its top level."
    code, passed, tail = _project_tests(SAMPLE_PROJECT_2)
    return code == 0, ("Renamed, and every test passes." if code == 0 else f"Renamed, but the tests fail (exit {code}): {tail}")


def readme_length_units_result() -> tuple[bool, str]:
    """T1 docs_line: sample-project-2's README names the length units mm, cm, km and ft."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    text = (_WORKING_DIR / SAMPLE_PROJECT_2 / "README.md").read_text(encoding="utf-8")
    missing = [unit for unit in ("mm", "cm", "km", "ft") if not re.search(rf"\b{unit}\b", text)]
    return not missing, ("The README lists the length units." if not missing else f"The README does not name {missing}.")


def without_unit_test_result() -> tuple[bool, str]:
    """T1 failing_test: the planted test_format_quantity_without_unit is still there, unchanged, and passes."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    tests = (_WORKING_DIR / SAMPLE_PROJECT_2 / "test_units.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    if WITHOUT_UNIT_TEST.strip("\n") not in tests:
        return False, "test_format_quantity_without_unit was changed or removed."
    return _test_passes(SAMPLE_PROJECT_2, "test_format_quantity_without_unit")


def measure_result(check: str) -> tuple[bool, str]:
    """A result check's measurement (RESULT_CHECKS), looked up in this module when it runs."""
    return globals()[RESULT_CHECKS[check]]()


# Each result check's measurement, by the ask it belongs to (run_small_asks runs it after the ask's run): every result
# check a set file names for its case.
SMALL_ASK_RESULT_CHECKS: dict[str, dict[str, Callable[[], tuple[bool, str]]]] = {
    case.ask: {name: (lambda name=name: measure_result(name)) for name in case.checks if name in RESULT_CHECKS}
    for case in _ASK_CASES
}


def _result_check(name: str, query: str) -> dict[str, object]:
    if skip := _not_this_case(name, query):
        return skip
    measured = SMALL_ASK_RESULTS.get(query, {}).get(name)
    if measured is None:
        return {"passed": False, "reason": "Not measured: the ask did not run."}
    return {"passed": measured[0], "reason": measured[1]}


@evaluator(name="item_count_works")
def item_count_works(query: str) -> dict[str, object]:
    """The item_count ask's result: the function it added returns the total quantity."""
    return _result_check("item_count_works", query)


@evaluator(name="discount_test_passes")
def discount_test_passes(query: str) -> dict[str, object]:
    """The discount ask's result: test_percent_discount passes on the sample project as the run left it."""
    return _result_check("discount_test_passes", query)


@evaluator(name="readme_says_how_to_run_tests")
def readme_says_how_to_run_tests(query: str) -> dict[str, object]:
    """The README ask's result: the README names unittest or pytest after the run."""
    return _result_check("readme_says_how_to_run_tests", query)


@evaluator(name="fahrenheit_to_celsius_works")
def fahrenheit_to_celsius_works(query: str) -> dict[str, object]:
    """T1 add_function's result."""
    return _result_check("fahrenheit_to_celsius_works", query)


@evaluator(name="boiling_point_test_passes")
def boiling_point_test_passes(query: str) -> dict[str, object]:
    """T1 fix_bug's result."""
    return _result_check("boiling_point_test_passes", query)


@evaluator(name="metres_per_unit_renamed")
def metres_per_unit_renamed(query: str) -> dict[str, object]:
    """T1 refactor's result."""
    return _result_check("metres_per_unit_renamed", query)


@evaluator(name="readme_lists_length_units")
def readme_lists_length_units(query: str) -> dict[str, object]:
    """T1 docs_line's result."""
    return _result_check("readme_lists_length_units", query)


@evaluator(name="without_unit_test_passes")
def without_unit_test_passes(query: str) -> dict[str, object]:
    """T1 failing_test's result."""
    return _result_check("without_unit_test_passes", query)


# The eval gate (step 6, 6.2): the improvement loop keeps a change only if the small-ask checks do not drop below
# the recorded baseline. The baseline is raised by the operator after a real improvement (a one-line edit). Baselines
# are kept per set version in harness/steward/evals/baselines.json (EVAL_BASELINES, with each version's fingerprint).


def applicable_checks(items: Any) -> tuple[int, int]:
    """(passed, total) over the checks that apply to their ask (a "Not this case." pass does not count)."""
    passed = total = 0
    for item in items:
        for score in item.scores:
            if (score.sample or {}).get("reason") == "Not this case.":
                continue
            total += 1
            passed += bool(score.passed)
    return passed, total


def gate(passed: int, total: int, name: str = "small", baselines: Path = EVAL_BASELINES) -> int:
    """The gate's exit code: 0 when the checks are at or above the baseline of the set's current version, 1 when they
    dropped. (A file whose set entry holds "checks" itself is read as that one baseline.)"""
    entry = json.loads(baselines.read_text(encoding="utf-8"))[name]
    if "checks" not in entry:
        entry = entry[str(EVAL_SETS[name].version)]
    baseline = int(entry["checks"])
    ok = passed >= baseline
    print(f"Gate: {passed}/{total} checks against the baseline of {baseline}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


SMALL_ASK_EVALUATORS = (
    plan_is_approval, check_covers_writes, edit_keeps_file_whole, commit_by_tool, commit_message_specific,
    no_nudge_in_reply, answer_on_topic, item_count_works, discount_test_passes, readme_says_how_to_run_tests,
    fahrenheit_to_celsius_works, boiling_point_test_passes, metres_per_unit_renamed, readme_lists_length_units,
    without_unit_test_passes, run_completed,
)


async def run_small_asks(
    asks: list[str], around: Callable[[str], Any] | None = None, **build: Any
) -> tuple[Agent[Any] | None, list[AgentResponse[Any]]]:
    """Each ask once through his workflow (run_steward), as small_main runs the small asks: the plan card and the writes
    approved, every other card denied, the discount bug planted for the discount ask only, the sample project put back
    after each, each run on its own throwaway memory. ``around(ask)`` is a context entered around each run (the
    diagnosis opens the ask's trace span there). Define once: small_main and the diagnosis (improvement_loop.py) both
    run their asks here."""
    import steward_workflow as wf  # noqa: PLC0415
    from agent import _WORKING_DIR  # noqa: PLC0415
    from agent_framework import FileAccessProvider  # noqa: PLC0415

    build.setdefault("auto_approve_skill_scripts", True)
    CASE_TIMINGS.clear()  # this set's cases only
    # Each ask's sample project and plant step are its set file's (CASE_FIXTURES); an ask in no set is sample-project's.
    named = sorted({CASE_FIXTURES.get(query, (SAMPLE_PROJECT, None))[0] for query in asks})
    for name in named:
        sample_project_as_committed(name)
    projects = [_WORKING_DIR / name for name in named]
    SMALL_ASK_ORIGINALS.clear()
    SMALL_ASK_ORIGINALS.update(
        {p.relative_to(_WORKING_DIR).as_posix(): p.read_text(encoding="utf-8") for project in projects for p in project.glob("*.py")}
    )
    originals = {p: p.read_bytes() for project in projects for p in project.iterdir() if p.is_file()}
    untracked_before = untracked_files()  # anything a run adds elsewhere in the repository goes in reset()
    # Writes approved, and a shell card only for the sample project's pytest (card_approved), as the steps set and the
    # user approve them; every other shell command and git_commit denied.
    approve = set(FileAccessProvider._WRITE_TOOL_NAMES)  # noqa: SLF001
    SMALL_ASK_RESULTS.clear()
    responses: list[AgentResponse[Any]] = []
    steward = None
    def reset() -> None:
        """The sample projects as committed: every file put back, anything a run added removed, in them or anywhere
        else in the repository (remove_new_untracked)."""
        for path in (path for project in projects for path in project.iterdir()):
            if path.is_file() and path not in originals:
                path.unlink()
        for path, data in originals.items():
            path.write_bytes(data)
        remove_new_untracked(untracked_before)

    try:
        for query in asks:
            # Only an ask whose fixture names a plant has it (the discount ask's bug: in the others a failing test would
            # send the run to repair; the README ask's how-to taken out: otherwise it asks for a line already there).
            name, plant = CASE_FIXTURES.get(query, (SAMPLE_PROJECT, None))
            project = _WORKING_DIR / name
            with (around or contextlib.nullcontext)(query), contextlib.ExitStack() as fixtures:
                if plant is not None and not fixture_entered(fixtures, query, plant_step(plant)):
                    responses.append(AgentResponse(messages=[]))  # the case fails with the fixture's reason; the set goes on
                    SMALL_ASK_FILES[query] = {}
                    continue
                before = {p.relative_to(_WORKING_DIR).as_posix(): p.read_bytes() for p in project.iterdir() if p.is_file()}
                ran, response = await run_case(query, approve, **build)  # a raising run is a failed case; reset follows
                steward = ran or steward
                responses.append(response)
                # Only writes that happened: the file is on disk and changed (or new) since the run began.
                written = [
                    name for name in wf.written_python_files(response.messages)
                    if (_WORKING_DIR / name).is_file() and (_WORKING_DIR / name).read_bytes() != before.get(name)
                ]
                SMALL_ASK_FILES[query] = {name: (_WORKING_DIR / name).read_text(encoding="utf-8") for name in written}
                SMALL_ASK_RESULTS[query] = {name: measure() for name, measure in SMALL_ASK_RESULT_CHECKS.get(query, {}).items()}
            reset()  # each ask starts from the committed sample project
    finally:
        reset()  # the reset before any save
    return steward, responses


async def score_small_asks(
    steward: Any, asks: list[str], responses: list[AgentResponse[Any]], eval_set: EvalSet | None = None
) -> Any:
    """The small-ask checks on each ask's run (MAF's evaluate_agent): one result, an item per ask. The set (default the
    small set) gives MAF its eval_name (<set>@v<version>), its split, and each case's expected_output and
    expected_tool_calls; when any case names tool calls, MAF's tool_call_args_match scores them."""
    eval_set = eval_set or SMALL_SET
    cases = {case.ask: case for case in eval_set.cases}
    mine = [cases.get(ask) for ask in asks]
    evaluators: list[Any] = list(SMALL_ASK_EVALUATORS)
    extra: dict[str, Any] = {}
    if any(case and case.expected_output for case in mine):
        extra["expected_output"] = [(case.expected_output or "") if case else "" for case in mine]
    if any(case and case.expected_tool_calls for case in mine):
        extra["expected_tool_calls"] = [list(case.expected_tool_calls) if case else [] for case in mine]
        evaluators.append(tool_call_args_match)
    results = await evaluate_agent(
        agent=steward,
        queries=asks,
        responses=responses,
        evaluators=LocalEvaluator(*evaluators),
        eval_name=eval_set.eval_name,
        conversation_split=SPLITS[eval_set.split],
        **extra,
    )
    return results[0]


async def small_main(use_gate: bool = False) -> int:
    """Step 4's small asks, one run each, scored with their checks; with use_gate, the exit code is the gate's, without
    it exit_code's."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    steward, responses = await run_small_asks(SMALL_ASKS)
    result = await score_small_asks(steward, SMALL_ASKS, responses)
    passed, total = print_asks_report("Small asks", "Small-ask checks", result)
    code = gate(passed, total) if use_gate else exit_code([result])
    record_history("small", {"": result}, code)
    return code


def print_asks_report(cases_label: str, checks_label: str, result: Any) -> tuple[int, int]:
    """An asks set's report: its cases passed, each case with its applicable checks, and the checks passed; the
    (passed, total) of those checks."""
    print(f"{cases_label}: {result.passed}/{result.total} passed")
    for item in result.items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            if (score.sample or {}).get("reason") != "Not this case.":
                print(f"      [{'pass' if score.passed else 'fail'}] {score.name}: {(score.sample or {}).get('reason', '')}")
    passed, total = applicable_checks(result.items)
    print(f"{checks_label}: {passed}/{total}")
    return passed, total


async def set_main(name: str) -> int:
    """Any other asks set from its file (T1's heldout, and the sets that follow), as small_main runs the small asks:
    each ask once, scored with its checks; the exit code is exit_code's, and the run is recorded under the set's name.
    A non-gating set (tier ext) with num_repetitions runs the whole set that many times, each pass scored and recorded
    on its own (a flakiness check); the exit code is the worst pass's."""
    eval_set = EVAL_SETS[name]
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    codes = []
    for _ in range(eval_set.num_repetitions):
        steward, responses = await run_small_asks(eval_set.asks)
        result = await score_small_asks(steward, eval_set.asks, responses, eval_set)
        print_asks_report(f"{eval_set.tier} {eval_set.eval_name}", "Checks", result)
        codes.append(exit_code([result]))
        record_history(name, {"": result}, codes[-1])
    return max(codes)


def validate_sets(folder: Path = EVAL_SETS_DIR, baselines: Path | None = None) -> list[str]:
    """Every set file in ``folder`` checked with no model; the problems, one per line (none: every set is valid).

    Each file's schema (_schema_problems: its keys, names, bar and the runner's checks; every case has a RESULT check
    and a precondition among them). Each case's precondition must FAIL on its unmodified fixture: the plant step entered
    and the result check measured, as before a run, so an ask its fixture already satisfies (the old README ask) is
    refused. Set names and asks are each used once. Each set version's cases match the fingerprint recorded for that
    version in baselines.json: a changed case or check without a new version is refused, and a version with no
    fingerprint is named with the one to record. And each check a runner names has its evaluator or measurement here."""
    baselines = baselines or folder / "baselines.json"
    problems: list[str] = []
    missing = [n for n in ASKS_PROCESS_CHECKS + ASKS_RESULT_CHECKS if n not in {e.__name__ for e in SMALL_ASK_EVALUATORS}]
    missing += [f"{n} (measurement {f})" for n, f in RESULT_CHECKS.items() if not callable(globals().get(f))]
    missing += [n for n in STEPS_CHECKS if not callable(globals().get(n))]
    missing += [f"plant {n} ({f})" for n, f in PLANTS.items() if not callable(globals().get(f))]
    problems += [f"evals.py: no check {n}" for n in missing]
    try:
        recorded = json.loads(baselines.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        recorded = {}
        problems.append(f"{baselines.name}: cannot be read: {error}")
    sets: dict[str, EvalSet] = {}
    asks: dict[str, str] = {}
    for path in sorted(folder.glob("*.yaml")):
        try:
            eval_set = load_eval_set(path)
        except EvalSetError as error:
            problems += str(error).splitlines()
            continue
        if eval_set.name in sets:
            problems.append(f"{path.name}: the set name {eval_set.name!r} is also {sets[eval_set.name].path.name}'s")
        sets[eval_set.name] = eval_set
        fingerprint = recorded.get(eval_set.name, {}).get(str(eval_set.version), {}).get("cases")
        if fingerprint is None:
            problems.append(
                f"{path.name}: version {eval_set.version} has no fingerprint in {baselines.name}; record "
                f'"{eval_set.name}": {{"{eval_set.version}": {{"cases": "{eval_set.fingerprint}"}}}}'
            )
        elif fingerprint != eval_set.fingerprint:
            problems.append(
                f"{path.name}: its cases changed but its version did not: give it version {eval_set.version + 1}, say "
                f"what changed under changes, and record its fingerprint {eval_set.fingerprint}"
            )
        for case in eval_set.cases:
            if eval_set.runner == "asks" and case.ask in asks:  # the asks runner keys its cases by their ask
                problems.append(f"{path.name}: case {case.id!r}'s ask is also a case of {asks[case.ask]}")
            if eval_set.runner == "asks":
                asks[case.ask] = path.name
            try:
                with plant_step(case.plant)():
                    held, reason = measure_result(case.precondition)
            except Exception as error:  # noqa: BLE001 - a plant or a measurement that raises is the case's problem
                problems.append(f"{path.name}: case {case.id!r}: its fixture or precondition raised {type(error).__name__}: {error}")
                continue
            if held:
                problems.append(
                    f"{path.name}: case {case.id!r}: its precondition {case.precondition} already passes on the "
                    f"unmodified fixture ({reason}), so the ask asks for what is there"
                )
    return problems


def validate_main() -> int:
    """python evals.py validate: 0 and one line when every set is valid, else each problem and 1."""
    problems = validate_sets()
    if problems:
        print("\n".join(problems))
        return 1
    print(f"Eval sets valid: {', '.join(f'{s.tier} {s.name} v{s.version}' for s in EVAL_SETS.values())}")
    return 0


def bar_status(name: str, history: Path | None = None) -> tuple[bool, str]:
    """Whether a set's bar is met: its last bar["runs_in_a_row"] runs in the history are runs of its current version,
    each with at least bar["passed"] of its cases passed."""
    eval_set = EVAL_SETS[name]
    bar = eval_set.bar
    path = history or EVAL_HISTORY
    runs = []
    for line in (path.read_text(encoding="utf-8").splitlines() if path.is_file() else []):
        try:
            run = json.loads(line)
        except ValueError:
            continue
        if run.get("set") == name:
            runs.append(run)
    last = runs[-bar["runs_in_a_row"]:]
    scores = [f"{run.get('passed')}/{run.get('total')}" + ("" if run.get("set_version") == eval_set.version else f" (v{run.get('set_version')})") for run in last]
    met = len(last) == bar["runs_in_a_row"] and all(
        run.get("set_version") == eval_set.version and int(run.get("passed") or 0) >= bar["passed"] for run in last
    )
    want = f"{bar['passed']}/{bar['of']} {bar['runs_in_a_row']}x in a row"
    return met, f"{eval_set.tier} {name} v{eval_set.version} bar {want}: {'MET' if met else 'NOT MET'} (last: {', '.join(scores) or 'none'})"


# Step 5, piece 5.3: a note saved in one request is recalled in the next. Two requests through his workflow
# (run_steward), each a new conversation, share one throwaway automatic memory (MAF's MemoryContextProvider store;
# file memory is each request's own), so a recall proves the provider and nothing reaches his real memory. The first states a fact about the sample project that cannot be guessed
# and asks him to remember it; the second asks for it. Run once: python evals.py memory.
MEMORY_FACT = "Kestrel-47"
MEMORY_REMEMBER = f"Remember this about harness/steward/working/sample-project: its next release is codenamed {MEMORY_FACT}."
MEMORY_RECALL = "What is the codename of harness/steward/working/sample-project's next release?"
MEMORY_QUERIES = [MEMORY_REMEMBER, MEMORY_RECALL]
# gpt-oss types a hyphen as Unicode's (live 2026-11-03: "Kestrel‑47" with U+2011 failed a recall that had happened).
_HYPHENS = str.maketrans({c: "-" for c in "‐‑‒–—−"})


@evaluator(name="memory_recalled")
def memory_recalled(query: str, response: str) -> dict[str, object]:
    """The second request, a new conversation, answers with the fact the first one saved."""
    if query != MEMORY_RECALL:
        return {"passed": True, "reason": "Not the recall case."}
    ok = MEMORY_FACT.lower() in (response or "").translate(_HYPHENS).lower()
    return {"passed": ok, "reason": f"Recalled {MEMORY_FACT} in a new conversation." if ok else f"Not recalled: {(response or '')[-160:]!r}"}


async def memory_runs(**build: Any) -> tuple[Agent[Any] | None, list[AgentResponse[Any]]]:
    """The memory set's requests, each a new conversation through run_steward, sharing one throwaway automatic memory
    for the set. File memory is NOT shared (run_steward gives each request its own), so a recall proves MAF's
    MemoryContextProvider carried the fact, not a file note."""
    steward = None
    responses: list[AgentResponse[Any]] = []
    async with AsyncExitStack() as stack:
        build.setdefault("memory_store", isolated_memory_store(stack))
        for query in MEMORY_QUERIES:
            ran, response = await run_case(query, set(), **build)
            steward = ran or steward
            responses.append(response)
    return steward, responses


async def memory_main() -> int:
    """Step 5's memory case, one run of each request, scored with memory_recalled; the exit code is exit_code's."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    steward, responses = await memory_runs(auto_approve_skill_scripts=True)
    results = await evaluate_agent(
        agent=steward,
        queries=MEMORY_QUERIES,
        responses=responses,
        evaluators=LocalEvaluator(memory_recalled, run_completed),
        conversation_split=ConversationSplit.FULL,
    )
    print(f"Memory: {results[0].passed}/{results[0].total} passed")
    for item in results[0].items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            if (score.sample or {}).get("reason") != "Not this case.":
                print(f"      [{'pass' if score.passed else 'fail'}] {score.name}: {(score.sample or {}).get('reason', '')}")
    code = exit_code(results)
    record_history("memory", {"": results[0]}, code)
    return code


# Settings sets (2026-11-04): Steward fumbled an inline `VAR=x VAR=y python evals.py small`. A named set of per-step
# model options is kept in eval_options.json and run with --options NAME.
EVAL_OPTIONS = Path(__file__).resolve().with_name("eval_options.json")


def apply_options(name: str, path: Path = EVAL_OPTIONS) -> str:
    """Set the named settings set's STEWARD_<STEP>_* variables for this run, before Steward is built (steward_workflow
    reads them at build), and return the report's line naming the set. An unknown name, a key that is no step option or
    a bad value raises ValueError, before anything runs."""
    import steward_workflow as wf  # noqa: PLC0415

    sets = json.loads(path.read_text(encoding="utf-8"))
    if name not in sets:
        raise ValueError(f"no settings set {name!r} in {path.name}; its sets: {', '.join(sets)}")
    values = {key: str(value) for key, value in sets[name].items()}
    known = {f"STEWARD_{step.upper()}_{option}" for step in wf.STEP_OPTION_STEPS for option in ("THINK", "TEMPERATURE", "SEED")}
    if unknown := sorted(set(values) - known):
        raise ValueError(f"settings set {name!r} names {unknown}, which are not step options ({', '.join(sorted(known))})")
    wf.step_options_from_env(values)  # a bad value raises here, naming its variable
    os.environ.update(values)
    global OPTIONS_IN_USE
    OPTIONS_IN_USE = {"name": name, "values": values}
    return f"Settings set {name}: {', '.join(f'{key}={value}' for key, value in values.items()) or 'no step options'}"


# <compare-transports>
def _median(values: list[float]) -> float | None:
    values = sorted(values)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else round((values[middle - 1] + values[middle]) / 2, 2)


def _set_runs(set_name: str, history: Path | None = None) -> list[dict[str, Any]]:
    """The history's runs of ``set_name``, oldest first (a line that does not parse is skipped)."""
    path = history or EVAL_HISTORY
    runs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            run = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(run, dict) and run.get("set") == set_name:
            runs.append(run)
    return runs


def runs_left_out(set_name: str = "small", version: int | None = None, history: Path | None = None) -> dict[str, dict[int, int]]:
    """The runs transport_comparison leaves out for being of another version of the set: {transport: {version: runs}}.
    Live 2026-11-05: main was pulled to the set's v2 while the responses run (v1) was going, so the comparison under
    v2 printed "-" for responses with no word of the run it had left out."""
    version = version if version is not None else (EVAL_SETS[set_name].version if set_name in EVAL_SETS else None)
    left: dict[str, dict[int, int]] = {}
    for run in _set_runs(set_name, history):
        other = run.get("set_version")
        if version is not None and other not in (version, None):
            counts = left.setdefault(run.get("transport") or "in-process", {})
            counts[other] = counts.get(other, 0) + 1
    return left


def transport_comparison(
    set_name: str = "small", last: int = 3, history: Path | None = None, version: int | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """From the history, each transport's last ``last`` runs of ``set_name`` (a line with no transport is in-process),
    per case: {transport: {case input: {runs, passed, first_event_s (median), total_s (median), cards, resumed,
    stream_errors}}}. Only runs of one version of the set count (like with like): ``version``, or the set's current
    one; runs_left_out names the others."""
    version = version if version is not None else (EVAL_SETS[set_name].version if set_name in EVAL_SETS else None)
    runs: dict[str, list[dict[str, Any]]] = {name: [] for name in eval_transports.TRANSPORTS}
    for run in _set_runs(set_name, history):
        if version is not None and run.get("set_version") not in (version, None):
            continue
        runs.setdefault(run.get("transport") or "in-process", []).append(run)
    table: dict[str, dict[str, dict[str, Any]]] = {}
    for transport, kept in runs.items():
        cases: dict[str, dict[str, Any]] = {}
        for run in kept[-last:] if last > 0 else []:
            for case in run.get("cases") or []:
                row = cases.setdefault(case.get("input") or "", {
                    "runs": 0, "passed": 0, "first": [], "total": [], "cards": 0, "resumed": 0, "stream_errors": 0,
                })
                timings = case.get("timings") or {}
                row["runs"] += 1
                row["passed"] += bool(case.get("passed"))
                if timings.get("first_event_s") is not None:
                    row["first"].append(float(timings["first_event_s"]))
                if timings.get("total_s") is not None:
                    row["total"].append(float(timings["total_s"]))
                row["cards"] += int(timings.get("cards") or 0)
                row["resumed"] += int(timings.get("cards_resumed") or 0)
                row["stream_errors"] += len(timings.get("stream_errors") or [])
        for row in cases.values():
            row["first_event_s"], row["total_s"] = _median(row.pop("first")), _median(row.pop("total"))
        table[transport] = cases
    return table


def ag_ui_decision(table: dict[str, dict[str, dict[str, Any]]]) -> tuple[bool, list[str]]:
    """The README's rule: AG-UI on by default only if, on every case, it matches or beats responses on the result (the
    share of runs passed) and on the resumes (the share of cards resumed), with no stream error. (on, the reasons not)."""
    ag_ui, responses = table.get("ag-ui") or {}, table.get("responses") or {}
    if not ag_ui or not responses:
        return False, ["no ag-ui and responses runs to compare"]
    reasons: list[str] = []

    def share(part: int, whole: int) -> float:
        return part / whole if whole else 1.0

    for case, base in responses.items():
        mine = ag_ui.get(case)
        if mine is None:
            reasons.append(f"{case[:40]!r}: no ag-ui run")
            continue
        if share(mine["passed"], mine["runs"]) < share(base["passed"], base["runs"]):
            reasons.append(f"{case[:40]!r}: result {mine['passed']}/{mine['runs']} < responses {base['passed']}/{base['runs']}")
        if share(mine["resumed"], mine["cards"]) < share(base["resumed"], base["cards"]):
            reasons.append(f"{case[:40]!r}: resumed {mine['resumed']}/{mine['cards']} < responses {base['resumed']}/{base['cards']}")
    for case, mine in ag_ui.items():
        if mine["stream_errors"]:
            reasons.append(f"{case[:40]!r}: {mine['stream_errors']} ag-ui stream error(s)")
    return not reasons, reasons


def compare_transports_main(args: list[str]) -> int:
    """``compare-transports [--set NAME] [--last N] [--set-version V]``: the per-case table of in-process vs responses
    vs ag-ui from the history (transport_comparison, of the set's version V, or its current one), a line for each
    transport's runs of other versions it leaves out (runs_left_out), and the README's decision line (ag_ui_decision).
    Runs nothing; 0, or 2 for bad args."""
    set_name, last, version = "small", 3, None
    try:
        if "--set" in args:
            set_name = args[args.index("--set") + 1]
        if "--last" in args:
            last = int(args[args.index("--last") + 1])
        if "--set-version" in args:
            version = int(args[args.index("--set-version") + 1])
    except (IndexError, ValueError):
        print("evals.py compare-transports [--set NAME] [--last N] [--set-version V]", file=sys.stderr)
        return 2
    if version is None and set_name in EVAL_SETS:
        version = EVAL_SETS[set_name].version
    table = transport_comparison(set_name, last, version=version)
    print(
        f"Transports on {set_name}" + (f" v{version}" if version is not None else "") + f", the last {last} run(s) of "
        "each (passed/runs, first event s, total s, cards resumed/answered, stream errors):"
    )
    for transport, counts in runs_left_out(set_name, version).items():
        others = ", ".join(f"{n} of v{v}" for v, n in sorted(counts.items(), key=lambda kv: str(kv[0])))
        print(f"  {transport}: left out {others} (--set-version to compare them)")
    cases = list(dict.fromkeys(case for transport in eval_transports.TRANSPORTS for case in table.get(transport, {})))

    def cell(row: dict[str, Any] | None) -> str:
        if not row:
            return "-"
        first = "-" if row["first_event_s"] is None else f"{row['first_event_s']:g}"
        total = "-" if row["total_s"] is None else f"{row['total_s']:g}"
        return f"{row['passed']}/{row['runs']} {first}s {total}s {row['resumed']}/{row['cards']} e{row['stream_errors']}"

    width = 30
    print(f"  {'case':<40} " + " ".join(f"{transport:<{width}}" for transport in eval_transports.TRANSPORTS))
    for case in cases:
        print(f"  {case[:40]:<40} " + " ".join(f"{cell(table.get(t, {}).get(case)):<{width}}" for t in eval_transports.TRANSPORTS))
    on, reasons = ag_ui_decision(table)
    print("Decision: AG-UI on by default." if on else f"Decision: keep AG-UI off by default ({'; '.join(reasons)}).")
    return 0
# </compare-transports>


def cli(argv: list[str]) -> int:
    """evals.py's command line, ``[small [--gate] | steps | memory | <set name>] [--options NAME] [--transport T]``,
    ``validate``, ``bar <set name>`` or ``compare-transports [--set NAME] [--last N]``: the set's exit code, or 2 for a
    settings set or transport that cannot be used (the reason on stderr, and nothing run). validate checks every set file (validate_main); bar prints whether a set's bar is met (0) or not (1),
    from the history, running nothing."""
    global GIT_HEAD_AT_START, OPTIONS_IN_USE, TRANSPORT_IN_USE
    OPTIONS_IN_USE = None  # a run uses only the settings set it names
    TRANSPORT_IN_USE = "in-process"  # and only the transport it names
    args = list(argv)
    if args[:1] == ["validate"]:
        return validate_main()
    if args[:1] == ["compare-transports"]:
        return compare_transports_main(args[1:])
    if args[:1] == ["bar"]:
        if len(args) != 2 or args[1] not in EVAL_SETS:
            print(f"evals.py bar: name one set: {', '.join(EVAL_SETS)}", file=sys.stderr)
            return 2
        met, line = bar_status(args[1])
        print(line)
        return 0 if met else 1
    GIT_HEAD_AT_START = _git_head()  # a set run from here on: the code it runs is what is checked out now
    if "--options" in args:
        at = args.index("--options")
        name = args[at + 1] if at + 1 < len(args) else ""
        del args[at : at + 2]
        try:
            line = apply_options(name)
        except ValueError as error:
            print(f"evals.py --options: {error}", file=sys.stderr)
            return 2
        print(line)
    if "--transport" in args:
        at = args.index("--transport")
        transport = args[at + 1] if at + 1 < len(args) else ""
        del args[at : at + 2]
        named = EVAL_SETS.get(args[0]) if args else None
        if transport not in eval_transports.TRANSPORTS:
            print(f"evals.py --transport: one of {', '.join(eval_transports.TRANSPORTS)}", file=sys.stderr)
            return 2
        if transport != "in-process" and (named is None or named.runner != "asks"):
            print("evals.py --transport: a host transport runs an asks set (small, heldout) only", file=sys.stderr)
            return 2
        TRANSPORT_IN_USE = transport
        print(f"Transport: {transport}")
    runs = {"steps": steps_main, "small": small_main, "memory": memory_main}
    if args[:1] == ["small"]:
        return asyncio.run(small_main(use_gate="--gate" in args))
    if args and args[0] not in runs and args[0] in EVAL_SETS:
        return asyncio.run(set_main(args[0]))  # an asks set with no main of its own (T1's heldout)
    return asyncio.run(runs[args[0]]() if args and args[0] in runs else main())


if __name__ == "__main__":
    # a reason can carry characters Windows' console code page cannot print (2026-10-30: U+2011)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(cli(sys.argv[1:]))
