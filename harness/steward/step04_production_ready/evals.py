"""Local evals for the production-ready Steward (Step 4).

Follows the guide's ``evals.py``: run fixed queries (one fresh session each) and score the answers
with local evaluators. Foundry evaluators are left out: they need Microsoft Foundry. Every span goes
to halo_traces/traces.jsonl, as in console_app.py, and a failed check prints its reason.

The shell is disabled and skill scripts are auto-approved for this unattended run, so no query
stops on an approval prompt. Nothing here writes files or commits.

The last four queries are regression cases from MAF's improvement loop (Kyle, 2026-10-30, the plan
"fix Steward's four failures with MAF's improvement loop"): each is a failure the improvement loop's
eval gate and Kyle's Part 3 verdicts found, checked with MAF's own tool_call_args_match (the tools
Steward must call) beside a check of the answer. A case stays here once it passes.

Run:
    python harness/steward/step04_production_ready/evals.py
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
from contextlib import AsyncExitStack, contextmanager
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentResponse,
    ConversationSplit,
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
from agent import build_steward_agent  # noqa: E402
from halo_traces import HaloJsonlSpanExporter  # noqa: E402

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


# Plan before act (Kyle, 2026-11-01: "follow the rules"; the guide's plan mode, and the cookbook: "A short plan
# shown before acting", "State a tool policy inside the instructions"). Each query asks for a change. Run as
# the live host runs him (hosted.py's plan_mode_turns: PlanningResponse in plan mode, as the guide's console),
# the run must add todos (none marked done), change nothing, not leave plan mode itself, and end with the
# guide's PlanningResponse: an approval holding the plan, or a clarification. Run alone: python evals.py plan.
# The gate is the cookbook's 0.8.
PLAN_BEFORE_ACT_QUERIES = [
    'Write a file working/plan-check.txt that says "plan mode works".',
    "Fix the bug that makes test_percent_discount fail in harness/steward/working/sample-project.",
    "Add a docstring to order_total in harness/steward/working/sample-project/inventory.py.",
    'Commit the current work with the message "checkpoint".',
    "Create a README.md in harness/steward/working/sample-project that describes the project.",
]
PLAN_GATE = 0.8
# What each plan must name, read from its todos and its PlanningResponse (the cookbook: "Validators should check the
# artefacts themselves"). Run 15: the bug-fix plan passed the gate while planning a new inventory.py instead of the
# discount line, because nothing checked what the plan said (and the bug was not planted for that run).
PLAN_MUST_NAME: dict[str, tuple[str, ...]] = {
    PLAN_BEFORE_ACT_QUERIES[0]: ("plan-check.txt",),
    PLAN_BEFORE_ACT_QUERIES[1]: ("inventory.py", "discount"),
    PLAN_BEFORE_ACT_QUERIES[2]: ("order_total", "docstring"),
    PLAN_BEFORE_ACT_QUERIES[3]: ("checkpoint",),
    PLAN_BEFORE_ACT_QUERIES[4]: ("readme",),
}


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


def _tool_errors(conversation: list[Any]) -> list[str]:
    """Tool results that came back as errors."""
    errors: list[str] = []
    for message in conversation or []:
        for content in getattr(message, "contents", None) or []:
            if content.type == "function_result" and getattr(content, "exception", None) is not None:
                errors.append(str(content.exception)[:120])
    return errors


@evaluator(name="plan_before_act")
def plan_before_act(query: str, response: str, conversation: list[Any]) -> dict[str, object]:
    """The artefacts of planning first (the cookbook: "Validators should check the artefacts themselves"):
    nothing changed or put on a card, todos added and none marked done, still in plan mode, and the guide's
    PlanningResponse. A change the plan-mode gate refused is the harness working, reported, not failed."""
    from agent import _CHANGES_THINGS  # noqa: PLC0415
    from hosted import planning_response_in  # noqa: PLC0415

    calls = _calls_in_order(conversation)
    names = [name for name, _, _ in calls]
    acted = [f"{name} ({outcome})" for name, _, outcome in calls if name in _CHANGES_THINGS and outcome != "refused"]
    if acted:
        return {"passed": False, "reason": f"Changed things before the plan's approval: {acted}. Calls: {names[:14]}"}
    left = [args for name, args, _ in calls if name == "mode_set" and str((args or {}).get("mode", "")).lower() != "plan"]
    if left:
        return {"passed": False, "reason": f"Left plan mode without the user: mode_set{left}."}
    todos = [args for name, args, _ in calls if name == "todos_add" and (args or {}).get("todos")]
    errors = _tool_errors(conversation)
    if not todos:
        return {"passed": False, "reason": f"No todos added. Calls: {names[:14]}. Errors: {errors[:3]}"}
    if any(name == "todos_complete" and outcome == "ran" for name, _, outcome in calls):
        return {"passed": False, "reason": f"Marked a todo done before anything ran. Calls: {names[:14]}"}
    # The guide's console parses only the last model call's text as the PlanningResponse ("a single agent run
    # may produce multiple model invocations ... only the final response's text is retained for JSON parsing",
    # harness/console/observers/planning_output.py), and the JSON is read in code (hosted.planning_response_in).
    last = next(
        (m.text for m in reversed(conversation or []) if getattr(m, "role", None) == "assistant" and (m.text or "").strip()),
        response,
    )
    plan = planning_response_in(last)
    if plan is None:
        return {"passed": False, "reason": f"Last reply is not a PlanningResponse: {last[:160]!r}"}
    if not plan.questions:
        return {"passed": False, "reason": f"A {plan.type.value} with no content."}
    said = " ".join(
        [str(todo) for args in todos for todo in args.get("todos") or []] + [q.message for q in plan.questions]
    ).lower()
    missing = [term for term in PLAN_MUST_NAME.get(query, ()) if term not in said]
    if missing:
        return {"passed": False, "reason": f"The plan does not name {missing}: todos {todos[0]}, plan {plan.questions[0].message[:120]!r}"}
    refusals = [name for name, _, outcome in calls if outcome == "refused"]
    note = f" (the gate refused {refusals} first)" if refusals else ""
    return {"passed": True, "reason": f"Todos {todos[0]}, then a {plan.type.value}{note}: {plan.questions[0].message[:90]!r}"}


async def _run_queries(agent: Agent[Any], queries: list[str], *, mode: str | None = None) -> list[AgentResponse[Any]]:
    """Run each query on its own fresh session (the harness's approval middleware needs a session).

    Streamed, so each response holds every round of the run: MAF's ToolApprovalMiddleware keeps the
    auto-approved rounds on its streaming path and returns only the last round otherwise
    (_harness/_tool_approval.py), and MAF's tool checks read the response (2026-10-30: a
    non-streaming run reported load_skill "not called" though the trace shows it).

    ``mode`` puts each session in that mode first, as the application does (MAF's set_agent_mode). The
    regression cases run as approved work, in execute mode (2026-11-01: sessions start in plan mode, and
    plan mode plans first; the plan-before-act cases check that).
    """
    from agent_framework import AgentModeProvider, set_agent_mode  # noqa: PLC0415

    modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
    responses: list[AgentResponse[Any]] = []
    for query in queries:
        session = agent.create_session()
        if mode:
            set_agent_mode(session, mode, source_id=modes.source_id, available_modes=modes.available_modes)
        # Every iteration's updates: the harness loop streams each iteration, and get_final_response() keeps only
        # the last (2026-11-01: a CodeExplorer delegation in the first iteration was scored "not called").
        updates = [update async for update in agent.run(query, session=session, stream=True)]
        responses.append(AgentResponse.from_updates(updates))
    return responses


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


async def main() -> None:
    """Run the local Steward evals."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    async with AsyncExitStack() as stack:
        agent = await build_steward_agent(stack, enable_shell=False, auto_approve_skill_scripts=True)
        async with agent:
            local = LocalEvaluator(
                repo_status_grounded,
                codebase_map_names_files,
                bug_diagnosis,
                map_names_files,
                test_share_counted,
                research_covers_topics,
                explorer_names_files,
                tool_call_args_match,
            )
            with discount_bug_planted():
                responses = await _run_queries(agent, STEWARD_EVAL_QUERIES, mode="execute")
            results = await evaluate_agent(
                agent=agent,
                queries=STEWARD_EVAL_QUERIES,
                responses=responses,
                expected_tool_calls=STEWARD_EXPECTED_TOOL_CALLS,
                evaluators=local,
                # The question is the first user message and the answer every iteration after it: the loop's
                # nudges are user messages, and the default (the last turn) scored a nudge and the last iteration.
                conversation_split=ConversationSplit.FULL,
            )
            print(f"Local evals: {results[0].passed}/{results[0].total} passed")
            for item in results[0].items:
                print(f"  [{item.status}] {(item.input_text or '')[:70]}")
                for score in item.scores:
                    if score.passed is False:
                        print(f"      {score.name}: {(score.sample or {}).get('reason', '')}")


async def plan_main() -> None:
    """The plan-before-act cases alone, against the cookbook's 0.8 gate."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    async with AsyncExitStack() as stack:
        # as the live host runs him: the guide's PlanningResponse in plan mode (hosted.py)
        from agent_framework import AgentModeProvider  # noqa: PLC0415
        from hosted import plan_mode_turns, planning_response_in  # noqa: PLC0415

        agent = await build_steward_agent(
            stack, enable_shell=False, auto_approve_skill_scripts=True, plan_reply_check=planning_response_in
        )

        mode_provider = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
        agent.middleware = [plan_mode_turns(mode_provider), *(agent.middleware or [])]
        async with agent:
            # The bug-fix case needs the bug there to plan its fix (run 15 planned against fixed code).
            with discount_bug_planted():
                responses = await _run_queries(agent, PLAN_BEFORE_ACT_QUERIES)
            results = await evaluate_agent(
                agent=agent,
                queries=PLAN_BEFORE_ACT_QUERIES,
                responses=responses,
                evaluators=LocalEvaluator(plan_before_act),
                conversation_split=ConversationSplit.FULL,
            )
    result = results[0]
    rate = result.passed / result.total if result.total else 0.0
    print(f"Plan before act: {result.passed}/{result.total} passed ({rate:.0%}); gate {PLAN_GATE:.0%}: "
          f"{'PASS' if rate >= PLAN_GATE else 'FAIL'}")
    for item in result.items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            print(f"      {score.name}: {(score.sample or {}).get('reason', '')}")


# The whole round (Part 1, "How plan mode works"): a request planned in plan mode, the user's Approve switches the
# session to execute mode (hosted.py's agent_mode metadata, as the console's Approve calls set_agent_mode), the
# work runs with its todos ticked off, and the harness returns him to plan mode (ReturnToPlanWhenDone). No write is
# involved, so no card waits on a user. Run alone: python evals.py roundtrip.
ROUND_TRIP_QUERY = "How many lines does harness/steward/working/sample-project/inventory.py have?"
ROUND_TRIP_APPROVE = "Approve and switch to execute mode"


async def round_trip_main() -> None:
    """One request through plan, Approve, execute and back to plan, checked on the session's own state."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    from agent import _WORKING_DIR  # noqa: PLC0415
    from agent_framework import AgentModeProvider, TodoProvider, get_agent_mode, set_agent_mode  # noqa: PLC0415
    from hosted import plan_mode_turns, planning_response_in  # noqa: PLC0415

    module = _WORKING_DIR / "harness" / "steward" / "working" / "sample-project" / "inventory.py"
    expected = str(len(module.read_text(encoding="utf-8").splitlines()))
    failures: list[str] = []
    async with AsyncExitStack() as stack:
        agent = await build_steward_agent(
            stack, enable_shell=False, auto_approve_skill_scripts=True, plan_reply_check=planning_response_in
        )
        modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
        todos = next(p for p in agent.context_providers if isinstance(p, TodoProvider))
        agent.middleware = [plan_mode_turns(modes), *(agent.middleware or [])]
        mode_args = {"source_id": modes.source_id, "available_modes": modes.available_modes}
        async with agent:
            session = agent.create_session()
            planned = AgentResponse.from_updates(
                [u async for u in agent.run(ROUND_TRIP_QUERY, session=session, stream=True)]
            )
            last = next((m.text for m in reversed(planned.messages) if m.role == "assistant" and (m.text or "").strip()), "")
            if planning_response_in(last) is None:
                failures.append(f"Turn 1 did not end with a plan: {last[:160]!r}")
            if not await todos.store.load_items(session, source_id=todos.source_id):
                failures.append("Turn 1 added no todos.")
            set_agent_mode(session, "execute", **mode_args)  # the user's Approve
            done = AgentResponse.from_updates(
                [u async for u in agent.run(ROUND_TRIP_APPROVE, session=session, stream=True)]
            )
            called = [c.name for m in done.messages for c in m.contents if c.type == "function_call"]
            items = await todos.store.load_items(session, source_id=todos.source_id)
            if "execute_code" not in called:
                failures.append(f"Turn 2 did not count with CodeAct. Calls: {called[:14]}")
            if not items or not all(item.is_complete for item in items):
                failures.append(f"Turn 2 left todos open: {[(i.title, i.is_complete) for i in items]}")
            mode = get_agent_mode(session, default_mode=modes.default_mode, **mode_args)
            if mode != "plan":
                failures.append(f"Not returned to plan mode after the work (mode {mode}).")
            if expected not in (done.text or ""):
                failures.append(f"Expected {expected} lines: {(done.text or '')[-160:]!r}")
    print(f"Round trip: {'PASS' if not failures else 'FAIL'}")
    for failure in failures:
        print(f"  [fail] {failure}")


# The README's walkthrough steps no other eval covered (Kyle, 2026-11-01: "I want this done"), each run as approved
# work in execute mode with its cards answered the way the case says, and checked on what the run did. The bug is
# planted, so there is an uncommitted change to review and a failing test to run. Memory goes to a store that is
# deleted after the run, never his. The commit card is denied: the eval never commits. Run: python evals.py walkthrough.
WALKTHROUGH_REVIEW = "Review my uncommitted changes in harness/steward/working/sample-project."
WALKTHROUGH_TESTS = "Run the tests in harness/steward/working/sample-project."
WALKTHROUGH_REMEMBER = "I use unittest and type hints everywhere. Remember that."
WALKTHROUGH_RECALL = "Which test framework do I use, and how do I write type annotations?"
WALKTHROUGH_COMMIT = 'Commit the current work with the message "checkpoint".'
# SecondBrain is a notes repository at heart (Kyle, 2026-11-01): the case finds and reads one of his notes over MCP.
WALKTHROUGH_NOTE = (
    "Find my SecondBrain note on the plan for Steward's context, memory and cheap reads, and tell me how many "
    "approval rounds SecondBrain allows in one turn."
)
WALKTHROUGH_QUERIES = [
    WALKTHROUGH_REVIEW, WALKTHROUGH_TESTS, WALKTHROUGH_REMEMBER, WALKTHROUGH_RECALL, WALKTHROUGH_COMMIT, WALKTHROUGH_NOTE,
]
# The note, and the fact in it the answer must carry (MAX_ROUNDS = 20, read 2026-11-01).
SECONDBRAIN_NOTE_ID = "plan-steward-context-memory-reads"
WALKTHROUGH_EXPECTED_TOOL_CALLS: list[list[ExpectedToolCall]] = [
    [ExpectedToolCall("load_skill", {"skill_name": "code-review"})],
    [ExpectedToolCall("run_shell")],
    [],
    [],
    [],
    [ExpectedToolCall("secondbrain_read_note", {"id": SECONDBRAIN_NOTE_ID})],
]
# The card answers per query: the test run's shell commands are approved, every other card is denied.
_APPROVE_ON = {WALKTHROUGH_TESTS: {"run_shell"}}


def _head() -> str:
    from agent import _WORKING_DIR  # noqa: PLC0415

    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=_WORKING_DIR, capture_output=True, text=True).stdout.strip()


