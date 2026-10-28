"""Shared production-ready Steward agent factory (Step 4).

Follows Part 4 of MAF's "Build your own claw" series: Step 3's agent is restructured into one
factory, ``build_steward_agent``, that thin hosts (``console_app.py``, ``evals.py``) share.

Changes from the guide for local Ollama:
    * Foundry hosting (``hosted.py``, agent manifests), Purview middleware and Foundry Toolbox
      skills are left out: they need Microsoft Foundry / Azure.
    * Skills and the script runner are read from the parent ``steward/`` folder instead of local
      copies (the copies only exist in the guide for Foundry's ZIP deployment).

Environment variables:
    OLLAMA_HOST       — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL      — model name, e.g. gpt-oss:20b
    STEWARD_WORKSPACE — repo or folder Steward works in (defaults to ../working)
"""

from __future__ import annotations

import logging
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
    HistoryProvider,
    InMemoryHistoryProvider,
    SkillsProvider,
    create_harness_agent,
    tool,
)
from agent_framework.monty import MontyCodeActProvider
from agent_framework.ollama import OllamaChatClient
from agent_framework.tools import LocalShellTool, ShellPolicy
from dotenv import load_dotenv
from pydantic import Field

_STEWARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_STEWARD_DIR))
from subprocess_script_runner import subprocess_script_runner  # noqa: E402

load_dotenv()
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or _STEWARD_DIR / "working").resolve()
_SKILLS_DIR = _STEWARD_DIR / "skills"

# Startup diagnostics go through ``logging`` so every host decides where they appear.
logger = logging.getLogger(__name__)

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
    """Stage every change under the workspace and commit it; the user approves before it runs."""
    added = _git("add", "--all", "--", ".")
    if added.returncode != 0:
        return f"git add failed: {added.stderr.strip()}"
    committed = _git("commit", "-m", message)
    if committed.returncode != 0:
        return f"git commit failed: {(committed.stdout + committed.stderr).strip()}"
    return f"Committed {_git('rev-parse', '--short', 'HEAD').stdout.strip()}: {message}"


# </git_commit>


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
    """Build a shell confined to the workspace; every command is surfaced for approval."""
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


# <build_steward_agent>
async def build_steward_agent(
    stack: AsyncExitStack,
    *,
    client: OllamaChatClient | None = None,
    history_provider: HistoryProvider | None = None,
    enable_file_access: bool = True,
    file_memory_store: Any = None,
    enable_shell: bool = True,
    auto_approve_skill_scripts: bool = False,
) -> Agent[Any]:
    """Build the production-ready Steward harness agent.

    Args:
        stack: Owns the lifetime of resources the agent uses (the persistent shell).
        client: Optional preconfigured chat client. Defaults to ``OllamaChatClient()``.
        history_provider: Optional history provider override.
        enable_file_access: When True (default), the agent can read and write workspace files.
        file_memory_store: Optional custom ``AgentFileStore`` for the harness file memory. When None,
            the harness default ``{cwd}/agent-file-memory`` is used.
        enable_shell: When True (default), the agent can run shell commands in the workspace.
        auto_approve_skill_scripts: When True, ``run_skill_script`` is auto-approved so skills complete
            without a human in the loop. Intended for unattended runs such as ``evals.py``; it only
            covers the skill tools — git_commit, the shell and file writes keep their approvals.

    Returns:
        A fully configured harness agent with Step 3's capabilities.
    """
    _WORKING_DIR.mkdir(exist_ok=True)
    client = client or OllamaChatClient()

    tools: list[Any] = [get_repo_status, git_commit]
    if enable_shell:
        shell = await stack.enter_async_context(_build_shell())
        tools.append(shell.as_function())
        logger.info("Shell enabled (confined to %s).", _WORKING_DIR)
    else:
        logger.info("Shell disabled.")

    access_store = FileSystemAgentFileStore(str(_WORKING_DIR)) if enable_file_access else None
    logger.info("File access %s.", f"enabled ({_WORKING_DIR})" if enable_file_access else "disabled")

    # ``load_skill`` only reads a skill's own body, so it skips approval; ``run_skill_script``,
    # which executes code, keeps it unless this is an unattended run.
    skills_provider = SkillsProvider(
        FileSkillsSource(str(_SKILLS_DIR), script_runner=subprocess_script_runner),
        disable_load_skill_approval=True,
    )
    logger.info("Local file skills enabled (from %s).", _SKILLS_DIR)

    auto_approval_rules: list[Any] = [FileAccessProvider.read_only_tools_auto_approval_rule]
    if auto_approve_skill_scripts:
        auto_approval_rules.append(SkillsProvider.all_tools_auto_approval_rule)
        logger.info("Skill script approval disabled (unattended run).")

    # <create_agent>
    return create_harness_agent(
        client=client,
        name="Steward",
        description="Software engineering and development assistant.",
        agent_instructions=STEWARD_INSTRUCTIONS,
        tools=tools,
        history_provider=history_provider or InMemoryHistoryProvider(),
        file_access_store=access_store,
        file_memory_store=file_memory_store,
        skills_provider=skills_provider,
        background_agents=[_build_explorer_agent(client)],
        auto_approval_rules=auto_approval_rules,
        context_providers=[MontyCodeActProvider(approval_mode="never_require")],
        mode_provider=AgentModeProvider(default_mode="execute"),
        max_context_window_tokens=65_536,
        max_output_tokens=8_192,
        disable_web_search=True,
    )
    # </create_agent>


# </build_steward_agent>
