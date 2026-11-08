"""Steward's outside eval sets (tier ext): pinned public benchmarks, for calibration only, never a gate.

Their cases may already be in a model's training data (the set files say so), so a score here is a reading against
the field, not a bar a change must meet. Two runners, each reading a snapshot pinned once in harness/steward/evals/data/
(RULE 4: nothing downloads at first use; each set file names its source repository, commit, license and attribution):

* ``bfcl``: the Berkeley Function Calling Leaderboard (ShishirPatil/gorilla, Apache-2.0), its Python AST categories
  (simple, multiple, parallel, parallel_multiple) and irrelevance. Each case's function specs are offered to a bare
  MAF Agent on Steward's model (OllamaChatClient, OLLAMA_MODEL) as declaration-only tools (MAF's FunctionTool with
  func=None: the run stops on the calls and returns them, nothing runs), with no Estate tool and no instructions.
  MAF's evaluate_agent scores the calls against the case's possible answers (its expected_output) with bfcl_ast_match,
  or no_tool_called for irrelevance.
* ``exercises``: the Aider polyglot benchmark's Python exercises (Exercism's Python track, MIT). Each case copies the
  exercise's stub, tests and instructions into a throwaway folder in the working area (EXERCISE_WORK, gitignored), runs
  Steward's normal workflow on it as the asks runner does (evals.run_case: the plan and the writes approved, the shell
  only for pytest on that folder, every other card denied), then runs the PINNED test file against the stub the run
  left, with a hard timeout (exercise_tests_pass). The folder is removed after each case. No Docker (his rule).

evals.py reads the set files (load_eval_set: an ext runner's cases are {id, checks}, its set has a ``source``) and runs
them (``evals.py bfcl`` / ``evals.py aider-py``); this module holds what is the ext sets' own. It imports nothing from
evals.py: the runners are handed evals.py's module (``host``) for its run_case, history and report.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agent_framework import Agent, AgentResponse, FunctionTool, LocalEvaluator, Message, evaluate_agent, evaluator

EVALS_DIR = Path(__file__).resolve().parents[1] / "evals"
_REPO = Path(__file__).resolve().parents[3]
EXT_RUNNERS = ("bfcl", "exercises")
_CASE_KEYS = {"id", "checks"}
_SOURCE_KEYS = {"data", "repo", "commit", "license", "attribution", "contamination"}


def data_folder(source: dict[str, Any]) -> Path:
    """A set's pinned data folder (its source's data, relative to harness/steward/evals/)."""
    return EVALS_DIR / source["data"]


def data_fingerprint(folder: Path) -> str:
    """The sha256 of every file under a pinned data folder (paths and contents, CRLF read as LF so a Windows checkout
    and GitHub's agree; the files in order of their "/"-separated names, which Windows' case-blind Path order is not):
    a change to the snapshot is a new set version, as a change to a case is."""
    digest = hashlib.sha256()
    files = {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    for name in sorted(files):
        path = files[name]
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def schema_problems(raw: dict[str, Any]) -> list[str]:
    """What is wrong with an ext runner's set beyond the common keys evals.py checks: the tier, the source (every key,
    its data folder and that folder's LICENSE), and each case ({id, checks}: an id in the pinned data, used once, and
    the runner's own checks)."""
    runner, problems = raw["runner"], []
    if raw["tier"] != "ext":
        problems.append(f"runner {runner} is for an outside set: its tier is ext, not {raw['tier']!r}")
    source = raw.get("source")
    if not (isinstance(source, dict) and set(source) == _SOURCE_KEYS and all(isinstance(v, str) and v.strip() for v in source.values())):
        return [*problems, f"source is not {{{', '.join(sorted(_SOURCE_KEYS))}}}, each text"]
    folder = data_folder(source)
    if not folder.is_dir():
        return [*problems, f"source data {source['data']!r} is not a folder in harness/steward/evals/"]
    if not (folder / "LICENSE").is_file():
        problems.append(f"source data {source['data']!r} has no LICENSE file")
    known = pinned_ids(runner, folder)
    checks = BFCL_CHECKS if runner == "bfcl" else EXERCISE_CHECKS
    seen: set[str] = set()
    for n, case in enumerate(raw["cases"], 1):
        if not (isinstance(case, dict) and set(case) == _CASE_KEYS):
            problems.append(f"case {n} is not {{id, checks}}")
            continue
        where = f"case {case['id']!r}"
        if case["id"] in seen:
            problems.append(f"{where}: the id is used twice")
        seen.add(case["id"])
        if case["id"] not in known:
            problems.append(f"{where}: not in the pinned data {source['data']}")
        if not (isinstance(case["checks"], list) and len(case["checks"]) == 1 and case["checks"][0] in checks):
            problems.append(f"{where}: checks is not one of the {runner} runner's {list(checks)}")
        elif runner == "bfcl" and case["id"] in known:
            want = "no_tool_called" if known[case["id"]] == "irrelevance" else "bfcl_ast_match"
            if case["checks"][0] != want:
                problems.append(f"{where}: {known[case['id']]} cases are scored by {want}")
    return problems


