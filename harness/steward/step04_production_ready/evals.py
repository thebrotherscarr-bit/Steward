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

Run:
    python harness/steward/step04_production_ready/evals.py [small [--gate] | steps | memory] [--options NAME]
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
import contextlib
from collections.abc import Callable, Iterable
from contextlib import AsyncExitStack, contextmanager
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
from halo_traces import HaloJsonlSpanExporter  # noqa: E402
from steward_workflow import APPROVE_PLAN, build_steward  # noqa: E402

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


def _calls_in_order(conversation: list[Any]) -> list[tuple[str, Any, str]]:
    """Every tool call in the run, in order, with its arguments and its outcome: "ran", "card" (left on an
    approval card) or "refused" (the plan-mode gate's corrective feedback)."""
    from agent import PLAN_MODE_REFUSAL, PLAN_MODE_TODOS_NOT_DONE  # noqa: PLC0415

    markers = (PLAN_MODE_REFUSAL.split("{name}")[0], PLAN_MODE_TODOS_NOT_DONE)
    refused = {
        content.call_id
        for message in conversation or []
        for content in getattr(message, "contents", None) or []
        if content.type == "function_result" and str(content.result or "").startswith(markers)
    }
    calls: list[tuple[str, Any, str]] = []
    for message in conversation or []:
        for content in getattr(message, "contents", None) or []:
            if content.type == "function_call":
                calls.append((content.name, content.parse_arguments(), "refused" if content.call_id in refused else "ran"))
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
# The one shell command an eval approves (the evals run real commands on his PC): pytest, or python -m pytest, with
# only -q, -rA or -p no:cacheprovider, on the sample project or a test file (and test) in it. Nothing else: no second
# command, no pipe, no redirect.
_SAMPLE_PYTEST = re.compile(
    r"(?:[\w.:/-]*python(?:3)?(?:\.exe)?\s+-m\s+)?pytest"
    r"(?:\s+(?:-q|-rA|-p\s+no:cacheprovider))*"
    r"\s+(?:\./)?" + re.escape(SAMPLE_PROJECT) + r"(?:/[\w-]+\.py(?:::[\w:]+)?)?/?"
    r"(?:\s+(?:-q|-rA|-p\s+no:cacheprovider))*"
)


def is_sample_project_pytest(command: str) -> bool:
    """Whether a shell command is only the sample project's pytest (_SAMPLE_PYTEST), backslashes read as slashes."""
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


def sample_project_as_committed() -> None:
    """The sample project put back to its committed text before a run snapshots it. The runs' own resets put back
    what was on disk when they began, so a damaged file outlived every run (2026-11-04: inventory.py, cut to a
    stand-in at 10:14, was the "original" of each eval after it)."""
    from agent import _WORKING_DIR  # noqa: PLC0415

    subprocess.run(["git", "checkout", "HEAD", "--", SAMPLE_PROJECT], cwd=_WORKING_DIR, check=True, capture_output=True)


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


def exit_code(results: Iterable[EvalResults]) -> int:
    """A set's exit code: 0 when every result passed, 1 when any case failed or errored, or nothing was scored (MAF's
    EvalResults.all_passed, agent_framework/_evaluation.py:457, the check its raise_for_status makes for CI)."""
    return 0 if all(result.all_passed for result in results) else 1


# Live 2026-11-04, evals.py small: Ollama raised "error parsing tool call" in the first ask (the malformed-call retry
# gave up), the exception left the set through the workflow as an ExceptionGroup, and nothing was reported. A case
# whose run raises is recorded here, by its query, and scored as failed by run_completed; the set goes on.
CASE_ERRORS: dict[str, str] = {}


def raised(error: BaseException, what: str = "the run") -> str:
    """A raising run's reason: the exception's type and first line, from inside the task group it came through."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    first = next(iter(str(error).strip().splitlines()), "")
    return f"{what} raised {type(error).__name__}: {first}" if first else f"{what} raised {type(error).__name__}"


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


async def run_case(query: str, approve: set[str], **build: Any) -> tuple[Agent[Any] | None, AgentResponse[Any]]:
    """One case of a set through run_steward. A run that raises (an Exception: a cancellation or Ctrl+C still stops the
    set) is recorded in CASE_ERRORS and answered with an empty response, so the case is scored, and fails, with the rest."""
    CASE_ERRORS.pop(query, None)
    try:
        return await run_steward(query, approve, **build)
    except Exception as error:
        CASE_ERRORS[query] = raised(error)
        return None, AgentResponse(messages=[])


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
EVAL_HISTORY = _REPO / "storage" / "evals" / "history.jsonl"
EVAL_HISTORY_KEEP = 500
# The settings set this run uses (cli's --options), as {"name", "values"}; None when it uses none.
OPTIONS_IN_USE: dict[str, Any] | None = None
logger = logging.getLogger(__name__)


def _git_head() -> str | None:
    """This repo's HEAD, short (a read: git rev-parse), or None when git cannot say."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return (head.stdout.strip() or None) if head.returncode == 0 else None


