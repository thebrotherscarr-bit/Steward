"""Working with your code, safely (Step 2).

Follows Part 2 of MAF's "Build your own claw" series
(https://devblogs.microsoft.com/agent-framework/agent-harness-working-with-your-data-safely), turned
into a software engineering assistant on local Ollama. It builds on Step 1 and adds:

1. File access  — read the workspace's source files and write changes and reports
                  (file_access_* tools). Read-only file tools are auto-approved; writes still prompt.
2. Approvals    — the ``git_commit`` tool is marked ``approval_mode="always_require"`` so the
                  harness asks for human approval before anything is committed.
3. Durable memory — file memory (projects.md, notes) lives on disk under
                  ``{cwd}/agent-file-memory/<session-id>/`` and persists across runs on this machine.
                  ``/session-export`` + ``/session-import`` re-link a relaunched session to its files.

Changes from the guide for local Ollama:
    * ``OllamaChatClient`` replaces ``FoundryChatClient``; web search is disabled.
    * Foundry memory (cloud fact extraction) is left out: it needs Microsoft Foundry.

Environment variables:
    OLLAMA_HOST       — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL      — model name, e.g. gpt-oss:20b
    STEWARD_WORKSPACE — repo or folder Steward works in (defaults to ./working)
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from agent_framework import (
    AgentModeProvider,
    FileAccessProvider,
    FileSystemAgentFileStore,
    create_harness_agent,
    tool,
)
from agent_framework.ollama import OllamaChatClient
from dotenv import load_dotenv
from pydantic import Field

# Reuse the shared harness console that lives in the parent ``harness/`` directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from console import build_observers_with_planning, run_agent_async  # noqa: E402

load_dotenv()
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or Path(__file__).resolve().parent / "working").resolve()

STEWARD_INSTRUCTIONS = """\
## Steward: Engineering Assistant Instructions

You are Steward, a software engineering and development assistant. You work inside the user's
workspace: you read and understand their code, make careful changes, and commit them when asked.

### Working style

- Read before you write. Use the file_access tools to open the relevant files (and grep for call
  sites) before answering questions about the code or changing it. Never guess at file contents.
- Call get_repo_status before and after making changes so you know the branch and what changed.
- Make the smallest change that solves the problem, in the existing style of the file. Writing a
  file is an action the user approves, so say which file you will change and why first.
- When asked for a review, design note or report, write it to a Markdown file with the file_access
  tools (e.g. reports/review.md) and tell the user where you saved it.
- Keep the user's active projects in a memory file called projects.md, and update it whenever the
  user starts, finishes or describes one.
- To commit, use the git_commit tool with a clear, imperative commit message. The user will be
  asked to approve it before it runs, so summarize what is being committed first.
- Remember durable facts the user tells you (languages, conventions, test commands, preferences)
  and follow them.

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


# <git_commit>
@tool(approval_mode="always_require")
def git_commit(
    message: Annotated[str, Field(min_length=1, description="Imperative commit message, e.g. 'Fix total rounding'.")],
) -> str:
    """Stage every change under the workspace and commit it. Marked approval-required, so the
    harness asks the user to approve before this ever runs.
    """
    added = _git("add", "--all", "--", ".")
    if added.returncode != 0:
        return f"git add failed: {added.stderr.strip()}"
    committed = _git("commit", "-m", message)
    if committed.returncode != 0:
        return f"git commit failed: {(committed.stdout + committed.stderr).strip()}"
    return f"Committed {_git('rev-parse', '--short', 'HEAD').stdout.strip()}: {message}"


# </git_commit>


async def main() -> None:
    _WORKING_DIR.mkdir(exist_ok=True)

    # <create_client>
    client = OllamaChatClient()
    # </create_client>

    # <create_agent>
    # On top of Step 1 we point file access at the workspace, add the approval-gated git_commit tool,
    # and auto-approve the read-only file tools so reading code is frictionless while writes and
    # commits still prompt. File memory keeps its on-disk default store.
    agent = create_harness_agent(
        client=client,
        name="Steward",
        agent_instructions=STEWARD_INSTRUCTIONS,
        tools=[get_repo_status, git_commit],
        file_access_store=FileSystemAgentFileStore(str(_WORKING_DIR)),
        auto_approval_rules=[FileAccessProvider.read_only_tools_auto_approval_rule],
        mode_provider=AgentModeProvider(default_mode="execute"),
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
        initial_mode="execute",
        title="🛠️ Steward",
        placeholder="Explain some code, fix a bug, write a review, or commit your changes...",
    )
    # </run>


if __name__ == "__main__":
    asyncio.run(main())
