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
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentResponse,
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
        stream = agent.run(query, session=session, stream=True)
        responses.append(await stream.get_final_response())
    return responses


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
            responses = await _run_queries(agent, STEWARD_EVAL_QUERIES, mode="execute")
            results = await evaluate_agent(
                agent=agent,
                queries=STEWARD_EVAL_QUERIES,
                responses=responses,
                expected_tool_calls=STEWARD_EXPECTED_TOOL_CALLS,
                evaluators=local,
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
            responses = await _run_queries(agent, PLAN_BEFORE_ACT_QUERIES)
            results = await evaluate_agent(
                agent=agent,
                queries=PLAN_BEFORE_ACT_QUERIES,
                responses=responses,
                evaluators=LocalEvaluator(plan_before_act),
            )
    result = results[0]
    rate = result.passed / result.total if result.total else 0.0
    print(f"Plan before act: {result.passed}/{result.total} passed ({rate:.0%}); gate {PLAN_GATE:.0%}: "
          f"{'PASS' if rate >= PLAN_GATE else 'FAIL'}")
    for item in result.items:
        print(f"  [{item.status}] {(item.input_text or '')[:70]}")
        for score in item.scores:
            print(f"      {score.name}: {(score.sample or {}).get('reason', '')}")


if __name__ == "__main__":
    # a reason can carry characters Windows' console code page cannot print (2026-10-30: U+2011)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(plan_main() if sys.argv[1:] == ["plan"] else main())
