"""Shared production-ready Steward agent factory (Step 4).

Follows Part 4 of MAF's "Build your own claw" series: Step 3's agent is restructured into one
factory, ``build_steward_agent``, that thin hosts (``console_app.py``, ``evals.py``) share.

Changes from the guide for local Ollama:
    * Foundry deployment (agent manifests) is left out: it needs Microsoft Foundry / Azure.
    * Local pieces stand in for the rest: Presidio for Purview, SecondBrain's skill notes over MCP
      for Foundry Toolbox skills, and SecondBrain's web tools for hosted web search (the main agent
      and WebResearchAgent).
    * Skills and the script runner are read from the parent ``steward/`` folder instead of local
      copies (the copies only exist in the guide for Foundry's ZIP deployment).

Steward's team (each a background agent on its own local model):
    * Steward (orchestrator) — OLLAMA_MODEL, e.g. gpt-oss:20b: talks to the user, plans, uses tools.
    * CodeExplorer — the orchestrator's model: explores modules read-only.
    * Coder        — STEWARD_CODER_MODEL (qwen3-coder:30b): returns exact code edits to apply.
    * Reasoner     — STEWARD_REASONER_MODEL (deepseek-r1:14b): thinks through hard problems; no tools.
    * Explainer    — STEWARD_CONVERSATION_MODEL (gemma4:26b): explanations, docs and summaries.

Environment variables:
    OLLAMA_HOST                — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL               — orchestrator model, e.g. gpt-oss:20b
    STEWARD_CODER_MODEL        — coder model (defaults to qwen3-coder:30b)
    STEWARD_REASONER_MODEL     — reasoner model (defaults to deepseek-r1:14b)
    STEWARD_CONVERSATION_MODEL — conversationalist model (defaults to gemma4:26b)
    STEWARD_WORKSPACE          — repo or folder Steward works in (defaults to ../working)
    SECONDBRAIN_MCP_URL        — SecondBrain's MCP endpoint, e.g. http://127.0.0.1:43110/mcp
    SECONDBRAIN_MCP_KEY        — its share key (SecondBrain → Settings → Share); never printed
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from agent_framework import (
    Agent,
    AgentModeProvider,
    AggregatingSkillsSource,
    ChatContext,
    ChatMiddleware,
    ChatResponse,
    ContextProvider,
    DeduplicatingSkillsSource,
    FileAccessProvider,
    FileSkillsSource,
    FileSystemAgentFileStore,
    HistoryProvider,
    InMemoryHistoryProvider,
    MCPSkillsSource,
    MCPStreamableHTTPTool,
    Message,
    MiddlewareTermination,
    ResponseStream,
    SkillsProvider,
    create_harness_agent,
    tool,
)
from agent_framework.monty import MontyCodeActProvider
from agent_framework.ollama import OllamaChatClient
from agent_framework.tools import (
    LocalShellTool,
    ShellEnvironmentProvider,
    ShellEnvironmentProviderOptions,
    ShellFamily,
    ShellPolicy,
)
from dotenv import load_dotenv
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import Field
import httpx2

_STEWARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_STEWARD_DIR))
from subprocess_script_runner import subprocess_script_runner  # noqa: E402

load_dotenv()
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or _STEWARD_DIR / "working").resolve()
_SKILLS_DIR = _STEWARD_DIR / "skills"
# Kyle, 2026-10-29: gemma4:26b replaces gemma4:12b (better reviewed; measured 60 tok/s vs 52 here).
# qwen3-coder:30b stays: devstral-small-2:24b, the reviews' 16 GB pick, measured 13 tok/s at an 8k
# context against qwen3-coder's 41, because its dense weights never fit the card.
_CODER_MODEL = os.environ.get("STEWARD_CODER_MODEL", "qwen3-coder:30b")
_REASONER_MODEL = os.environ.get("STEWARD_REASONER_MODEL", "deepseek-r1:14b")
_CONVERSATION_MODEL = os.environ.get("STEWARD_CONVERSATION_MODEL", "gemma4:26b")
# The context Ollama loads each model with (num_ctx, a chat option). Ollama's own default here is
# 131,072, which put 4 GB of gpt-oss:20b in system RAM: 45.6 tok/s, against 84.6 at 65,536.
# Steward's prompts already reach ~23k tokens, so he keeps 65,536, matching the harness budget below;
# CodeExplorer shares his model and context so Ollama never reloads it between them. The rest of the
# team works from shorter inputs: 32,768.
_STEWARD_CONTEXT = 65_536
_TEAM_CONTEXT = 32_768

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
- You lead a team of background agents, each on its own model. Delegate to them, then apply and
  verify their output yourself. Start a task once, wait for it, then read its result with
  get_task_results; never start the same task again while one is running or finished.
  - CodeExplorer: explores one module or folder read-only. Use one per module, concurrently.
  - Coder: writes and fixes code. Give it the task and the files involved; it returns the exact
    edits, which you apply with the file_access tools and then test.
  - Reasoner: thinks through hard debugging, root-cause and design questions. It cannot read
    files, so include the relevant code, errors and test output in its input.
  - Explainer: writes clear explanations, documentation, summaries and commit messages.
- Use the run_shell tool to run tests, linters, builds and read-only git commands in the workspace.
  Run the tests before and after a change, and report the actual output. Explain what a command
  does before running anything that changes files.
- Use CodeAct (Python) for any calculation instead of estimating.
- Edit existing files with file_access_replace (exact old text to new text), one small edit per
  call; use file_access_grep and file_access_read_lines to find the lines first. Never rewrite a
  whole existing file with file_access_write: large writes break the tool call. Keep every tool
  call's arguments under about 1,500 characters; split a bigger change into several edits, top
  to bottom (for example the opening lines, then the middle, then the end).
- CodeAct (execute_code) is for calculation only: it cannot see the file tools or the disk, so
  never try to edit files from it.
- An edit is applied only when file_access_replace returns "Replaced". If a tool fails, is refused
  or is still waiting for approval, say so. Never report a change, or show file content, that a
  tool result did not give you. Read the file back before saying it is done.
- Make the smallest change that solves the problem, in the existing style of the file. A change is
  done only when the tests that cover it pass.
- To commit, use the git_commit tool with a clear, imperative message. The user will be asked to
  approve it before it runs, so summarize what is being committed first.
- When the secondbrain_* tools are available, SecondBrain's notes are your long-term memory: the
  user's plans, rulings, laws and past work. Search them (secondbrain_search_notes, then
  secondbrain_read_note) before answering about any of those, and cite the note you used. When
  the user asks you to remember something, write it there with secondbrain_write_note or
  secondbrain_append_to_note. secondbrain_git_commit goes through SecondBrain's door and is held
  for the user's approval there; say so when you make one.
- Learning loop: when you learn a durable fact about the work, make a decision with Kyle, or
  find a lesson (a mistake not to repeat), record it with secondbrain_memory, target "memory",
  action "add", in one short line. When the memory is full, consolidate with "replace" or
  "remove" instead of adding. Facts about Kyle himself are kept for you automatically.
- "About Kyle" and your long-term memory are put in front of you every turn. When Kyle asks about
  himself, his preferences or how he works, answer from "About Kyle" first, then add what notes say.
- Notes age. Give the date of every note you cite (its updated date), prefer the newest note on a
  subject, and never report an older note's status, plans or priorities as current: say "as of"
  that date.

### Important

Say plainly when you don't know something or haven't verified it. Never invent file contents,
APIs or command output.
"""


