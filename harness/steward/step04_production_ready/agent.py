"""Shared production-ready Steward agent factory (Step 4).

Follows Part 4 of MAF's "Build your own claw" series: Step 3's agent is restructured into one
factory, ``build_steward_agent``, that thin hosts (``console_app.py``, ``evals.py``) share.

Changes from the guide for local Ollama:
    * Foundry hosting (``hosted.py``, agent manifests), Purview middleware and Foundry Toolbox
      skills are left out: they need Microsoft Foundry / Azure.
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
from typing import Annotated, Any

from agent_framework import (
    Agent,
    AgentModeProvider,
    AggregatingSkillsSource,
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


# Part 1 of the guide, as its claw_step01 sample: instructions, one custom tool, web search
# (SecondBrain's, since Ollama has none hosted) and the harness's own planning and file memory.
PART1_INSTRUCTIONS = """\
## Steward: Engineering Assistant Instructions

You are Steward, a software engineering assistant. When asked about the workspace's git state,
look it up with the get_repo_status tool, and use secondbrain_web_search and secondbrain_web_fetch
for documentation, releases or anything else on the web.

### Working style

- Always verify facts with a tool rather than relying on memory.
- Cite web sources inline when you use them.
- Keep the user's watchlist in a memory file called watchlist.md: read it when reviewing the
  watchlist, and update it whenever the user adds or removes an item.

### Important

Say plainly when you don't know something or haven't verified it.
"""


# Desktop\Research, the ground: Manjuel at its root, atlas, worlds\steward, worlds\jesster.
_RESEARCH_DIR = Path(__file__).resolve().parents[5]
PART1_GITHUB_INSTRUCTIONS = """
### GitHub

- Use the run_shell tool for git and gh. The repositories are under the shell's folder:
  Manjuel at its root, atlas, worlds\\steward and worlds\\jesster (SecondBrain).
- Never run git status or git diff with no arguments in the root; use git -C <folder> ls-files -m,
  git -C <folder> log and git -C <folder> show to look.
- Commit only files you name. Commit messages are plain: what changed. Never add Co-Authored-By,
  "Generated with" or any other attribution: all the work is Kyle's.
- main is protected on GitHub: push the branch you are on (git push -u origin <branch>), then open
  a pull request with gh pr create. Never push with --force, --all or --mirror.
"""

# Part 2 of the guide, its working-style lines with Steward's workspace in place of the portfolio.
PART2_INSTRUCTIONS = """
### Your workspace

- The workspace's files are read with the file_access tools. Read them before answering questions
  about the code, and never change a file unless asked. To change one, find the line with
  file_access_grep, read it with file_access_read_lines, and edit it with file_access_replace_lines.
- When asked for a report, write it to a Markdown file under reports/ and tell the user where you
  saved it.
- To commit in the workspace, use the git_commit tool. It takes a real action, so the user will be
  asked to approve it before it runs: say what you are about to commit first.
"""

# MAF's own plan and execute steps (AgentModeProvider's defaults), with plan mode held more firmly:
# on 2026-10-29 Steward skipped MAF's todo, plan-file and approval steps twice and did the work in
# plan mode (Kyle: "tighten it", through mode_instructions, the Learn page's own setting).
_MAF_MODES = AgentModeProvider().mode_instructions
PART1_MODE_INSTRUCTIONS = {
    **_MAF_MODES,
    "plan": _MAF_MODES["plan"]
    + """

Rules that always hold in plan mode:
- Do not do the work yet. Only look: read files, check the repo, or run one quick search if you
  need it to ask a sensible question. Never save results and never write any file except plan.md.
- Before you present the plan, call todos_add with one todo for each step of the plan.
- Write the plan to a memory file called plan.md.
- Every plan-mode reply ends with a clarification (with choices) or an approval request for the
  plan. Never reply with the results of the work.""",
}


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
def _build_shell(workdir: Path = _WORKING_DIR, *, allow_push: bool = False) -> LocalShellTool:
    """Build a shell confined to ``workdir``; every command is surfaced for approval.

    With ``allow_push`` (Kyle, 2026-10-29: Steward does the GitHub work himself) a plain push of
    one branch is allowed; a force push, --all and --mirror stay refused (CLAUDE.md RULE 1).
    """
    push_rule = r"\bgit\s+push\b.*(\s--force|\s-f\b|\s--mirror|\s--all)" if allow_push else r"\bgit\s+push\b"
    return LocalShellTool(
        mode="persistent",
        workdir=str(workdir),
        confine_workdir=True,
        policy=ShellPolicy(
            denylist=[
                r"\brm\s+-[a-z]*r",
                r"\bRemove-Item\b.*-Recurse",
                r"\bdel\s+/s\b",
                push_rule,
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


_EXTRACT_FACTS = """\
From the exchange below, list the durable facts the USER explicitly states about themselves that are
worth remembering in every future session: their preferences, conventions, tools, projects, goals
and ways of working. Only what they say about themselves in so many words: never infer a fact from
a question they ask, a task they request, or what the assistant did. Most turns have none.
Answer with a JSON array of short strings, one fact each, and nothing else. Answer [] if none.

USER: {user}

