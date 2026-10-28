"""Scaling Steward's capabilities (Step 3).

Follows Part 3 of MAF's "Build your own claw" series
(https://devblogs.microsoft.com/agent-framework/agent-harness-scaling-the-claw-or-harness-capabilities/),
turned into a software engineering assistant on local Ollama. It builds on Step 2 in four ways:

1. Skills        — engineering know-how (code-review, codebase-map) packaged as discoverable
                   SKILL.md files the agent loads on demand, with scripts it can run.
2. Shell         — a shell confined to the workspace, used to run tests, linters, builds and git
                   inspection. Guarded by a deny-list policy and a confined working directory; every
                   command is surfaced for approval.
3. CodeAct       — the agent writes and runs Python in the sandboxed Monty interpreter to crunch
                   numbers (coverage, sizes, timings) instead of estimating.
4. Background agents — a read-only CodeExplorer sub-agent that the main agent fans out to explore
                   several modules concurrently, then aggregates the findings.

Changes from the guide for local Ollama:
    * ``OllamaChatClient`` replaces ``FoundryChatClient``; web search is disabled.
    * The Ollama client doesn't implement ``SupportsShellTool``, so the shell is passed as a plain
      function tool (``shell.as_function()``), the pattern MAF documents for any chat client.
    * The web-search research sub-agent becomes a read-only code explorer.
    * Foundry Toolbox skills are left out: they need Microsoft Foundry.

Environment variables:
    OLLAMA_HOST       — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL      — model name, e.g. gpt-oss:20b
    STEWARD_WORKSPACE — repo or folder Steward works in (defaults to ./working)
"""

import asyncio
import os
import re
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Annotated, Any

from agent_framework import (
    Agent,
    AgentModeProvider,
    FileAccessProvider,
    FileSkillsSource,
    FileSystemAgentFileStore,
    SkillsProvider,
    create_harness_agent,
    tool,
)
from agent_framework.monty import MontyCodeActProvider
from agent_framework.ollama import OllamaChatClient
from agent_framework.tools import LocalShellTool, ShellPolicy
from dotenv import load_dotenv
from pydantic import Field

# Reuse the shared harness console that lives in the parent ``harness/`` directory, and the local
# subprocess script runner used to execute file-based skill scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console import build_observers_with_planning, run_agent_async  # noqa: E402
from subprocess_script_runner import subprocess_script_runner  # noqa: E402

load_dotenv()
_SAMPLE_DIR = Path(__file__).resolve().parent
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or _SAMPLE_DIR / "working").resolve()
_SKILLS_DIR = _SAMPLE_DIR / "skills"

STEWARD_INSTRUCTIONS = """\
## Steward: Engineering Assistant Instructions

You are Steward, a software engineering and development assistant. You work inside the user's
workspace: you map and understand codebases, review changes, fix bugs, run tests, and commit work
when asked.

### Working style

- Read before you write. Use the file_access tools to open the relevant files (and grep for call
  sites) before answering questions about the code or changing it. Never guess at file contents.
- You have skills for code-review and codebase-map. When a request matches a skill, load it and
  follow its instructions (read its references, run its scripts) rather than improvising.
- When asked to understand a large codebase or several modules, delegate each module to the
  background CodeExplorer agent so they are explored concurrently, then combine the findings.
- Use the run_shell tool to run tests, linters, builds and read-only git commands in the workspace.
  Run the tests before and after a change, and report the actual output. Explain what a command
  does before running anything that changes files.
- Use CodeAct (Python) for any calculation instead of estimating.
- Make the smallest change that solves the problem, in the existing style of the file. A change is
  done only when the tests that cover it pass.
- To commit, use the git_commit tool with a clear, imperative message. The user will be asked to
  approve it before it runs, so summarize what is being committed first.

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


# <skills>
def _build_skills_provider() -> SkillsProvider:
    """Build a skills provider over the local skills/ folder (code-review, codebase-map)."""
    # subprocess_script_runner lets the file-based skills run their Python scripts.
    return SkillsProvider(FileSkillsSource(str(_SKILLS_DIR), script_runner=subprocess_script_runner))


# </skills>


# <background>
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".mypy_cache"}


def _inside_workspace(path: str) -> Path:
    """Resolve ``path`` relative to the workspace and refuse anything outside it."""
    resolved = (_WORKING_DIR / path).resolve()
    if resolved != _WORKING_DIR and _WORKING_DIR not in resolved.parents:
        raise ValueError(f"{path} is outside the workspace.")
    return resolved


def list_files(path: Annotated[str, "Folder relative to the workspace root, e.g. '.' or 'src'."] = ".") -> str:
    """List the files under a folder in the workspace (recursively, skipping build and VCS folders)."""
    root = _inside_workspace(path)
    files = [
        str(p.relative_to(_WORKING_DIR))
        for p in sorted(root.rglob("*"))
        if p.is_file() and not _SKIP_DIRS.intersection(p.relative_to(_WORKING_DIR).parts)
    ]
    return "\n".join(files[:500]) or "(no files)"


def read_file(path: Annotated[str, "File path relative to the workspace root."]) -> str:
    """Read a text file from the workspace, with line numbers."""
    lines = _inside_workspace(path).read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(f"{i:>5}  {line}" for i, line in enumerate(lines[:2000], 1))


def search_code(
    pattern: Annotated[str, "Regular expression to search for."],
    path: Annotated[str, "Folder relative to the workspace root."] = ".",
) -> str:
    """Search the workspace's text files for a regular expression; returns file:line: text matches."""
    regex = re.compile(pattern)
    hits: list[str] = []
    for p in sorted(_inside_workspace(path).rglob("*")):
        if not p.is_file() or _SKIP_DIRS.intersection(p.relative_to(_WORKING_DIR).parts):
            continue
        try:
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if regex.search(line):
                    hits.append(f"{p.relative_to(_WORKING_DIR)}:{i}: {line.strip()}")
        except (UnicodeDecodeError, OSError):
            continue
        if len(hits) >= 200:
            break
    return "\n".join(hits) or "(no matches)"