def pinned_ids(runner: str, folder: Path) -> dict[str, str]:
    """The case ids the pinned data holds, each with its category (bfcl) or its exercise name (exercises)."""
    if runner == "bfcl":
        try:
            return {cid: row["category"] for cid, row in load_bfcl(folder).items()}
        except (OSError, ValueError, KeyError):
            return {}
    exercises = folder / "exercises"
    return {p.name: p.name for p in exercises.iterdir() if p.is_dir()} if exercises.is_dir() else {}


def case_ask(runner: str, source: dict[str, Any], case_id: str) -> str:
    """A case's ask: the BFCL question as its user wrote it, or the exercise ask (exercise_ask)."""
    if runner == "bfcl":
        row = load_bfcl(data_folder(source))[case_id]
        return "\n".join(m["content"] for m in row["question"][0] if m["role"] == "user")
    return exercise_ask(case_id)


def set_fingerprint(raw: dict[str, Any]) -> str:
    """An ext set's fingerprint: its cases and its source, and the pinned data's own (data_fingerprint)."""
    cases = {"cases": raw["cases"], "source": raw["source"], "data": data_fingerprint(data_folder(raw["source"]))}
    return hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------------------------- BFCL

BFCL_CATEGORIES = ("simple_python", "multiple", "parallel", "parallel_multiple", "irrelevance")
BFCL_CHECKS = ("bfcl_ast_match", "no_tool_called")


@functools.lru_cache(maxsize=4)
def load_bfcl(folder: Path) -> dict[str, dict[str, Any]]:
    """The pinned BFCL cases by id, each with its possible answer (ground_truth: a list of {function: {param:
    [acceptable values]}}; empty for irrelevance). Read once per folder."""
    def rows(name: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in (folder / name).read_text(encoding="utf-8").splitlines() if line.strip()]

    answers = {row["id"]: row["ground_truth"] for row in rows("possible_answers.jsonl")}
    return {row["id"]: {**row, "ground_truth": answers.get(row["id"], [])} for row in rows("cases.jsonl")}