ASSISTANT: {assistant}
"""


class SecondBrainMemoryProvider(ContextProvider):
    """Long-term memory kept in SecondBrain (MAF Part 2's automatic memory, stored in the vault).

    Before each turn, SecondBrain's two memory notes are put in front of Steward, as SecondBrain's
    own agent does: ``agent-memory`` (facts, decisions, lessons) and ``user-profile`` (about Kyle).
    After each turn, durable facts about Kyle are extracted by the model and added to
    ``user-profile`` with SecondBrain's ``memory`` tool, which dedupes and caps them. The notes are
    ordinary notes, so Kyle can read and edit everything Steward remembers.
    """

    def __init__(self, secondbrain: MCPStreamableHTTPTool, client: Any) -> None:
        super().__init__("secondbrain-memory")
        self._secondbrain = secondbrain
        self._client = client

    async def _memory(self, **arguments: Any) -> str:
        result = await self._secondbrain.call_tool("memory", **arguments)
        return result if isinstance(result, str) else " ".join(getattr(c, "text", "") or "" for c in result)

    async def before_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        try:
            remembered = await self._memory(target="memory", action="read")
            about = await self._memory(target="user", action="read")
        except Exception as exc:  # noqa: BLE001
            logger.warning("SecondBrain memory not read: %s", type(exc).__name__)
            return
        context.extend_messages(
            self.source_id,
            [Message(role="user", contents=[
                "## Your long-term memory (SecondBrain note agent-memory)\n"
                f"{remembered}\n\n## About Kyle (SecondBrain note user-profile)\n{about}"
            ])],
        )

    async def after_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        user = "\n".join(m.text for m in context.input_messages if m and m.text)
        assistant = context.response.text if context.response else ""
        if not user.strip():
            return
        try:
            reply = await self._client.get_response(
                [Message(role="user", contents=[_EXTRACT_FACTS.format(user=user[-4000:], assistant=assistant[-4000:])])]
            )
            facts = json.loads(re.search(r"\[.*\]", reply.text or "[]", re.S).group(0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("No facts extracted this turn: %s", type(exc).__name__)
            return
        for fact in facts:
            if isinstance(fact, str) and fact.strip():
                # A refused add (the profile is full, a duplicate) is SecondBrain's answer, not a
                # failed turn: it is logged, and Steward consolidates the note with secondbrain_memory.
                try:
                    outcome = await self._memory(target="user", action="add", text=fact.strip())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("SecondBrain memory refused a fact: %s", exc)
                    continue
                logger.info("SecondBrain memory: %s", outcome)


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
    part: int = 2,
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
    if part <= 2:
        # Kyle, 2026-10-29: start again from Part 1, exactly as the guide builds it, and add each
        # Part as the one before it passes. The later Parts' pieces below come back the same way.
        secondbrain = await _connect_secondbrain(
            stack, tools=["web_search", "web_fetch", *(["memory"] if part >= 2 else [])]
        )
        # Kyle, 2026-10-29: the retry stays on, because ollama/ollama#17638 (gpt-oss tool calls
        # Ollama cannot parse) is open with no fix in MAF or Ollama
        part1_client = _retry_malformed_tool_calls(client or OllamaChatClient())
        # MAF's own setting: a tool call that fails validation returns the real error, so the model
        # can correct it. Ollama shows gpt-oss todos_add's items as any[] (MAF's $ref schema), and
        # the default "Argument parsing failed." gives him nothing to fix (microsoft/agent-framework#7222).
        part1_client.function_invocation_configuration["include_detailed_errors"] = True
        # Kyle, 2026-10-29: Steward does the GitHub work himself, so MAF's shell (the guide's Part 3
        # piece) comes in early, rooted at Desktop\Research where the repositories are, every
        # command on Kyle's Approve card (LocalShellTool's default approval)
        part1_shell = await stack.enter_async_context(_build_shell(_RESEARCH_DIR, allow_push=True))
        part_tools: list[Any] = [get_repo_status, part1_shell.as_function()]
        instructions = PART1_INSTRUCTIONS + PART1_GITHUB_INSTRUCTIONS
        part2: dict[str, Any] = {}
        if part >= 2:
            # Part 2 of the guide: file access over the workspace (Steward's own store, the guide's
            # "supply your own AgentFileStore", so MAF's line edits keep a CRLF file CRLF), a tool
            # that asks before it acts (git_commit, as the guide's place_trade), auto-approval rules
            # (MAF's read-only file rule and Steward's small-commit rule, the guide's "rule of your
            # own"), and automatic memory (SecondBrain's notes, in place of Foundry memory).
            part_tools.append(git_commit)
            instructions += PART2_INSTRUCTIONS
            part2 = {
                "file_access_store": LineEndingFileStore(str(_WORKING_DIR)),
                "auto_approval_rules": [
                    FileAccessProvider.read_only_tools_auto_approval_rule,
                    small_commit_auto_approval_rule,
                ],
                "context_providers": (
                    [SecondBrainMemoryProvider(secondbrain, part1_client)] if secondbrain is not None else []
                ),
            }
        return create_harness_agent(
            client=part1_client,
            name="Steward",
            agent_instructions=instructions,
            tools=[*part_tools, *([secondbrain] if secondbrain is not None else [])],
            history_provider=history_provider or InMemoryHistoryProvider(),
            mode_provider=AgentModeProvider(mode_instructions=PART1_MODE_INSTRUCTIONS),
            max_context_window_tokens=_STEWARD_CONTEXT,
            default_options={"num_ctx": _STEWARD_CONTEXT},
            disable_web_search=True,
            **part2,
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
            *([CharterProvider(secondbrain), SecondBrainMemoryProvider(secondbrain, client)] if secondbrain is not None else []),
        ],
        mode_provider=AgentModeProvider(default_mode="execute"),
        max_context_window_tokens=_STEWARD_CONTEXT,
        max_output_tokens=8_192,
        default_options={"num_ctx": _STEWARD_CONTEXT},
        disable_web_search=True,
    )
    # </create_agent>


# </build_steward_agent>