def history_entry(name: str, results: dict[str, Any], code: int) -> dict[str, Any]:
    """One run's line: the set, its settings set, its counts (applicable_checks for the checks), the exit code, each
    case with its failed checks (a step's cases carry the step's name), the repo's HEAD and the model's name."""
    items = [(step, item) for step, result in results.items() for item in result.items]
    checks_passed, checks_total = applicable_checks(item for _, item in items)
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "set": name,
        "options": OPTIONS_IN_USE,
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
            }
            for step, item in items
        ],
        "git_head": _git_head(),
        "model": os.environ.get("OLLAMA_MODEL") or None,  # the model's name only; never a key
    }


def record_history(name: str, results: dict[str, Any], code: int, path: Path | None = None) -> None:
    """Append the run's line to the history (EVAL_HISTORY), keeping the newest EVAL_HISTORY_KEEP lines; written to a
    temp file and moved into place. Any failure is a logged warning: the report and the exit code are never touched."""
    path = path or EVAL_HISTORY
    try:
        line = json.dumps(history_entry(name, results, code), default=str)
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

    updates = [u async for u in agent.run(query, session=session, stream=True)]
    messages = list(AgentResponse.from_updates(updates).messages)
    answered: set[str] = set()
    for _ in range(8):
        requests = [
            c for u in updates for c in u.contents
            if c.type == "function_approval_request" and c.function_call.call_id not in answered
        ]
        if not requests:
            break
        answered.update(request.function_call.call_id for request in requests)
        answers = [request.to_function_approval_response(approved=card_approved(request.function_call, approve)) for request in requests]
        answer = Message(role="user", contents=answers)
        turn = [u async for u in agent.run(answer, session=session, stream=True)]
        updates += turn
        messages += [answer, *AgentResponse.from_updates(turn).messages]
    return AgentResponse(messages=messages)


# Piece 5 (Kyle's build order, 2026-11-01): the workflow's steps scored one by one on a single run. The bug is
# planted, Steward plans its fix, the plan and his writes are approved as the user would (shell commands too; any
# other card, a commit, is denied), and each step is scored on what it did: PLAN's plan, each EXECUTE turn's write,
# and overall the report's check line and the fix on disk. MAF's evaluate_workflow runs every evaluator on every
# step and takes a resumed step's query from the user's card answer (_evaluation.py), so the steps are grouped by
# their executor ids here and each group is scored by its own LocalEvaluator. Run alone: python evals.py steps.
STEPS_QUERY = "Fix the bug that makes test_percent_discount fail in harness/steward/working/sample-project."
# What the plan must name, read from its steps (the cookbook: "Validators should check the artefacts themselves"). Run
# 15: a bug-fix plan passed while planning a new inventory.py instead of the discount line, because nothing checked it.
STEPS_MUST_NAME = ("inventory.py", "discount")
STEPS_FIXED: list[bool] = [False]


def step_conversations(events: list[Any]) -> dict[str, list[list[Any]]]:
    """Each AgentExecutor step's conversations, keyed by its executor id, from a run's events (one per completion)."""
    from agent_framework import AgentExecutorResponse  # noqa: PLC0415

    steps: dict[str, list[list[Any]]] = {}
    for event in events:
        if event.type != "executor_completed" or not event.executor_id:
            continue
        for sent in event.data if isinstance(event.data, list) else [event.data]:
            if isinstance(sent, AgentExecutorResponse):
                steps.setdefault(event.executor_id, []).append(list(sent.full_conversation or sent.agent_response.messages))
    return steps


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
    if not STEPS_FIXED[0]:
        return {"passed": False, "reason": "The discount line was not fixed on disk."}
    return {"passed": True, "reason": "Checks passed, and the discount line is fixed."}