def bfcl_tool_name(name: str) -> str:
    """A BFCL function name as a tool name the chat API takes ("math.factorial" -> "math_factorial"), as BFCL's own
    function-calling handlers rename them."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


_BFCL_TYPES = {"dict": "object", "float": "number", "tuple": "array", "any": None}


def bfcl_json_schema(spec: Any) -> Any:
    """A BFCL parameter spec as JSON Schema (its Python type names mapped: dict, float, tuple; "any" left untyped)."""
    if isinstance(spec, dict):
        out: dict[str, Any] = {}
        for key, value in spec.items():
            if key == "type" and isinstance(value, str):
                if (mapped := _BFCL_TYPES.get(value, value)) is not None:
                    out[key] = mapped
            else:
                out[key] = bfcl_json_schema(value)
        return out
    if isinstance(spec, list):
        return [bfcl_json_schema(value) for value in spec]
    return spec


def bfcl_tools(functions: list[dict[str, Any]]) -> list[FunctionTool]:
    """A case's function specs as declaration-only tools (MAF's FunctionTool with func=None): the model may call them,
    and MAF returns the calls to the caller without running anything."""
    return [
        FunctionTool(
            name=bfcl_tool_name(spec["name"]), description=spec.get("description", ""), func=None,
            input_model=bfcl_json_schema(spec.get("parameters") or {"type": "dict", "properties": {}}),
        )
        for spec in functions
    ]


def bfcl_expected(case: dict[str, Any]) -> str:
    """What a case's evaluators compare against, as MAF's expected_output (text): its category, its possible answers
    and its functions' required parameters, by tool name."""
    return json.dumps(
        {
            "category": case["category"],
            "ground_truth": [
                {bfcl_tool_name(name): params for name, params in call.items()} for call in case["ground_truth"]
            ],
            "required": {
                bfcl_tool_name(spec["name"]): list((spec.get("parameters") or {}).get("required", []))
                for spec in case["function"]
            },
        },
        ensure_ascii=False,
    )


def _calls(conversation: list[Any]) -> list[tuple[str, dict[str, Any] | None]]:
    """Every function call in the run, with its arguments parsed (None when they are not a JSON object)."""
    calls: list[tuple[str, dict[str, Any] | None]] = []
    for message in conversation or []:
        for content in getattr(message, "contents", None) or []:
            if content.type != "function_call" or not content.name:
                continue
            args = content.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except ValueError:
                    args = None
            calls.append((content.name, dict(args) if isinstance(args, dict) else None if args is not None else {}))
    return calls


_STRIP = re.compile(r"[ ,./\-_*^]")


def _norm(text: str) -> str:
    """A string compared as BFCL's AST checker compares it: case, spaces and , . / - _ * ^ ignored, ' read as "."""
    return _STRIP.sub("", text.replace("'", '"')).lower()


def bfcl_value_matches(value: Any, expected: Any) -> bool:
    """Whether one argument value is one acceptable value: strings normalized (_norm), an int accepted for a float,
    lists in order, dicts key by key (each key's value one of its acceptable values; "" means it may be left out)."""
    if isinstance(expected, bool) or isinstance(value, bool):
        return isinstance(expected, bool) and isinstance(value, bool) and value == expected
    if isinstance(expected, str):
        return isinstance(value, str) and _norm(value) == _norm(expected)
    if isinstance(expected, (int, float)):
        if not isinstance(value, (int, float)):
            return False
        if isinstance(expected, int) and isinstance(value, float) and not value.is_integer():
            return False
        return float(value) == float(expected)
    if isinstance(expected, list):
        return isinstance(value, (list, tuple)) and len(value) == len(expected) and all(
            bfcl_value_matches(v, e) for v, e in zip(value, expected)
        )
    if isinstance(expected, dict):
        if not isinstance(value, dict) or set(value) - set(expected):
            return False
        for key, acceptable in expected.items():
            options = acceptable if isinstance(acceptable, list) else [acceptable]
            if key not in value:
                if "" not in options:
                    return False
            elif not any(bfcl_value_matches(value[key], option) for option in options if option != ""):
                return False
        return True
    return value == expected