# Part 1: the plan's step 1 (step01_meet_steward.py), as written there.
PART1_INSTRUCTIONS = """\
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


# Part 2: the plan's step 2 (step02_working_with_code.py), as written there.
PART2_INSTRUCTIONS = """\
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


# Part 3: the plan's step 3 (step03_scaling_capabilities.py), as written there.
PART3_INSTRUCTIONS = """\
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
- When asked to research several libraries, tools or topics on the web, delegate each one to the
  background WebResearchAgent so they run concurrently, then summarize the findings together.
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
        # --short lists paths relative to the workspace, so they open with file access as given
        "changes": _git("status", "--short", "--", ".").stdout.splitlines(),
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
        default_options={"num_ctx": _STEWARD_CONTEXT},
        instructions=(
            "You explore one part of a codebase. Use list_files, read_file and search_code to find out "
            "what it does, its main entry points and functions, what it depends on, and anything that "
            "looks wrong. Return a short, factual summary (4-6 bullet points) naming files and functions, "
            "with no preamble. Only report what you read."
        ),
    )


def _build_coder_agent() -> Any:
    """Build the coding agent on the coder model; it reads the workspace and returns exact edits."""
    return Agent(
        client=OllamaChatClient(model=_CODER_MODEL),
        name="Coder",
        description="Writes and fixes code: reads the files involved and returns the exact edits to make.",
        tools=[list_files, read_file, search_code],
        default_options={"num_ctx": _TEAM_CONTEXT},
        instructions=(
            "You are an expert software engineer. Read the files involved with read_file and search_code "
            "before writing anything. Return each change as: the file path, then the exact existing text "
            "to replace and the new text, ready to apply. Keep the existing style and make the smallest "
            "change that works. You cannot write files yourself, so never claim a change is applied. "
            "Your final reply is only the edits, with no narration of the steps you took."
        ),
    )


def _build_reasoner_agent() -> Any:
    """Build the reasoning agent on the reasoner model; it has no tools and works from its input."""
    return Agent(
        client=OllamaChatClient(model=_REASONER_MODEL),
        name="Reasoner",
        description="Thinks through hard debugging, root-cause and design questions from the context it is given.",
        default_options={"num_ctx": _TEAM_CONTEXT},
        instructions=(
            "You reason carefully about hard software problems: bugs, root causes, design trade-offs. "
            "Work only from the code, errors and output in your input. Give your conclusion first, then "
            "the key reasoning in a few short points, and say what evidence would confirm it."
        ),
    )


def _build_conversation_agent() -> Any:
    """Build the conversationalist agent on the conversation model, for prose for the user."""
    return Agent(
        client=OllamaChatClient(model=_CONVERSATION_MODEL),
        name="Explainer",
        description="Writes clear explanations, documentation, summaries and commit messages for the user.",
        default_options={"num_ctx": _TEAM_CONTEXT},
        instructions=(
            "You write clear, friendly, accurate prose for a software engineer: explanations, docs, "
            "summaries and commit messages. Use only the facts in your input and keep it concise."
        ),
    )


# </background>


# <shell>
def _build_shell() -> LocalShellTool:
    """Build a shell confined to the workspace; every command is surfaced for approval."""
    return LocalShellTool(
        # Kyle, 2026-10-29: bash (Git Bash) by preference, through MAF's own shell override
        shell=[r"C:\Program Files\Git\bin\bash.exe"],
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
        # Kyle, 2026-10-29: long enough for Steward to run the improvement loop (about 20 minutes)
        timeout=3600,
    )


# </shell>


# <tool_call_retry>
_TOOL_CALL_RETRIES = 2


def _retry_malformed_tool_calls(client: OllamaChatClient) -> OllamaChatClient:
    """Retry a model turn whose tool call Ollama could not parse, instead of failing the run.

    gpt-oss sometimes emits invalid JSON for a tool call that carries code; Ollama then raises
    "error parsing tool call" mid-stream and the whole turn dies. The model samples again on a
    retry, so the same request is re-asked (without streaming) up to _TOOL_CALL_RETRIES times.
    """
    from ollama import ResponseError

    chat = client.client.chat

    async def _ask_again(kwargs: dict[str, Any], first: ResponseError) -> Any:
        error = first
        for attempt in range(1, _TOOL_CALL_RETRIES + 1):
            logger.warning("Malformed tool call from the model; asking again (%d/%d).", attempt, _TOOL_CALL_RETRIES)
            try:
                return await chat(**{**kwargs, "stream": False})
            except ResponseError as exc:
                if "error parsing tool call" not in str(exc):
                    raise
                error = exc
        raise error

    async def chat_with_retry(*args: Any, **kwargs: Any) -> Any:
        if not kwargs.get("stream"):
            try:
                return await chat(*args, **kwargs)
            except ResponseError as exc:
                if "error parsing tool call" not in str(exc):
                    raise
                return await _ask_again(kwargs, exc)
        stream = await chat(*args, **kwargs)

        async def parts() -> Any:
            try:
                async for part in stream:
                    yield part
            except ResponseError as exc:
                if "error parsing tool call" not in str(exc):
                    raise
                yield await _ask_again(kwargs, exc)

        return parts()

    client.client.chat = chat_with_retry  # type: ignore[method-assign]
    return client


# </tool_call_retry>


# <file_store>
class LineEndingFileStore(FileSystemAgentFileStore):
    """The workspace file store, line-ending safe for a Windows repo.

    Many files here are CRLF, while the model writes "\\n" in file_access_replace's old/new text,
    so a multi-line edit never matched. Steward reads every file with "\\n" endings; a write keeps
    the endings the file already had on disk (CRLF stays CRLF, LF stays LF, new files are LF).
    """

    async def read(self, path: str) -> str | None:
        content = await super().read(path)
        return content.replace("\r\n", "\n") if content is not None else None

    async def write(self, path: str, content: str, *, overwrite: bool = True) -> None:
        existing = await super().read(path) if await self.file_exists(path) else None
        content = content.replace("\r\n", "\n")
        if existing is not None and "\r\n" in existing:
            content = content.replace("\n", "\r\n")
        await super().write(path, content, overwrite=overwrite)


# </file_store>


# <secondbrain>
# Stage 1 starts small: the notes, git reads and a held commit. Notes writes ask in
# Steward's console; door writes are held by SecondBrain's own gate, so they are not asked twice.
_SECONDBRAIN_TOOLS = [
    "search_notes", "read_note", "list_notes", "search_sessions", "write_note", "append_to_note",
    "git", "git_diff", "notes", "git_commit",
    "web_search", "web_fetch",  # Part 1: the web, through SecondBrain's own tools
    "memory",  # Part 2: SecondBrain's long-term memory notes (agent-memory, user-profile)
    "skill_save",  # Part 3: new skills are saved to SecondBrain, where they are served from
    # SecondBrain's browser window and computer use (Kyle, 2026-10-28: "allow clicking and typing
    # too", "computer use"): served while switched on in SecondBrain's Settings, never asked
    "browser_open", "browser_read", "browser_click", "browser_type", "browser_press", "browser_scroll", "browser_back",
    "computer_task", "screen_look",
]  # hold_list is left out: SecondBrain answers it only to Kyle's glass
_SECONDBRAIN_ASKS = ["write_note", "append_to_note", "skill_save"]


async def _connect_secondbrain(stack: AsyncExitStack, tools: list[str] = _SECONDBRAIN_TOOLS) -> MCPStreamableHTTPTool | None:
    """Connect to SecondBrain's MCP endpoint, or return None when it is not configured or not up."""
    url = os.environ.get("SECONDBRAIN_MCP_URL")
    key = os.environ.get("SECONDBRAIN_MCP_KEY")
    if not url or not key:
        logger.info("SecondBrain not connected (SECONDBRAIN_MCP_URL / SECONDBRAIN_MCP_KEY not set).")
        return None
    secondbrain = MCPStreamableHTTPTool(
        name="secondbrain",
        url=url,
        tool_name_prefix="secondbrain",  # the door's git_commit would clash with Steward's own
        static_headers={"Authorization": f"Bearer {key}"},
        allowed_tools=tools,
        approval_mode={
            "always_require_approval": [t for t in tools if t in _SECONDBRAIN_ASKS],
            "never_require_approval": [t for t in tools if t not in _SECONDBRAIN_ASKS],
        },
        load_prompts=False,
        request_timeout=60,
    )
    try:
        await stack.enter_async_context(secondbrain)
    except Exception as exc:  # SecondBrain down, sharing off or a wrong key: run without it
        logger.warning("SecondBrain not connected (%s): %s", url, type(exc).__name__)
        return None
    logger.info("SecondBrain connected (%s).", url)
    return secondbrain


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
        logger.warning("Automatic memory disabled: %s: %s", type(exc).__name__, exc)
        return None
    logger.info("Automatic memory enabled (local Mem0, %s).", _MEMORY_DIR)
    return Mem0ContextProvider(mem0_client=memory, user_id=_MEMORY_SCOPE, search_user_id=_MEMORY_SCOPE)