def _cards(conversation: list[Any]) -> list[str]:
    return [
        c.function_call.name
        for m in conversation or []
        for c in getattr(m, "contents", None) or []
        if c.type == "function_approval_request" and c.function_call is not None
    ]


def _called(conversation: list[Any]) -> list[str]:
    return [c.name for m in conversation or [] for c in getattr(m, "contents", None) or [] if c.type == "function_call"]


@evaluator(name="walkthrough")
def walkthrough(query: str, response: str, conversation: list[Any]) -> dict[str, object]:
    """Each walkthrough step's own outcome, read from the run (calls, cards, the answer) and the repository."""
    text = (response or "").lower()
    calls, cards = _called(conversation), _cards(conversation)
    if query == WALKTHROUGH_REVIEW:
        ok = "discount" in text
        return {"passed": ok, "reason": "The review names the discount change." if ok else f"Review misses the discount change: {response[:160]!r}"}
    if query == WALKTHROUGH_TESTS:
        if "run_shell" not in cards:
            return {"passed": False, "reason": f"No run_shell card. Calls: {calls[:14]}"}
        ok = "test_percent_discount" in text
        return {"passed": ok, "reason": "Ran the tests on a card and named the failing test." if ok else f"Answer misses test_percent_discount: {response[:160]!r}"}
    if query == WALKTHROUGH_REMEMBER:
        ok = any(name.startswith("file_memory_") for name in calls)
        return {"passed": ok, "reason": "Saved to file memory." if ok else f"Nothing saved to memory. Calls: {calls[:14]}"}
    if query == WALKTHROUGH_RECALL:
        ok = "unittest" in text and "type hint" in text
        return {"passed": ok, "reason": "Recalled in a new session." if ok else f"Not recalled: {response[:160]!r}"}
    if query == WALKTHROUGH_COMMIT:
        commit_cards = [name for name in cards if name.endswith("git_commit")]
        held = "atlas_git_commit" in calls
        if not commit_cards and not held:
            return {"passed": False, "reason": f"No commit card. Calls: {calls[:14]}"}
        if _head() != WALKTHROUGH_HEAD[0]:
            return {"passed": False, "reason": "HEAD moved: a commit ran."}
        how = "on Steward's card (denied)" if commit_cards else "held on SecondBrain's card (deny it there)"
        return {"passed": True, "reason": f"Commit asked for approval, {how}; nothing committed."}
    if query == WALKTHROUGH_NOTE:
        ok = "20" in text
        return {"passed": ok, "reason": "Answered 20 from the note." if ok else f"Answer misses the note's 20 rounds: {response[:160]!r}"}
    return {"passed": True, "reason": "Not a walkthrough case."}


