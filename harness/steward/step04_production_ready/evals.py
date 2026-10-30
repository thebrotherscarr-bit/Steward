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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402
from halo_traces import HaloJsonlSpanExporter  # noqa: E402

STEWARD_EVAL_QUERIES = [
    "Use get_repo_status and tell me which git branch the workspace is on.",
    "Map sample-project with the codebase-map skill. Which file is the module and which is the test file?",
    "Read sample-project/inventory.py and sample-project/test_inventory.py and explain why "
    "test_percent_discount fails. Don't change any files.",
    # MAF improvement-loop regression cases (layer per MAF's evaluation reference)
    "Map this codebase.",  # case 2: instructions / skill
    "What percentage of sample-project's lines are tests?",  # case 3: tool selection
    "Research Microsoft Agent Framework, Ollama and mem0 and summarize the latest news.",  # case 1: tool selection
    "Explore sample-project with the CodeExplorer agent and summarize it.",  # case 4: output contract
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
    passed = "main" in response.lower()
    return {"passed": passed, "reason": "Names the main branch." if passed else response[:160]}


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
    if query != "Map this codebase.":
        return {"passed": True, "reason": "Not the map case."}
    text = response.lower()
    found = [name for name in ("inventory.py", "test_inventory.py") if name in text]
    return {"passed": len(found) == 2, "reason": f"Found files: {found}."}


@evaluator(name="test_share_counted")
def test_share_counted(query: str, response: str) -> dict[str, object]:
    """Case 3: the share is counted, not estimated: 24 of 45 lines, 53.3% (Kyle's count, Part 3)."""
    if "percentage" not in query.lower():
        return {"passed": True, "reason": "Not the line-count case."}
    passed = "53.3" in response
    return {"passed": passed, "reason": "Reports 53.3%." if passed else response[:160]}


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


async def _run_queries(agent: Agent[Any], queries: list[str]) -> list[AgentResponse[Any]]:
    """Run each query on its own fresh session (the harness's approval middleware needs a session)."""
    responses: list[AgentResponse[Any]] = []
    for query in queries:
        responses.append(await agent.run(query, session=agent.create_session()))
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
            responses = await _run_queries(agent, STEWARD_EVAL_QUERIES)
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


if __name__ == "__main__":
    # a reason can carry characters Windows' console code page cannot print (2026-10-30: U+2011)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