def bfcl_call_problem(
    name: str, args: dict[str, Any] | None, answer: dict[str, dict[str, list[Any]]], required: dict[str, list[str]]
) -> str | None:
    """Why one call is not the answer's one call (None: it is): the function, its required parameters, no parameter
    the answer has not, and each value among its acceptable values ("" acceptable: it may be left out)."""
    (want, params), = answer.items()
    if name != want:
        return f"called {name}, not {want}"
    if args is None:
        return f"{name}'s arguments are not a JSON object"
    if missing := [p for p in required.get(name, []) if p not in args]:
        return f"{name} is missing required {missing}"
    if extra := sorted(set(args) - set(params)):
        return f"{name} was given {extra}, which the answer does not have"
    for param, acceptable in params.items():
        if param not in args:
            if "" not in acceptable:
                return f"{name} left out {param}"
        elif not any(bfcl_value_matches(args[param], option) for option in acceptable if option != ""):
            return f"{name}({param}={args[param]!r}) is not one of {acceptable}"
    return None


def bfcl_match_problem(calls: list[tuple[str, dict[str, Any] | None]], expected: dict[str, Any]) -> str | None:
    """Why a case's calls are not its answer (None: they are). simple and multiple: exactly one call, the answer's.
    parallel and parallel_multiple: as many calls as the answer has, each matched to a different one in any order."""
    answers, required = expected["ground_truth"], expected["required"]
    if not calls:
        return "no function was called"
    if len(calls) != len(answers):
        return f"{len(calls)} call(s) ({[n for n, _ in calls]}), the answer has {len(answers)}"
    if len(answers) == 1:
        return bfcl_call_problem(calls[0][0], calls[0][1], answers[0], required)

    def match(i: int, free: frozenset[int]) -> bool:
        if i == len(calls):
            return True
        return any(
            bfcl_call_problem(calls[i][0], calls[i][1], answers[j], required) is None and match(i + 1, free - {j})
            for j in free
        )

    if match(0, frozenset(range(len(answers)))):
        return None
    first = next(
        (p for name, args in calls if all(p := bfcl_call_problem(name, args, a, required) for a in answers)), None
    )
    return f"the calls do not match the answer one to one: {first or 'each matches, but not each a different one'}"


@evaluator(name="bfcl_ast_match")
def bfcl_ast_match(conversation: list[Any], expected_output: str) -> dict[str, object]:
    """BFCL's AST check: the first turn's calls are the possible answer (bfcl_match_problem); irrelevance is
    no_tool_called's."""
    expected = json.loads(expected_output)
    if expected["category"] == "irrelevance":
        return {"passed": True, "reason": "Not this case."}
    problem = bfcl_match_problem(_calls(conversation), expected)
    return {"passed": problem is None, "reason": problem or f"{len(expected['ground_truth'])} call(s) match the answer."}


@evaluator(name="no_tool_called")
def no_tool_called(conversation: list[Any], expected_output: str) -> dict[str, object]:
    """BFCL's irrelevance check: none of the offered functions fits, so none is called."""
    if json.loads(expected_output)["category"] != "irrelevance":
        return {"passed": True, "reason": "Not this case."}
    calls = [name for name, _ in _calls(conversation)]
    return {"passed": not calls, "reason": f"called {calls}" if calls else "No function was called."}




async def run_bfcl(eval_set: Any, host: Any, client: Any = None) -> tuple[list[Any], list[str], list[str]]:
    """Each case's question to a bare MAF Agent on Steward's model with the case's functions as declaration-only tools
    (bfcl_tools), num_repetitions times; the responses, their asks and their expected outputs (bfcl_expected), in
    order. A run that raises (an Exception) is recorded in host.CASE_ERRORS and fails with host.run_completed."""
    if client is None:
        from agent_framework.ollama import OllamaChatClient  # noqa: PLC0415 - Steward's model, OLLAMA_MODEL

        client = OllamaChatClient()
    rows = load_bfcl(data_folder(eval_set.source))
    responses: list[Any] = []
    asks: list[str] = []
    expected: list[str] = []
    for _ in range(eval_set.num_repetitions):
        for case in eval_set.cases:
            row = rows[case.id]
            agent = Agent(client=client, name="bfcl", tools=bfcl_tools(row["function"]))
            host.CASE_ERRORS.pop(case.ask, None)
            with host.case_logs() as logs:
                try:
                    response = await agent.run(case.ask)
                except Exception as error:  # the case fails with its reason (run_completed); the set goes on
                    host.CASE_ERRORS[case.ask] = host.raised(error)
                    response = AgentResponse(messages=[])
            # its transcript (evals.keep_case_transcript): the ask's message, then the run's
            messages = [Message(role="user", contents=[case.ask]), *response.messages]
            host.keep_case_transcript(eval_set.name, case.ask, host.message_records(messages), logs=logs, case_id=case.id)
            responses.append(response)
            asks.append(case.ask)
            expected.append(bfcl_expected(row))
    return responses, asks, expected


