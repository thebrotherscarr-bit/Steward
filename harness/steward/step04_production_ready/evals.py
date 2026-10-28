"""Local evals for the production-ready Steward (Step 4).

Follows the guide's ``evals.py``: run fixed queries (one fresh session each) and score the answers
with local evaluators. Foundry evaluators are left out: they need Microsoft Foundry.

The shell is disabled and skill scripts are auto-approved for this unattended run, so no query
stops on an approval prompt. Nothing here writes files or commits.

Run:
    python harness/steward/step04_production_ready/evals.py
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from agent_framework import Agent, AgentResponse, LocalEvaluator, evaluate_agent, evaluator
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402

STEWARD_EVAL_QUERIES = [
    "Use get_repo_status and tell me which git branch the workspace is on.",
    "Map sample-project with the codebase-map skill. Which file is the module and which is the test file?",
    "Read sample-project/inventory.py and sample-project/test_inventory.py and explain why "
    "test_percent_discount fails. Don't change any files.",
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


async def _run_queries(agent: Agent[Any], queries: list[str]) -> list[AgentResponse[Any]]:
    """Run each query on its own fresh session (the harness's approval middleware needs a session)."""
    responses: list[AgentResponse[Any]] = []
    for query in queries:
        responses.append(await agent.run(query, session=agent.create_session()))
    return responses


async def main() -> None:
    """Run the local Steward evals."""
    load_dotenv()
    async with AsyncExitStack() as stack:
        agent = await build_steward_agent(stack, enable_shell=False, auto_approve_skill_scripts=True)
        async with agent:
            local = LocalEvaluator(repo_status_grounded, codebase_map_names_files, bug_diagnosis)
            responses = await _run_queries(agent, STEWARD_EVAL_QUERIES)
            results = await evaluate_agent(
                agent=agent, queries=STEWARD_EVAL_QUERIES, responses=responses, evaluators=local
            )
            print(f"Local evals: {results[0].passed}/{results[0].total} passed")
            for item in results[0].items:
                print(f"  [{item.status}] {(item.input_text or '')[:70]}")


if __name__ == "__main__":
    asyncio.run(main())