# </automatic_memory>


_CHARTER_NOTE = "steward-charter"


class CharterProvider(ContextProvider):
    """Steward's Charter, put in his instructions every turn: what we are building, what binds him.

    The Charter is a SecondBrain note (steward-charter), read fresh before each turn, so Kyle can
    change it there and the next turn follows it. Step 1 of the design note
    plan-steward-small-model-smart-harness.
    """

    def __init__(self, secondbrain: MCPStreamableHTTPTool) -> None:
        super().__init__("steward-charter")
        self._secondbrain = secondbrain

    async def before_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        try:
            result = await self._secondbrain.call_tool("read_note", id=_CHARTER_NOTE)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Charter not read: %s", type(exc).__name__)
            return
        text = result if isinstance(result, str) else " ".join(getattr(c, "text", "") or "" for c in result)
        if text.strip():
            context.extend_instructions(self.source_id, text)


# </secondbrain>


# <governance>
# The guide's Purview step, on this PC: Microsoft Presidio (open source, offline) screens what goes to
# the model and what comes back, in the same place and the same way as the guide's
# PurviewChatPolicyMiddleware (chat middleware: the prompt before the call, the whole response after
# it, a streamed response buffered and screened before any of it is released). Opt-in, as Purview
# is: on when PRESIDIO_ENTITIES lists the entity types to block.
_PRESIDIO_SCORE = 0.5