async def score_bfcl(eval_set: Any, host: Any, responses: list[Any], asks: list[str], expected: list[str]) -> Any:
    """The BFCL checks on each run (MAF's evaluate_agent, the responses given): one result, an item per run, named
    <set>@v<version>."""
    results = await evaluate_agent(
        queries=asks,
        responses=responses,
        expected_output=expected,
        evaluators=LocalEvaluator(bfcl_ast_match, no_tool_called, host.run_completed),
        eval_name=eval_set.eval_name,
        conversation_split=host.SPLITS[eval_set.split],
    )
    return results[0]


# ----------------------------------------------------------------------------------------------------------- exercises

EXERCISE_CHECKS = ("exercise_tests_pass",)
# The throwaway folder each exercise case is copied into and removed from: in the working area, so his file tools
# reach it and his CHECK step runs its pytest; gitignored, so a run stopped part-way leaves nothing a commit carries.
EXERCISE_WORK = "harness/steward/working/ext-aider-py"
EXERCISE_TIMEOUT = 60  # seconds for one exercise's tests, the run's result check
# Each case's measured result, by its ask, taken before its folder is removed: {ask: (passed, reason)}.
EXERCISE_RESULTS: dict[str, tuple[bool, str]] = {}


def exercise_files(name: str) -> tuple[str, str]:
    """An exercise's stub and test file names (bowling: bowling.py, bowling_test.py)."""
    module = name.replace("-", "_")
    return f"{module}.py", f"{module}_test.py"


def exercise_ask(name: str) -> str:
    """The ask for one exercise, after the Aider benchmark's own prompt: the instructions, the file to change, the
    names kept, the standard library only, and the tests left as they are."""
    stub, test = exercise_files(name)
    return (
        f"Solve the exercise in {EXERCISE_WORK}/{name}: read its instructions.md, then implement {stub} there so that "
        f"every test in {test} passes. Keep the names of the existing functions and classes, use only the Python "
        f"standard library, and do not change {test}."
    )


def exercise_copied(data: Path, name: str, folder: Path) -> None:
    """The pinned exercise (stub, tests, instructions) copied into a fresh folder."""
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(data / "exercises" / name, folder, ignore=shutil.ignore_patterns("__pycache__"))


