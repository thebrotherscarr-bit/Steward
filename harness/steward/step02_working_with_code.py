"""Working with your code, safely (Step 2).

Follows Part 2 of MAF's "Build your own claw" series
(https://devblogs.microsoft.com/agent-framework/agent-harness-working-with-your-data-safely), turned
into a software engineering assistant on local Ollama. It builds on Step 1 and adds:

1. File access  — read the workspace's source files and write changes and reports
                  (file_access_* tools). Read-only file tools are auto-approved; writes still prompt.
2. Approvals    — the ``git_commit`` tool is marked ``approval_mode="always_require"`` so the
                  harness asks for human approval before anything is committed. A rule of our own
                  (the guide's "trades under $1,000") auto-approves a commit under 20 changed lines
                  with no new files; everything else still prompts.
3. Durable memory — two kinds, as in the guide:
                  * File memory (coarse, explicit): projects.md and notes, on disk under
                    ``{cwd}/agent-file-memory/<session-id>/``. ``/session-export`` +
                    ``/session-import`` re-link a relaunched session to its files.
                  * Automatic memory (fine, automatic): durable facts about the user are extracted
                    after each turn and recalled in later turns and in any new session.

Changes from the guide for local Ollama:
    * ``OllamaChatClient`` replaces ``FoundryChatClient``; web search is disabled.
    * Automatic memory is Mem0 running locally (``Mem0ContextProvider`` over mem0's own
      ``AsyncMemory``) instead of Foundry memory: facts are extracted by the Steward model,
      embedded with nomic-embed-text-v2-moe, and kept in an on-disk Qdrant store under
      ``{cwd}/agent-memory/``. Like the guide's Foundry memory, it uses one fixed user scope, so
      it is recalled in every session, not just a re-linked one.

Environment variables:
    OLLAMA_HOST       — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL      — model name, e.g. gpt-oss:20b
    STEWARD_WORKSPACE — repo or folder Steward works in (defaults to ./working)
"""

import asyncio
import os
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Annotated, Any

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


# <small_commit_rule>
# The guide's "a rule of your own": it auto-approves trades under $1,000; Steward auto-approves a
# commit when the whole change is small. Rules run in order and the first that returns True wins;
# anything else still prompts.
_SMALL_COMMIT_LINES = 20


def small_commit_auto_approval_rule(call: Any) -> bool:
    """Auto-approve git_commit when the change it would commit is under _SMALL_COMMIT_LINES lines."""
    if call.name != "git_commit":
        return False
    if _git("ls-files", "--others", "--exclude-standard", "--", ".").stdout.strip():
        return False  # new files are never "small": always ask
    numstat = _git("diff", "HEAD", "--numstat", "--", ".").stdout.splitlines()
    changed = 0
    for line in numstat:
        added, removed, _ = (line.split("\t") + ["", "", ""])[:3]
        if not (added.isdigit() and removed.isdigit()):
            return False  # binary change: always ask
        changed += int(added) + int(removed)
    return 0 < changed < _SMALL_COMMIT_LINES


# </small_commit_rule>


# <automatic_memory>
_MEMORY_DIR = Path.cwd() / "agent-memory"
_MEMORY_SCOPE = "kyle"


async def _maybe_enable_local_memory() -> Any:
    """Enable automatic memory (the guide's Foundry memory, run locally with Mem0 on Ollama).

    One fixed user scope, so extracted facts are recalled across sessions. Returns None (and says
    so) when Ollama or the store cannot be reached, so Steward still starts.
    """
    try:
        from agent_framework_mem0 import Mem0ContextProvider
        from mem0 import AsyncMemory

        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        _MEMORY_DIR.mkdir(exist_ok=True)
        memory = AsyncMemory.from_config({
            "llm": {"provider": "ollama", "config": {"model": os.environ.get("OLLAMA_MODEL", "gpt-oss:20b"), "ollama_base_url": host}},
            "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text-v2-moe", "ollama_base_url": host, "embedding_dims": 768}},
            "vector_store": {"provider": "qdrant", "config": {"path": str(_MEMORY_DIR / "qdrant"), "collection_name": "steward", "embedding_model_dims": 768, "on_disk": True}},
            "history_db_path": str(_MEMORY_DIR / "history.db"),
            # As the guide's Foundry store (user_profile_enabled=True, chat_summary_enabled=False):
            # keep durable facts about the user, not a log of what the assistant did.
            "custom_instructions": (
                "Extract only durable facts about the user: their preferences, conventions, tools, "
                "projects, goals and ways of working. Do not store what the assistant did, explained, "
                "planned or committed, and do not store one-off requests."
            ),
        })
    except Exception as exc:  # noqa: BLE001
        print(f"Automatic memory disabled: {type(exc).__name__}: {exc}")
        return None
    print(f"Automatic memory enabled (local Mem0, {_MEMORY_DIR}).")
    return Mem0ContextProvider(mem0_client=memory, user_id=_MEMORY_SCOPE, search_user_id=_MEMORY_SCOPE)


# </automatic_memory>


async def main() -> None:
    _WORKING_DIR.mkdir(exist_ok=True)

    # <create_client>
    client = OllamaChatClient()
    # </create_client>

    async with AsyncExitStack() as stack:
        context_providers: list[Any] = []
        local_memory = await _maybe_enable_local_memory()
        if local_memory is not None:
            await stack.enter_async_context(local_memory)
            context_providers.append(local_memory)

        # <create_agent>
        # On top of Step 1 we point file access at the workspace, add the approval-gated git_commit
        # tool, and auto-approve the read-only file tools so reading code is frictionless while writes
        # and commits still prompt. File memory keeps its on-disk default store; automatic memory is
        # added as a context provider.
        agent = create_harness_agent(
            client=client,
            name="Steward",
            agent_instructions=STEWARD_INSTRUCTIONS,
            tools=[get_repo_status, git_commit],
            file_access_store=FileSystemAgentFileStore(str(_WORKING_DIR)),
            auto_approval_rules=[FileAccessProvider.read_only_tools_auto_approval_rule, small_commit_auto_approval_rule],
            context_providers=context_providers or None,
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
