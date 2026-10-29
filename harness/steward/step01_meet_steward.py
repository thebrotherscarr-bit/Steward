"""Meet Steward (Step 1).

Follows Part 1 of MAF's "Build your own claw" series
(https://devblogs.microsoft.com/agent-framework/meet-your-agent-harness-and-claw), turned into a
software engineering assistant that runs on local Ollama.

``create_harness_agent`` wires up a batteries-included agent: function invocation,
per-service-call history persistence, planning (TodoProvider + AgentModeProvider) and compaction.
All we add is engineering instructions and a custom ``get_repo_status`` tool.

Changes from the guide for local Ollama:
    * ``OllamaChatClient`` replaces ``FoundryChatClient`` (model from OLLAMA_MODEL in .env).
    * Web search comes from SecondBrain's web_search and web_fetch tools (Ollama has no hosted web search).
    * Token budgets are passed so the harness compacts long sessions (Ollama context: 64k).

Environment variables:
    OLLAMA_HOST       — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL      — model name, e.g. gpt-oss:20b
    STEWARD_WORKSPACE — repo or folder Steward works in (defaults to ./working)
"""

import asyncio
from contextlib import AsyncExitStack
import os
import subprocess
import sys
from pathlib import Path

from agent_framework import create_harness_agent, MCPStreamableHTTPTool
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv

# Reuse the shared harness console that lives in the parent ``harness/`` directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from console import build_observers_with_planning, run_agent_async  # noqa: E402

load_dotenv()
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or Path(__file__).resolve().parent / "working").resolve()

STEWARD_INSTRUCTIONS = """\
## Steward: Engineering Assistant Instructions

You are Steward, a software engineering and development assistant. You help the user understand
the state of their codebase, plan engineering work, and reason about code and its design.

### Working style

- Verify facts with tools rather than relying on memory. Before answering questions about the
  repository, call get_repo_status for the current branch, uncommitted changes and recent commits.
- Be precise: name files, functions, commands and line numbers. Prefer small, verifiable steps.
- Keep the user's active projects in a memory file called projects.md: read it when asked about
  their projects, and update it whenever the user starts, finishes or describes one.
- Use secondbrain_web_search for news and anything on the web, and cite the source.

### Important

Say plainly when you don't know something or haven't verified it. Never invent file contents,
APIs or command output.
"""


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=_WORKING_DIR, capture_output=True, text=True, timeout=30)


# <get_repo_status>
def get_repo_status() -> dict[str, object]:
    """Get the git status of the workspace: branch, uncommitted changes, and the last 5 commits."""
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return {"workspace": str(_WORKING_DIR), "error": "The workspace is not inside a git repository."}
    return {
        "workspace": str(_WORKING_DIR),
        "branch": _git("branch", "--show-current").stdout.strip(),
        "changes": _git("status", "--porcelain", "--", ".").stdout.splitlines(),
        "recent_commits": _git("log", "--oneline", "-5").stdout.splitlines(),
    }


# </get_repo_status>


async def main() -> None:
    # <create_client>
    # OllamaChatClient reads OLLAMA_HOST and OLLAMA_MODEL from the environment.
    client = OllamaChatClient()
    # </create_client>

    # <create_agent>
    async with AsyncExitStack() as stack:
        tools = [get_repo_status]
        url = os.environ.get("SECONDBRAIN_MCP_URL")
        key = os.environ.get("SECONDBRAIN_MCP_KEY")
        if url and key:
            secondbrain = MCPStreamableHTTPTool(
                name="secondbrain",
                url=url,
                tool_name_prefix="secondbrain",
                static_headers={"Authorization": f"Bearer {key}"},
                allowed_tools=["web_search", "web_fetch"],
                approval_mode="never_require",
                load_prompts=False,
            )
            await stack.enter_async_context(secondbrain)
            tools.append(secondbrain)
        agent = create_harness_agent(
            client=client,
            name="Steward",
            agent_instructions=STEWARD_INSTRUCTIONS,
            tools=tools,
            max_context_window_tokens=65_536,
            max_output_tokens=8_192,
            disable_web_search=True,
        )
        # </create_agent>

        # <run>
        await run_agent_async(
            agent,
            session=agent.create_session(),
            observers=build_observers_with_planning(agent),
            initial_mode="plan",
            title="🛠️ Steward",
            placeholder="Ask about the repo, or say 'review my projects'...",
        )
        # </run>


if __name__ == "__main__":
    asyncio.run(main())