async def _run_workflow_answering_cards(workflow: Any, query: str, approve: set[str]) -> list[Any]:
    """Every event of one run, its cards answered: approved for the names in ``approve``, denied otherwise."""
    events = [e async for e in workflow.run(query, stream=True)]
    answered: set[str] = set()
    for _ in range(12):
        pending = [e for e in events if e.type == "request_info" and e.request_id not in answered]
        if not pending:
            break
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
    from agent import _WORKING_DIR  # noqa: PLC0415
    from agent_framework import ConversationSplit, EvalItem, FileAccessProvider, Message  # noqa: PLC0415

    module = _WORKING_DIR / "harness" / "steward" / "working" / "sample-project" / "inventory.py"
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
            with contextlib.ExitStack() as fixtures:
                if fixture_entered(fixtures, STEPS_QUERY, discount_bug_planted):  # else overall fails with its reason
                    try:
                        events = await _run_workflow_answering_cards(workflow, STEPS_QUERY, approve)
                    except Exception as error:  # the run raised: overall fails with it (run_completed); the bug is put back
                        CASE_ERRORS[STEPS_QUERY] = raised(error)
                    STEPS_FIXED[0] = b"discount_percent / 100" in module.read_bytes()
                else:
                    STEPS_FIXED[0] = False
    steps = step_conversations(events)
    outputs = [str(e.data) for e in events if e.type == "output"]
    user = Message(role="user", contents=[STEPS_QUERY])

    def items(conversations: list[list[Any]]) -> list[Any]:
        return [EvalItem([user, *c], split_strategy=ConversationSplit.FULL) for c in conversations]

    report = [EvalItem([user, Message(role="assistant", contents=[outputs[-1] if outputs else ""])], split_strategy=ConversationSplit.FULL)]
    scored = {
        wf.PLAN_STEP: await LocalEvaluator(plan_step).evaluate(items(steps.get(wf.PLAN_STEP, [])), eval_name="plan"),
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
    record_history("steps", scored, code)
    return code


# Step 4: evals as small single asks (the cookbook's evaluation flywheel: today's failures labelled, grouped, and
# each given a check; MAF's guide evals.py: run each query yourself with its cards answered, then
# evaluate_agent(..., responses=...)). Each ask runs once through the workflow as the Agent tab runs it
# (run_steward), the plan and the writes approved as the user would, the commit card denied: nothing is committed.
# A check that is not its ask's passes ("Not this case."), as the guide's evaluators do. Run: python evals.py small.

# Live 2026-11-02 (run 1): order_total already had a docstring, so he rightly asked a clarification; and fixing
# the planted discount bug puts inventory.py back to its committed text, so the check finds nothing changed and no
# commit follows. The commit and check-coverage cases therefore ride on new code, which the tests still pass.
SMALL_ASK_NEW_CODE = (
    "Add a function item_count(items) to harness/steward/working/sample-project/inventory.py that returns the total "
    "quantity of all the items, with a docstring."
)
SMALL_ASK_DISCOUNT = "Fix the bug that makes test_percent_discount fail in harness/steward/working/sample-project."
SMALL_ASK_README = "Add one line to harness/steward/working/sample-project/README.md that says how to run its tests."
SMALL_ASKS = [SMALL_ASK_NEW_CODE, SMALL_ASK_DISCOUNT, SMALL_ASK_README]
# Which of today's failures each ask checks (the cookbook's axial codes, one check each).
SMALL_ASK_CHECKS: dict[str, set[str]] = {
    SMALL_ASK_NEW_CODE: {
        "plan_is_approval", "edit_keeps_file_whole", "check_covers_writes", "commit_by_tool", "commit_message_specific",
        "no_nudge_in_reply", "answer_on_topic", "item_count_works",
    },
    SMALL_ASK_DISCOUNT: {"plan_is_approval", "edit_keeps_file_whole", "no_nudge_in_reply", "answer_on_topic", "discount_test_passes"},
    SMALL_ASK_README: {"plan_is_approval", "no_nudge_in_reply", "answer_on_topic"},
}
# What an on-topic answer and a specific commit message name, per ask.
SMALL_ASK_SUBJECT: dict[str, tuple[str, ...]] = {
    SMALL_ASK_NEW_CODE: ("item_count",),
    SMALL_ASK_DISCOUNT: ("discount",),
    SMALL_ASK_README: ("readme", "test"),
}
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
    from agent import PLAN_REPLY_NUDGE, PLAN_TODOS_NUDGE, REQUIRED_TOOLS_NUDGE, TODOS_ALREADY_SHOWN  # noqa: PLC0415

    if skip := _not_this_case("no_nudge_in_reply", query):
        return skip
    said = _assistant_text(conversation)
    harness_texts = [
        PLAN_REPLY_NUDGE, PLAN_TODOS_NUDGE, REQUIRED_TOOLS_NUDGE, TODOS_ALREADY_SHOWN, wf.PLAN_IS_APPROVAL, wf.PLAN_AGAIN, wf.COMMIT_NOW,
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
    """His own last reply: the last assistant text not written by the workflow's harness steps (MAF's WorkflowAgent
    names each output's executor as its author_name) and not the harness's COMMIT_NOT_APPROVED sentence."""
    import steward_workflow as wf  # noqa: PLC0415

    harness_steps = {wf.COMMIT_STEP, wf.REPORT_STEP, "ask_commit"}
    not_approved = wf.COMMIT_NOT_APPROVED.split("{message}")
    for message in reversed(conversation or []):
        text = (getattr(message, "text", "") or "").strip()
        if getattr(message, "role", None) != "assistant" or not text or getattr(message, "author_name", None) in harness_steps:
            continue
        if text.startswith(not_approved[0]) and text.endswith(not_approved[1]):
            continue
        return text
    return ""


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


# Each result check's measurement, by the ask it belongs to (run_small_asks runs it after the ask's run).
SMALL_ASK_RESULT_CHECKS: dict[str, dict[str, Callable[[], tuple[bool, str]]]] = {
    SMALL_ASK_NEW_CODE: {"item_count_works": item_count_result},
    SMALL_ASK_DISCOUNT: {"discount_test_passes": discount_test_result},
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


# The eval gate (step 6, 6.2): the improvement loop keeps a change only if the small-ask checks do not drop below
# the recorded baseline. The baseline is raised by the operator after a real improvement (a one-line edit).
EVAL_BASELINES = Path(__file__).resolve().with_name("eval_baselines.json")


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
    """The gate's exit code: 0 when the checks are at or above the set's baseline, 1 when they dropped."""
    baseline = int(json.loads(baselines.read_text(encoding="utf-8"))[name]["checks"])
    ok = passed >= baseline
    print(f"Gate: {passed}/{total} checks against the baseline of {baseline}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


SMALL_ASK_EVALUATORS = (
    plan_is_approval, check_covers_writes, edit_keeps_file_whole, commit_by_tool, commit_message_specific,
    no_nudge_in_reply, answer_on_topic, item_count_works, discount_test_passes, run_completed,
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
    project = _WORKING_DIR / "harness" / "steward" / "working" / "sample-project"
    sample_project_as_committed()
    SMALL_ASK_ORIGINALS.clear()
    SMALL_ASK_ORIGINALS.update({p.relative_to(_WORKING_DIR).as_posix(): p.read_text(encoding="utf-8") for p in project.glob("*.py")})
    originals = {p: p.read_bytes() for p in project.iterdir() if p.is_file()}
    # Writes approved, and a shell card only for the sample project's pytest (card_approved), as the steps set and the
    # user approve them; every other shell command and git_commit denied.
    approve = set(FileAccessProvider._WRITE_TOOL_NAMES)  # noqa: SLF001
    SMALL_ASK_RESULTS.clear()
    responses: list[AgentResponse[Any]] = []
    steward = None
    def reset() -> None:
        """The sample project as committed: every file put back, anything a run added removed."""
        for path in project.iterdir():
            if path.is_file() and path not in originals:
                path.unlink()
        for path, data in originals.items():
            path.write_bytes(data)

    try:
        for query in asks:
            # Only the discount ask has the bug planted: in the others a failing test would send the run to repair.
            with (around or contextlib.nullcontext)(query), contextlib.ExitStack() as fixtures:
                if query == SMALL_ASK_DISCOUNT and not fixture_entered(fixtures, query, discount_bug_planted):
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


async def score_small_asks(steward: Any, asks: list[str], responses: list[AgentResponse[Any]]) -> Any:
    """The small-ask checks on each ask's run (MAF's evaluate_agent, the full split): one result, an item per ask."""
    results = await evaluate_agent(
        agent=steward,
        queries=asks,
        responses=responses,
        evaluators=LocalEvaluator(*SMALL_ASK_EVALUATORS),
        conversation_split=ConversationSplit.FULL,
    )
    return results[0]


async def small_main(use_gate: bool = False) -> int:
    """Step 4's small asks, one run each, scored with their checks; with use_gate, the exit code is the gate's, without
    it exit_code's."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    steward, responses = await run_small_asks(SMALL_ASKS)
    result = await score_small_asks(steward, SMALL_ASKS, responses)
    print(f"Small asks: {result.passed}/{result.total} passed")
    for item in result.items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            if (score.sample or {}).get("reason") != "Not this case.":
                print(f"      [{'pass' if score.passed else 'fail'}] {score.name}: {(score.sample or {}).get('reason', '')}")
    passed, total = applicable_checks(result.items)
    print(f"Small-ask checks: {passed}/{total}")
    code = gate(passed, total) if use_gate else exit_code([result])
    record_history("small", {"": result}, code)
    return code


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


def cli(argv: list[str]) -> int:
    """evals.py's command line, ``[small [--gate] | steps | memory] [--options NAME]``: the set's exit code, or 2 for a
    settings set that cannot be used (the reason on stderr, and nothing run)."""
    global OPTIONS_IN_USE
    OPTIONS_IN_USE = None  # a run uses only the settings set it names
    args = list(argv)
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
    runs = {"steps": steps_main, "small": small_main, "memory": memory_main}
    if args[:1] == ["small"]:
        return asyncio.run(small_main(use_gate="--gate" in args))
    return asyncio.run(runs[args[0]]() if args and args[0] in runs else main())


if __name__ == "__main__":
    # a reason can carry characters Windows' console code page cannot print (2026-10-30: U+2011)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(cli(sys.argv[1:]))