class PresidioChatPolicyMiddleware(ChatMiddleware):
    """Block a prompt or a response that contains one of the listed Presidio entity types."""

    def __init__(self, entities: list[str]) -> None:
        from presidio_analyzer import AnalyzerEngine

        self._analyzer = AnalyzerEngine()
        self._entities = entities

    def _found(self, messages: Any) -> list[str]:
        text = "\n".join(m.text for m in messages if m is not None and m.text)
        if not text.strip():
            return []
        results = self._analyzer.analyze(text=text, entities=self._entities, language="en", score_threshold=_PRESIDIO_SCORE)
        return sorted({r.entity_type for r in results})

    def _screened(self, response: ChatResponse[Any]) -> ChatResponse[Any]:
        found = self._found(response.messages)
        if not found:
            return response
        logger.warning("Presidio blocked a response (%s).", ", ".join(found))
        return ChatResponse(
            messages=[Message(role="system", contents=["Response blocked by policy"])],
            response_id=response.response_id,
            conversation_id=response.conversation_id,
            model=response.model,
            finish_reason=response.finish_reason,
            usage_details=response.usage_details,
        )

    async def process(self, context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
        found = self._found(context.messages)
        if found:
            logger.warning("Presidio blocked a prompt (%s).", ", ".join(found))
            blocked = ChatResponse(messages=[Message(role="system", contents=["Prompt blocked by policy"])])
            if context.stream:
                # A streamed call must get a ResponseStream back: MAF's own to_updates, "where a
                # complete response has to be emitted as a stream".
                async def _updates() -> Any:
                    for update in blocked.to_updates():
                        yield update

                context.result = ResponseStream(_updates(), finalizer=lambda _: blocked)
            else:
                context.result = blocked
            raise MiddlewareTermination
        await call_next()
        if isinstance(context.result, ResponseStream):

            async def _transform(final: ChatResponse[Any]) -> ChatResponse[Any]:
                return self._screened(final)

            context.stream_result_transforms.append(_transform)
            context.stream_result_to_updates = ChatResponse.to_updates
            context.stream_buffer_updates = True
            return
        if context.result is not None:
            context.result = self._screened(context.result)


def _build_governance_middleware() -> list[ChatMiddleware]:
    """The guide's _build_purview_middleware, with Presidio: on only when PRESIDIO_ENTITIES is set."""
    entities = [e.strip() for e in os.environ.get("PRESIDIO_ENTITIES", "").split(",") if e.strip()]
    if not entities:
        logger.info("Presidio disabled. Set PRESIDIO_ENTITIES to enable chat policy screening.")
        return []
    logger.info("Presidio enabled (blocks %s).", ", ".join(entities))
    return [PresidioChatPolicyMiddleware(entities)]


# </governance>


def _secondbrain_web_tools(client: Client) -> MCPStreamableHTTPTool:
    """SecondBrain's web_search and web_fetch over the shared client (Ollama has no hosted web search)."""
    return MCPStreamableHTTPTool(
        name="secondbrain",
        mcp_client=client,
        tool_name_prefix="secondbrain",
        allowed_tools=["web_search", "web_fetch"],
        approval_mode="never_require",
        load_prompts=False,
    )


def _build_web_research_agent(client: OllamaChatClient, web_tools: MCPStreamableHTTPTool) -> Agent[Any]:
    """The guide's lean, web-search-only research agent (claw_step04 _build_research_agent)."""
    return Agent(
        client=client,
        name="WebResearchAgent",
        description="Searches the web for recent news and documentation about a single library, tool or topic.",
        tools=[web_tools],
        instructions=(
            "You research a single library, tool or topic. Use the web search tool to find the most recent, "
            "relevant news and documentation, then return a short, factual summary (3-4 bullet points) "
            "with no preamble."
        ),
    )


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
    part: int = 4,
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
    if part <= 4:
        # Kyle, 2026-10-29: start over at step 1 and follow the plan. Part 1 is
        # step01_meet_steward.py's construction, Part 2 is step02_working_with_code.py's and Part 3 is
        # step03_scaling_capabilities.py's, each as written there.
        # Part 4 is Part 3's agent with MAF's claw_step04 factory switches for its hosts.
        # Web search is the harness default in every MAF step (none of claw_step02..04 turns it off);
        # Ollama has no hosted web search, so every part gets SecondBrain's web_search and web_fetch,
        # as Part 1 does. (Kyle, 2026-10-29: "fix the shit that you left out", superseding his earlier
        # "Part 2 has no web tools".)
        tools: list[Any] = [get_repo_status]
        url = os.environ.get("SECONDBRAIN_MCP_URL")
        key = os.environ.get("SECONDBRAIN_MCP_KEY")
        secondbrain_client: Client | None = None
        if url and key:
            # One high-level MCP client for SecondBrain, as MAF's mcp_based_skill sample opens one: the
            # web tools and (from Part 3) MCPSkillsSource share it. The key rides on its http client,
            # with the MCP SDK's own timeouts (create_mcp_http_client: 30 s, 300 s to read).
            http = await stack.enter_async_context(
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=httpx2.Timeout(30.0, read=300.0))
            )
            secondbrain_client = await stack.enter_async_context(Client(streamable_http_client(url, http_client=http)))
            # Kyle, 2026-10-30 (MAF improvement loop, case 1; supersedes "every part" above for Parts
            # 3 and 4): from Part 3 the web tools are the WebResearchAgent's alone, so Steward delegates
            # web research instead of searching himself. MAF's fix at the lowest layer, tool selection.
            if part <= 2:
                tools.append(await stack.enter_async_context(_secondbrain_web_tools(secondbrain_client)))
        if part == 1:
            return create_harness_agent(
                client=client or OllamaChatClient(),
                name="Steward",
                agent_instructions=PART1_INSTRUCTIONS,
                tools=tools,
                history_provider=history_provider,
                max_context_window_tokens=65_536,
                max_output_tokens=8_192,
                disable_web_search=True,
            )
        if part == 2:
            context_providers: list[Any] = []
            local_memory = await _maybe_enable_local_memory()
            if local_memory is not None:
                await stack.enter_async_context(local_memory)
                context_providers.append(local_memory)
            return create_harness_agent(
                client=client or OllamaChatClient(),
                name="Steward",
                agent_instructions=PART2_INSTRUCTIONS,
                tools=[*tools, git_commit],
                history_provider=history_provider,
                file_access_store=FileSystemAgentFileStore(str(_WORKING_DIR)),
                auto_approval_rules=[FileAccessProvider.read_only_tools_auto_approval_rule, small_commit_auto_approval_rule],
                context_providers=context_providers or None,
                mode_provider=AgentModeProvider(default_mode="execute"),
                max_context_window_tokens=65_536,
                max_output_tokens=8_192,
                disable_web_search=True,
            )
        # Part 4 adds governance on the chat client, as the guide adds Purview (Presidio, locally)
        part3_client = client or (OllamaChatClient(middleware=_build_governance_middleware()) if part == 4 else OllamaChatClient())
        explorer_agent = Agent(
            client=part3_client,
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
        background_agents: list[Any] = [explorer_agent]
        skill_sources: list[Any] = [FileSkillsSource(str(_SKILLS_DIR), script_runner=subprocess_script_runner)]
        if secondbrain_client is not None:
            # The guide's background research agent and its managed (Foundry Toolbox) skills, on this PC:
            # the research agent searches with SecondBrain's web tools, and SecondBrain's skill notes are
            # read with MCPSkillsSource over the same client, beside the file skills (claw_step04).
            web_tools = await stack.enter_async_context(_secondbrain_web_tools(secondbrain_client))
            background_agents.append(_build_web_research_agent(part3_client, web_tools))
            skill_sources.append(MCPSkillsSource(client=secondbrain_client))
        skills_source = skill_sources[0] if len(skill_sources) == 1 else AggregatingSkillsSource(skill_sources)
        # Part 4, as MAF's claw_step04 build_claw_agent: the shell and file access can be switched off
        # for a host, skill scripts auto-approved for unattended evals, and load_skill asks no approval
        # ("it only reads a skill's own body"); everything else is Part 3's agent.
        part4 = part == 4
        part3_tools: list[Any] = [*tools, git_commit]
        part3_providers: list[Any] = [MontyCodeActProvider(approval_mode="never_require")]
        if not part4 or enable_shell:
            shell = await stack.enter_async_context(_build_shell())
            # Kyle, 2026-10-29: MAF's run_shell text never names the shell, so it is named here
            # (as_function's description), and Steward's own line-ending store keeps a CRLF file CRLF.
            part3_tools.append(shell.as_function(description=shell.as_function().description + " The shell is bash (Git Bash on Windows)."))
            # ADR-0001 item 2: MAF's ShellEnvironmentProvider tells Steward his shell, OS, working
            # directory and tool versions before each run. The harness factory adds it only through
            # shell_executor, which needs a client with SupportsShellTool, and OllamaChatClient has
            # none, so it is added as MAF's shell-tools guide does for a plain agent. The provider
            # assumes PowerShell on Windows (_detect_family), and its PowerShell probe ends a bash
            # session, so the family is set with MAF's own override_family: the shell is Git Bash.
            part3_providers.append(
                ShellEnvironmentProvider(shell, ShellEnvironmentProviderOptions(override_family=ShellFamily.POSIX))
            )
        auto_approval_rules: list[Any] = [FileAccessProvider.read_only_tools_auto_approval_rule]
        if part4 and auto_approve_skill_scripts:
            auto_approval_rules.append(SkillsProvider.all_tools_auto_approval_rule)
        return create_harness_agent(
            client=part3_client,
            name="Steward",
            description="Software engineering and development assistant." if part4 else None,
            agent_instructions=PART3_INSTRUCTIONS,
            tools=part3_tools,
            history_provider=history_provider,
            file_access_store=LineEndingFileStore(str(_WORKING_DIR)) if not part4 or enable_file_access else None,
            file_memory_store=file_memory_store,
            skills_provider=SkillsProvider(DeduplicatingSkillsSource(skills_source), disable_load_skill_approval=part4),
            background_agents=background_agents,
            auto_approval_rules=auto_approval_rules,
            context_providers=part3_providers,
            mode_provider=AgentModeProvider(default_mode="execute"),
            max_context_window_tokens=65_536,
            max_output_tokens=8_192,
            disable_web_search=True,
        )
    client = _retry_malformed_tool_calls(client or OllamaChatClient())

    tools: list[Any] = [get_repo_status, git_commit]
    if enable_shell:
        shell = await stack.enter_async_context(_build_shell())
        tools.append(shell.as_function())
        logger.info("Shell enabled (confined to %s).", _WORKING_DIR)
    else:
        logger.info("Shell disabled.")
    secondbrain = await _connect_secondbrain(stack)
    if secondbrain is not None:
        tools.append(secondbrain)

    access_store = LineEndingFileStore(str(_WORKING_DIR)) if enable_file_access else None
    logger.info("File access %s.", f"enabled ({_WORKING_DIR})" if enable_file_access else "disabled")

    # ``load_skill`` only reads a skill's own body, so it skips approval; ``run_skill_script``,
    # which executes code, keeps it unless this is an unattended run.
    # Skills come from two places, aggregated as in the guide's Part 3: Steward's own file skills
    # (they carry runnable scripts) and SecondBrain's skill notes, served as MCP resources and
    # discovered with MCPSkillsSource (centrally managed: a skill Kyle or Steward saves in
    # SecondBrain is picked up without touching Steward).
    skill_sources: list[Any] = [FileSkillsSource(str(_SKILLS_DIR), script_runner=subprocess_script_runner)]
    if secondbrain is not None:
        # The live client of the already-connected secondbrain tool (MAF exposes no public getter).
        skill_sources.append(
            MCPSkillsSource(session_provider=lambda: secondbrain._connection.client or secondbrain._connection.session)
        )
    skills_provider = SkillsProvider(
        DeduplicatingSkillsSource(AggregatingSkillsSource(skill_sources)) if len(skill_sources) > 1 else skill_sources[0],
        disable_load_skill_approval=True,
    )
    logger.info("Skills enabled: files (%s)%s.", _SKILLS_DIR, " and SecondBrain" if secondbrain is not None else "")

    auto_approval_rules: list[Any] = [FileAccessProvider.read_only_tools_auto_approval_rule, small_commit_auto_approval_rule]
    if auto_approve_skill_scripts:
        auto_approval_rules.append(SkillsProvider.all_tools_auto_approval_rule)
        logger.info("Skill script approval disabled (unattended run).")

    local_memory = await _maybe_enable_local_memory()
    if local_memory is not None:
        await stack.enter_async_context(local_memory)

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
        background_agents=[
            _build_explorer_agent(client),
            _build_coder_agent(),
            _build_reasoner_agent(),
            _build_conversation_agent(),
        ],
        auto_approval_rules=auto_approval_rules,
        context_providers=[
            MontyCodeActProvider(approval_mode="never_require"),
            *([CharterProvider(secondbrain)] if secondbrain is not None else []),
            *([local_memory] if local_memory is not None else []),
        ],
        mode_provider=AgentModeProvider(default_mode="execute"),
        max_context_window_tokens=_STEWARD_CONTEXT,
        max_output_tokens=8_192,
        default_options={"num_ctx": _STEWARD_CONTEXT},
        disable_web_search=True,
    )
    # </create_agent>


# </build_steward_agent>