def _build_explorer_agent(client: OllamaChatClient) -> Any:
    """Build the lean, read-only chat agent used to explore one module or question at a time."""
    # This sub-agent doesn't need any harness machinery: it's a plain chat agent with read-only
    # file tools confined to the workspace. The parent exposes the background_agents_* tools because
    # it receives this agent via background_agents.
    return Agent(
        client=client,
        name="CodeExplorer",
        description="Explores one module, folder or question in the workspace (read-only) and summarizes it.",
        tools=[list_files, read_file, search_code],
        instructions=(
            "You explore one part of a codebase. Use list_files, read_file and search_code to find out "
            "what it does, its main entry points and functions, what it depends on, and anything that "
            "looks wrong. Return a short, factual summary (4-6 bullet points) naming files and functions, "
            "with no preamble. Only report what you read."
        ),
    )


# </background>


# <shell>
def _build_shell() -> LocalShellTool:
    """A shell confined to the workspace.

    ``confine_workdir`` re-anchors every command to the workspace, and the deny-list pre-filters
    destructive or publishing commands. (Patterns are a UX guardrail, not a security boundary.)
    Left at the default ``approval_mode="always_require"`` so each command is surfaced for approval.
    """
    return LocalShellTool(
        mode="persistent",
        workdir=str(_WORKING_DIR),
        confine_workdir=True,
        policy=ShellPolicy(
            denylist=[
                r"\brm\s+-[a-z]*r",
                r"\bRemove-Item\b.*-Recurse",
                r"\bdel\s+/s\b",
                r"\bgit\s+push\b",
                r"\bgit\s+reset\s+--hard\b",
                r"\bgit\s+clean\b",
                r"\bsudo\b",
                r"\bformat\s+[a-z]:",
                r"\bshutdown\b",
            ],
        ),
        timeout=120,
    )


# </shell>


async def main() -> None:
    _WORKING_DIR.mkdir(exist_ok=True)

    # <create_client>
    client = OllamaChatClient()
    # </create_client>

    async with AsyncExitStack() as stack:
        skills_provider = _build_skills_provider()
        explorer_agent = _build_explorer_agent(client)
        shell = await stack.enter_async_context(_build_shell())

        # <codeact>
        # CodeAct: a sandboxed Python interpreter the model can write and run code in. Monty is a
        # pure, cross-platform interpreter, so it needs no extra setup.
        context_providers: list[Any] = [MontyCodeActProvider(approval_mode="never_require")]
        # </codeact>

        # <create_agent>
        # On top of Step 2's file access and approvals we add the four "scaling" capabilities:
        # skills, a background explorer, a confined shell (as a function tool) and CodeAct.
        # Read-only file tools are auto-approved; writes, commits and shell commands still prompt.
        agent = create_harness_agent(
            client=client,
            name="Steward",
            agent_instructions=STEWARD_INSTRUCTIONS,
            tools=[get_repo_status, git_commit, shell.as_function()],
            file_access_store=FileSystemAgentFileStore(str(_WORKING_DIR)),
            skills_provider=skills_provider,
            background_agents=[explorer_agent],
            auto_approval_rules=[FileAccessProvider.read_only_tools_auto_approval_rule],
            context_providers=context_providers,
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
            placeholder="Map a codebase, review changes, fix a failing test, or run the build...",
        )
        # </run>


if __name__ == "__main__":
    asyncio.run(main())