WALKTHROUGH_HEAD: list[str] = [""]


async def _run_answering_cards(agent: Agent[Any], session: Any, query: str, approve: set[str]) -> AgentResponse[Any]:
    """A run whose approval cards are answered: approved for the tools in ``approve``, denied otherwise, as the
    console's Approve and Deny do (harness/console/observers/tool_approval.py)."""
    from agent_framework import Message  # noqa: PLC0415

    updates = [u async for u in agent.run(query, session=session, stream=True)]
    answered: set[str] = set()
    for _ in range(8):
        requests = [
            c for u in updates for c in u.contents
            if c.type == "function_approval_request" and c.function_call.call_id not in answered
        ]
        if not requests:
            break
        answered.update(request.function_call.call_id for request in requests)
        answers = [request.to_function_approval_response(approved=request.function_call.name in approve) for request in requests]
        updates += [u async for u in agent.run(Message(role="user", contents=answers), session=session, stream=True)]
    return AgentResponse.from_updates(updates)


async def walkthrough_main() -> None:
    """The walkthrough steps, scored with the walkthrough evaluator and MAF's tool_call_args_match."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    from agent import _WORKING_DIR  # noqa: PLC0415
    from agent_framework import FileSystemAgentFileStore  # noqa: PLC0415

    WALKTHROUGH_HEAD[0] = _head()
    with tempfile.TemporaryDirectory(dir=_WORKING_DIR / "storage") as memory_dir:
        async with AsyncExitStack() as stack:
            agent = await build_steward_agent(
                stack, auto_approve_skill_scripts=True, file_memory_store=FileSystemAgentFileStore(memory_dir)
            )
            async with agent:
                from agent_framework import AgentModeProvider, set_agent_mode  # noqa: PLC0415

                modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                responses: list[AgentResponse[Any]] = []
                with discount_bug_planted():
                    for query in WALKTHROUGH_QUERIES:
                        session = agent.create_session()
                        set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
                        responses.append(await _run_answering_cards(agent, session, query, _APPROVE_ON.get(query, set())))
                results = await evaluate_agent(
                    agent=agent,
                    queries=WALKTHROUGH_QUERIES,
                    responses=responses,
                    expected_tool_calls=WALKTHROUGH_EXPECTED_TOOL_CALLS,
                    evaluators=LocalEvaluator(walkthrough, tool_call_args_match),
                    conversation_split=ConversationSplit.FULL,
                )
    print(f"Walkthrough: {results[0].passed}/{results[0].total} passed")
    for item in results[0].items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            print(f"      {score.name}: {(score.sample or {}).get('reason', '')}")


# Piece 5 (Kyle's build order, 2026-11-01): the workflow's steps scored one by one on a single run. The bug is
# planted, Steward plans its fix, the plan and his writes are approved as the user would (shell commands too; any
# other card, a commit, is denied), and each step is scored on what it did: PLAN's plan, each EXECUTE turn's write,
# and overall the report's check line and the fix on disk. MAF's evaluate_workflow runs every evaluator on every
# step and takes a resumed step's query from the user's card answer (_evaluation.py), so the steps are grouped by
# their executor ids here and each group is scored by its own LocalEvaluator. Run alone: python evals.py steps.
STEPS_QUERY = PLAN_BEFORE_ACT_QUERIES[1]
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
    missing = [term for term in PLAN_MUST_NAME[STEPS_QUERY] if term not in said]
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
            name = card.data.function_call.name if card.data.function_call is not None else ""
            responses[card.request_id] = card.data.to_function_approval_response(name in approve)
        events += [e async for e in workflow.run(stream=True, responses=responses)]
    return events


async def steps_main() -> None:
    """One run of the workflow on the planted bug, each step scored by its own evaluator."""
    load_dotenv()
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)
    import steward_workflow as wf  # noqa: PLC0415
    from agent import _WORKING_DIR  # noqa: PLC0415
    from agent_framework import ConversationSplit, EvalItem, FileAccessProvider, Message  # noqa: PLC0415

    module = _WORKING_DIR / "harness" / "steward" / "working" / "sample-project" / "inventory.py"
    approve = {wf.APPROVE_PLAN, *FileAccessProvider._WRITE_TOOL_NAMES, "run_shell"}  # noqa: SLF001
    async with AsyncExitStack() as stack:
        agent = await build_steward_agent(stack, auto_approve_skill_scripts=True)
        async with agent:
            workflow = wf.build_steward_workflow(agent)
            with discount_bug_planted():
                events = await _run_workflow_answering_cards(workflow, STEPS_QUERY, approve)
                STEPS_FIXED[0] = b"discount_percent / 100" in module.read_bytes()
    steps = step_conversations(events)
    outputs = [str(e.data) for e in events if e.type == "output"]
    user = Message(role="user", contents=[STEPS_QUERY])

    def items(conversations: list[list[Any]]) -> list[Any]:
        return [EvalItem([user, *c], split_strategy=ConversationSplit.FULL) for c in conversations]

    report = [EvalItem([user, Message(role="assistant", contents=[outputs[-1] if outputs else ""])], split_strategy=ConversationSplit.FULL)]
    scored = {
        wf.PLAN_STEP: await LocalEvaluator(plan_step).evaluate(items(steps.get(wf.PLAN_STEP, [])), eval_name="plan"),
        wf.EXECUTE_STEP: await LocalEvaluator(execute_step).evaluate(items(steps.get(wf.EXECUTE_STEP, [])), eval_name="execute"),
        "overall": await LocalEvaluator(steps_overall).evaluate(report, eval_name="overall"),
    }
    passed = all(r.total and r.passed == r.total for r in scored.values())
    print(f"Workflow steps: {'PASS' if passed else 'FAIL'}")
    for step, result in scored.items():
        print(f"  {step}: {result.passed}/{result.total}")
        for item in result.items:
            for score in item.scores:
                print(f"      [{'pass' if score.passed else 'fail'}] {(score.sample or {}).get('reason', '')}")


if __name__ == "__main__":
    # a reason can carry characters Windows' console code page cannot print (2026-10-30: U+2011)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs = {"plan": plan_main, "roundtrip": round_trip_main, "walkthrough": walkthrough_main, "steps": steps_main}
    asyncio.run(runs[sys.argv[1]]() if sys.argv[1:] and sys.argv[1] in runs else main())