def exercise_tests_result(data: Path, name: str, folder: Path, timeout: int = EXERCISE_TIMEOUT) -> tuple[bool, str]:
    """The PINNED test file run against the stub in ``folder`` (python -m unittest, in a fresh temp folder holding
    the two files only, with a hard timeout): passed only when every test passes. A run that changed the test file
    in its copy changes nothing here."""
    stub, test = exercise_files(name)
    if not (folder / stub).is_file():
        return False, f"{stub} is not there"
    with tempfile.TemporaryDirectory() as scratch:
        shutil.copyfile(folder / stub, Path(scratch) / stub)
        shutil.copyfile(data / "exercises" / name / test, Path(scratch) / test)
        try:
            done = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "-q", test.removesuffix(".py")], cwd=scratch,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"{test} did not finish in {timeout} s"
    tail = [line for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    summary = " ".join(tail[-2:]) if tail else f"exit {done.returncode}"
    return done.returncode == 0, f"{test}: {summary}"


@evaluator(name="exercise_tests_pass")
def exercise_tests_pass(query: str) -> dict[str, object]:
    """The exercise's pinned tests pass on what the run left (EXERCISE_RESULTS, measured before its folder went)."""
    if query not in EXERCISE_RESULTS:
        return {"passed": False, "reason": "The exercise's tests were not run."}
    passed, reason = EXERCISE_RESULTS[query]
    return {"passed": passed, "reason": reason}


def exercise_precondition_problems(eval_set: Any) -> list[str]:
    """Each exercise's pinned tests must FAIL on its pinned stub, as an asks case's precondition must on its fixture."""
    data = data_folder(eval_set.source)
    problems = []
    for case in eval_set.cases:
        passed, reason = exercise_tests_result(data, case.id, data / "exercises" / case.id)
        if passed:
            problems.append(f"{eval_set.path.name}: case {case.id!r}: its tests already pass on the stub ({reason})")
    return problems


async def run_exercises(eval_set: Any, host: Any, **build: Any) -> tuple[Any, list[Any], list[str]]:
    """Each exercise once (num_repetitions times) through Steward's workflow (host.run_case) on its throwaway copy,
    then its pinned tests measured (EXERCISE_RESULTS) and the copy removed, with any untracked file the run left
    elsewhere (host.remove_new_untracked); Steward, the responses and their asks, in order. The writes are approved;
    a shell card only for pytest on the copy (host.card_approved); git_commit and everything else denied."""
    from agent_framework import FileAccessProvider  # noqa: PLC0415

    build.setdefault("auto_approve_skill_scripts", True)
    approve = set(FileAccessProvider._WRITE_TOOL_NAMES)  # noqa: SLF001
    data = data_folder(eval_set.source)
    work = _REPO / EXERCISE_WORK
    untracked_before = host.untracked_files()
    EXERCISE_RESULTS.clear()
    steward, responses, asks = None, [], []
    try:
        for _ in range(eval_set.num_repetitions):
            for case in eval_set.cases:
                folder = work / case.id
                try:
                    exercise_copied(data, case.id, folder)
                    ran, response = await host.run_case(case.ask, approve, **build)  # a raising run is a failed case
                    steward = ran or steward
                    EXERCISE_RESULTS[case.ask] = exercise_tests_result(data, case.id, folder)
                finally:
                    shutil.rmtree(folder, ignore_errors=True)
                    host.remove_new_untracked(untracked_before)
                responses.append(response)
                asks.append(case.ask)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return steward, responses, asks


async def ext_main(eval_set: Any, host: Any) -> int:
    """An ext set run once (each case num_repetitions times), scored by MAF's evaluate_agent under <set>@v<version>,
    reported as an asks set is, and recorded in the history under the set's name; the exit code is host.exit_code's
    (an ext set is calibration: nothing gates on it)."""
    host.load_dotenv()
    host.configure_otel_providers(exporters=[host.HaloJsonlSpanExporter()], enable_sensitive_data=True)
    if eval_set.runner == "bfcl":
        responses, asks, expected = await run_bfcl(eval_set, host)
        result = await score_bfcl(eval_set, host, responses, asks, expected)
    else:
        steward, responses, asks = await run_exercises(eval_set, host)
        result = (
            await evaluate_agent(
                agent=steward, queries=asks, responses=responses,
                evaluators=LocalEvaluator(exercise_tests_pass, host.run_completed),
                eval_name=eval_set.eval_name, conversation_split=host.SPLITS[eval_set.split],
            )
        )[0]
    host.print_asks_report(f"{eval_set.tier} {eval_set.eval_name}", "Checks", result)
    code = host.exit_code([result])
    host.record_history(eval_set.name, {"": result}, code)
    return code


EXT_EVALUATORS = (bfcl_ast_match, no_tool_called, exercise_tests_pass)
