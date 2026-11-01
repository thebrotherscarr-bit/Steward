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
    STEWARD_WORKSPACE          — repo or folder Steward works in (defaults to this repo, worlds/steward,
                                 per ADR-0001 item 11: his own code is in reach; reads run without a
                                 card and writes ask, and the file store never reads, searches or
                                 lists a .env file)
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
from contextvars import ContextVar
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from agent_framework import (
    Agent,
    AgentContext,
    AgentModeProvider,
    AggregatingSkillsSource,
    ChatContext,
    ChatMiddleware,
    ChatResponse,
    ContextProvider,
    DeduplicatingSkillsSource,
    FileAccessProvider,
    FileMemoryProvider,
    FileSkillsSource,
    FileSystemAgentFileStore,
    HistoryProvider,
    InMemoryHistoryProvider,
    MCPSkillsSource,
    FunctionInvocationContext,
    MCPStreamableHTTPTool,
    Message,
    MiddlewareTermination,
    ResponseStream,
    SkillsProvider,
    TodoProvider,
    create_harness_agent,
    get_agent_mode,
    set_agent_mode,
    todos_remaining,
    todos_remaining_message,
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
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or _STEWARD_DIR.parents[1]).resolve()
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


# <todo_instructions>
# Kyle, 2026-10-31: "he should have the todo list at all times and default to plan mode. a simple task
# can be easily messed up. unless he has an actual skill he is calling, there is no simple task."
# MAF's own todo text (TodoProvider's default, _harness/_todo.py) lets a "simple" ask skip the list
# and be done at once; asked to write one file in plan mode, he read that as leave to skip the plan.
# So his TodoProvider gets MAF's text with that choice replaced (instructions=, MAF's override): every
# task is turned into todos, and a matching skill's steps are the todos.
_MAF_TODO_STEPS = (
    "1. Determine whether the ask requires multiple steps to complete (complex) or can be completed "
    "using a single step (simple).\n"
    "2. If complex, turn the task into manageable todo items and add them to the list.\n"
    "3. If simple, don't add a todo item, but rather just complete the task directly.\n\n"
)
_STEWARD_TODO_STEPS = (
    "1. There is no simple task: one step can still go wrong. Turn every task into manageable todo items "
    "and add them to the list with todos_add before you act, and keep the list current until the task is done. "
    "Each item is an object with a title, never a bare string: "
    'todos_add(todos=[{"title": "Read the file"}, {"title": "Write the change"}]).\n'
    "2. When the task matches one of your skills, load it with load_skill and add the skill's steps as the "
    "todo items; follow the skill rather than improvising.\n"
    "3. The todo items are the plan: in plan mode, present them for the user's approval before execute mode.\n\n"
)
_MAF_TODO_INSTRUCTIONS = TodoProvider().instructions
if _MAF_TODO_STEPS not in _MAF_TODO_INSTRUCTIONS:
    # MAF changed its todo text: refuse to start rather than silently keep the "simple task" exception.
    raise RuntimeError("MAF's TodoProvider instructions changed; update _MAF_TODO_STEPS in agent.py.")
STEWARD_TODO_INSTRUCTIONS = _MAF_TODO_INSTRUCTIONS.replace(_MAF_TODO_STEPS, _STEWARD_TODO_STEPS)
# </todo_instructions>


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


# <atlas>
# The door's git tools and record that Steward may call (ADR-0001 items 5 and 6), by their names on the door.
# git_pr since 2026-10-31 (Kyle: "Yes, give it to him"): SecondBrain's door parks his open and merge for
# Kyle's Approve like every other write, so a change goes from his line to main through the door alone.
_ATLAS_GIT_TOOLS = ("git", "git_branch", "git_diff", "git_commit", "git_push", "git_pr", "records")
_STEWARD_WORLD = "steward"


async def steward_world_only(
    context: FunctionInvocationContext,
    call_next: Callable[[], Awaitable[None]],
) -> None:
    """Keep every door call on Steward's own world: MAF's middleware gating (controlling tool availability).

    The door's tools fall back to its default world (research) when no project is named, so a door call
    that names another world, or none, is answered with corrective feedback and never reaches the door.
    """
    if context.function.name.startswith("atlas_"):
        project = context.arguments.get("project") if hasattr(context.arguments, "get") else None
        if project != _STEWARD_WORLD:
            context.result = (
                f"Error: Atlas's door tools work only on your own repository. Call {context.function.name} "
                f"again with project=\"{_STEWARD_WORLD}\"."
            )
            return
    await call_next()


# </atlas>


# <plan_mode>
# Kyle, 2026-11-01 ("MAF says to have it in, don't skip it"): plan mode as the guide builds it. MAF's own
# mode_set stays (the guide never hides it), and the plan is presented as the guide's console presents it,
# PlanningResponse structured output in plan mode, set by the host (console_app.py's planning observer,
# hosted.py's plan_mode_turns). His rules go in through MAF's own options: the todo text (TodoProvider
# instructions=) and the plan-mode text (AgentModeProvider mode_instructions=, "Customize modes with
# AgentModeProvider(mode_instructions={...})"). Tools stay offered in every mode, as in MAF: the approvals
# are the gate (writes, git_commit and the shell each ask), and the tool policy is stated in the plan-mode
# text (the cookbook: "State a tool policy inside the instructions"). evals.py's plan-before-act cases check
# that he follows it.
_PLAN_MODE = "plan"
_EXECUTE_MODE = "execute"
_CHANGES_THINGS = frozenset({
    *FileAccessProvider._WRITE_TOOL_NAMES,  # MAF's own set: file_access_write, _replace, _replace_lines, _delete
    "git_commit",
    "run_shell",
    # Skill scripts are not here (Kyle, 2026-10-31: "unless he has an actual skill he is calling, there is no
    # simple task"): a matching skill is followed directly, and its scripts keep their own approval card.
    *(f"atlas_{name}" for name in ("git_branch", "git_commit", "git_push", "git_pr")),
})
PLAN_MODE_TOOL_POLICY = (
    "\n\nTool policy in plan mode: you have the tools that change things ("
    + ", ".join(sorted(_CHANGES_THINGS))
    + "), and each asks the user's approval when called. In plan mode do not call them. Add the work as todos "
    "(todos_add), then present the plan for the user's approval. Once the user approves, you are in execute "
    "mode, and you use those tools to do the todos."
)
_MAF_MODE_INSTRUCTIONS = AgentModeProvider().mode_instructions
# Gate run 2 (2026-11-01): in plan mode he edited a file as an "exploratory check", MAF's plan step 3. The
# rule goes in that step, where he acts on it: explore with tools that only read.
_MAF_PLAN_STEP_3 = (
    "3. If needed, use the provided tools to do some exploratory checks to help build a plan and determine "
    "what clarifying questions you may need from the user.\n"
)
_STEWARD_PLAN_STEP_3 = (
    "3. If needed, use the provided tools that only read (file_access_read, file_access_read_lines, "
    "file_access_ls, file_access_grep, get_repo_status) to do some exploratory checks to help build a plan and "
    "determine what clarifying questions you may need from the user. Never call a tool that changes things in "
    "plan mode: the change itself is a todo in the plan.\n"
)
if _MAF_PLAN_STEP_3 not in _MAF_MODE_INSTRUCTIONS[_PLAN_MODE]:
    # MAF changed its plan-mode text: refuse to start rather than lose the rule.
    raise RuntimeError("MAF's plan-mode instructions changed; update _MAF_PLAN_STEP_3 in agent.py.")
STEWARD_MODE_INSTRUCTIONS = {
    **_MAF_MODE_INSTRUCTIONS,
    _PLAN_MODE: _MAF_MODE_INSTRUCTIONS[_PLAN_MODE].replace(_MAF_PLAN_STEP_3, _STEWARD_PLAN_STEP_3)
    + PLAN_MODE_TOOL_POLICY,
}


# Session state set when the harness returns him to plan mode because every todo is done; read once by plan_reply_loop.
RETURNED_TO_PLAN_KEY = "steward_returned_to_plan"


class ReturnToPlanWhenDone(ContextProvider):
    """Back to plan mode once no todo is open after an execute run (Kyle, 2026-10-31), so each request is planned.

    The application changing the mode, as MAF's Learn page allows ("Applications can also change the mode
    directly, which causes the provider to inject a mode-change notification on the next run").
    """

    def __init__(self, mode_provider: AgentModeProvider, todo_provider: TodoProvider) -> None:
        super().__init__("return-to-plan")
        self._modes = mode_provider
        self._todos = todo_provider

    async def after_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        if session is None:
            return
        mode = get_agent_mode(
            session,
            source_id=self._modes.source_id,
            default_mode=self._modes.default_mode,
            available_modes=self._modes.available_modes,
        )
        if mode != _EXECUTE_MODE:
            return
        # Not while the run waits on an approval card: that run is paused, not finished.
        response = getattr(context, "response", None)
        if response is not None and any(
            c.type == "function_approval_request" for m in response.messages for c in m.contents
        ):
            return
        items = await self._todos.store.load_items(session, source_id=self._todos.source_id)
        # Only when there was a plan and all of it is done.
        if items and all(item.is_complete for item in items):
            set_agent_mode(session, _PLAN_MODE, source_id=self._modes.source_id, available_modes=self._modes.available_modes)
            # The work is done: the harness loop does not ask this run for a plan (plan_reply_loop).
            session.state[RETURNED_TO_PLAN_KEY] = True


# Gate run 4 (2026-11-01): with the rule stated in plan step 3 he still edited files in plan mode, 3 runs of 5.
# The cookbook's answer when a rule is present but not followed is a deterministic gate in code ("A gate: do
# not move on until the required files exist"): in plan mode a tool that changes things is refused with
# corrective feedback, so he plans instead. Tools stay offered, as in MAF. MAF asks a tool's approval before
# function middleware runs, so the refusal must come without a card, or the user would click Allow and then
# see a refusal: in plan mode MAF's auto-approval rule lets such a call past the card, and the function
# middleware then refuses it. The refusal checks the run's session and the call's session both, so an
# auto-approved call can never run. In execute mode none of this applies and every write asks as before.
_RUN_SESSION: ContextVar[Any] = ContextVar("steward_run_session", default=None)
PLAN_MODE_REFUSAL = (
    "Refused: you are in plan mode, and {name} changes things. Do not call it yet. Add the work as todos "
    "(todos_add) and present the plan for the user's approval; once the user approves, you are in execute "
    "mode and can call it."
)
PLAN_MODE_TODOS_NOT_DONE = (
    "Refused: you are in plan mode and nothing has been done yet, so no todo is complete. Todos are marked "
    "done in execute mode, after the work is done. Present the plan for the user's approval."
)


def plan_mode_gate(mode_provider: AgentModeProvider) -> tuple[list[Callable[..., Awaitable[None]]], Callable[[Any], bool]]:
    """The plan-mode gate: (middleware for the agent's list, an auto-approval rule)."""

    def in_plan_mode(session: Any) -> bool:
        if session is None:
            return False
        mode = get_agent_mode(
            session,
            source_id=mode_provider.source_id,
            default_mode=mode_provider.default_mode,
            available_modes=mode_provider.available_modes,
        )
        return mode == _PLAN_MODE

    async def remember_run_session(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        # Not reset after the run: a streamed run is consumed after this returns, and its approvals with it.
        _RUN_SESSION.set(context.session)
        await call_next()

    async def refuse_in_plan_mode(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        name = context.function.name
        planning = in_plan_mode(context.session) or in_plan_mode(_RUN_SESSION.get())
        if name in _CHANGES_THINGS and planning:
            context.result = PLAN_MODE_REFUSAL.format(name=name)
            return
        # Gate run 5: after a refusal he marked the todo done. In plan mode nothing has run yet.
        if name == "todos_complete" and planning:
            context.result = PLAN_MODE_TODOS_NOT_DONE
            return
        await call_next()

    def past_the_card_to_be_refused(call: Any) -> bool:
        """Auto-approval rule: in plan mode, a changing call skips the card; refuse_in_plan_mode refuses it."""
        return getattr(call, "name", None) in _CHANGES_THINGS and in_plan_mode(_RUN_SESSION.get())

    return [remember_run_session, refuse_in_plan_mode], past_the_card_to_be_refused


# Gate runs 6 and 8 (2026-11-01): the host asked for PlanningResponse on every call, and still one plan-mode
# reply in about seven came back as prose (the cookbook: a schema "is not guaranteed"). The harness loop
# (create_harness_agent's loop_should_continue, MAF's AgentLoopMiddleware, which already runs execute-mode
# todos) asks once or twice more for the plan when a plan-mode reply holds none, and only for a host that
# asked for it (plan_reply_check). Otherwise the loop is MAF's todos_remaining, unchanged.
PLAN_REPLY_NUDGE = (
    "Your last reply did not hold the plan. Reply now with only the plan for the user's approval, as the "
    "PlanningResponse JSON object: an approval whose message lists your todos in order, or a clarification "
    "with your questions."
)
_PLAN_REPLY_RETRIES = 2
# Gate run 9: he answered a change request in plan mode with no todos at all (Kyle, 2026-10-31: "he should
# have the todo list at all times"). A plan-mode reply with an empty todo list is asked once more.
PLAN_TODOS_NUDGE = (
    "Your todo list is empty. Add the work as todos with todos_add first, each an object with a title, then "
    "present the plan for the user's approval as the PlanningResponse JSON object."
)


def plan_reply_loop(
    mode_provider: AgentModeProvider, plan_reply_check: Callable[[str], Any] | None, todo_provider: TodoProvider | None = None
) -> tuple[Callable[..., Awaitable[Any]], Callable[..., Awaitable[str | None]]]:
    """The harness loop's (should_continue, next_message): the todos and the plan asked for again, then MAF's todo loop."""
    todo_loop = todos_remaining(looping_modes=[_EXECUTE_MODE])

    async def plan_missing(session: Any, last_result: Any, iteration: int) -> str | None:
        """'todos' or 'plan' when a plan-mode reply lacks them, else None."""
        if plan_reply_check is None or session is None or iteration > _PLAN_REPLY_RETRIES:
            return None
        # Live test 2026-11-01: when an execute run finished every todo, ReturnToPlanWhenDone put him back in
        # plan mode, and this loop then asked the finished run for a plan ("All pending todos have been
        # completed", a card with nothing to approve). That run was work done, not a plan to ask for.
        if session.state.pop(RETURNED_TO_PLAN_KEY, False):
            return None
        mode = get_agent_mode(
            session,
            source_id=mode_provider.source_id,
            default_mode=mode_provider.default_mode,
            available_modes=mode_provider.available_modes,
        )
        if mode != _PLAN_MODE or last_result is None:
            return None
        messages = list(getattr(last_result, "messages", None) or [])
        if any(c.type == "function_approval_request" for m in messages for c in m.contents):
            return None  # waiting on a card, not finished
        if todo_provider is not None and not await todo_provider.store.load_items(session, source_id=todo_provider.source_id):
            return "todos"
        last = next((m.text for m in reversed(messages) if m.role == "assistant" and (m.text or "").strip()), "")
        return "plan" if plan_reply_check(last) is None else None

    async def should_continue(*, session: Any = None, last_result: Any = None, iteration: int = 0, **kwargs: Any) -> Any:
        if missing := await plan_missing(session, last_result, iteration):
            return (True, missing)
        return await todo_loop(session=session, last_result=last_result, iteration=iteration, **kwargs)

    async def next_message(*, feedback: str | None = None, **kwargs: Any) -> str | None:
        if feedback == "plan":
            return PLAN_REPLY_NUDGE
        if feedback == "todos":
            return PLAN_TODOS_NUDGE
        return await todos_remaining_message(feedback=feedback, **kwargs)

    return should_continue, next_message


# </plan_mode>


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

    # Kyle, 2026-10-31 (the note plan-steward-context-memory-reads, piece 1): reads run without a card,
    # so the store itself keeps every .env file out (RULE 7): never read, searched or listed, approved or not.
    @staticmethod
    def _is_env(path: str) -> bool:
        return Path(str(path).replace("\\", "/")).name.lower().startswith(".env")

    async def read(self, path: str) -> str | None:
        if self._is_env(path):
            raise ValueError(".env files hold keys and are never read.")
        content = await super().read(path)
        return content.replace("\r\n", "\n") if content is not None else None

    async def search(self, directory: str, regex_pattern: str, glob_pattern: str | None = None, *, recursive: bool = False) -> Any:
        found = await super().search(directory, regex_pattern, glob_pattern, recursive=recursive)
        return [r for r in found if not self._is_env(r.file_name)]

    async def list_children(self, directory: str = "") -> Any:
        return [e for e in await super().list_children(directory) if not self._is_env(e.name)]

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
# The notes Steward reads in the live path (plan-steward-context-memory-reads, piece 2); reads only.
_SECONDBRAIN_NOTES_TOOLS = ("search_notes", "read_note", "list_notes")
# His file memory's one scope, the same in every session (piece 3).
_FILE_MEMORY_SCOPE = "steward"


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
    plan_reply_check: Callable[[str], Any] | None = None,
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
        plan_reply_check: For a host that asks for the guide's PlanningResponse in plan mode (hosted.py's
            plan_mode_turns): reads a reply's plan, or returns None. When a plan-mode reply holds no
            plan, the harness loop asks for it again, at most twice (see plan_reply_loop).

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
        if client is None:
            # Gate run 3 (2026-11-01): a todos_add call Ollama could not parse ("error parsing tool call") ended
            # the whole run. The retry written for that gpt-oss fault was only on the old path; Parts 3 and 4 get it.
            part3_client = _retry_malformed_tool_calls(part3_client)
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
        # ADR-0001 items 5 and 6: Atlas's door. SecondBrain serves the door's tools on the same MCP
        # client Steward already holds (its share key, as a client: reads run, writes park as holds for
        # the operator), and the door carries his repository as the world `steward`. So the door is one
        # more MCPStreamableHTTPTool on that client, with allowed_tools, as MAF's local-MCP page shows.
        # The door keeps its own authorization, as MAF says host tools must. Only the git tools and the
        # record are offered, the pieces of the branch-check-keep loop; steward_world_only keeps every
        # call on his own world.
        if secondbrain_client is not None:
            part3_tools.append(
                await stack.enter_async_context(
                    MCPStreamableHTTPTool(
                        name="atlas",
                        mcp_client=secondbrain_client,
                        tool_name_prefix="atlas",
                        allowed_tools=list(_ATLAS_GIT_TOOLS),
                        approval_mode="never_require",
                        load_prompts=False,
                    )
                )
            )
        part3_providers: list[Any] = [MontyCodeActProvider(approval_mode="never_require")]
        if secondbrain_client is not None:
            # plan-steward-context-memory-reads, piece 2: his notes, to look up the plans and rulings
            # himself (reads, never a card), and his Charter, read through them and put in his
            # instructions before every turn (CharterProvider, design step 1).
            notes = await stack.enter_async_context(
                MCPStreamableHTTPTool(
                    name="secondbrain_notes",
                    mcp_client=secondbrain_client,
                    tool_name_prefix="secondbrain",
                    allowed_tools=list(_SECONDBRAIN_NOTES_TOOLS),
                    approval_mode="never_require",
                    load_prompts=False,
                )
            )
            part3_tools.append(notes)
            part3_providers.append(CharterProvider(notes))
        # plan-steward-context-memory-reads, piece 3: MAF's file memory with one explicit scope, so what
        # he saves in one session is in front of him in the next ("Pass an explicit scope to group
        # memories differently ... across sessions"); the factory's per-session one is switched off.
        part3_providers.append(
            FileMemoryProvider(file_memory_store or FileSystemAgentFileStore(Path.cwd() / "agent-file-memory"), scope=_FILE_MEMORY_SCOPE)
        )
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
        # ADR-0001 item 11 kept file reads on a card in an attended run, because the repo root holds .env.
        # Superseded 2026-10-31 (plan-steward-context-memory-reads, piece 1): a card per read ended his
        # turns at SecondBrain's 20 approval rounds, so LineEndingFileStore keeps .env out and MAF's
        # read-only rule approves the reads in every run; writes still ask. Only an unattended run (evals)
        # also auto-approves skill scripts, as MAF's claw evals do.
        auto_approval_rules: list[Any] = [FileAccessProvider.read_only_tools_auto_approval_rule]
        if part4 and auto_approve_skill_scripts:
            auto_approval_rules.append(SkillsProvider.all_tools_auto_approval_rule)
        # Kyle, 2026-10-31 ("just change the line"): every session starts in plan mode, MAF's own default
        # (the first mode in _mode.py's DEFAULT_MODE_MAP). Plan mode analyses the request, explores with
        # the tools he has, writes the plan to memory and asks approval before mode_set("execute"). Started
        # in execute, he acted at once and reached for files and the shell over the tools in his list
        # (asked to read a note, he searched files and never called secondbrain_read_note).
        # Plan mode first, MAF's default, with his tool policy in the plan-mode text (STEWARD_MODE_INSTRUCTIONS).
        mode_provider = AgentModeProvider(default_mode="plan", mode_instructions=STEWARD_MODE_INSTRUCTIONS)
        # Kyle, 2026-10-31: the todo list at all times; no "simple task" outside a skill (STEWARD_TODO_INSTRUCTIONS).
        todo_provider = TodoProvider(instructions=STEWARD_TODO_INSTRUCTIONS)
        part3_providers.append(ReturnToPlanWhenDone(mode_provider, todo_provider))
        gate_middleware, gate_rule = plan_mode_gate(mode_provider)
        auto_approval_rules.insert(0, gate_rule)
        loop_should_continue, loop_next_message = plan_reply_loop(mode_provider, plan_reply_check, todo_provider)
        return create_harness_agent(
            client=part3_client,
            name="Steward",
            description="Software engineering and development assistant." if part4 else None,
            agent_instructions=PART3_INSTRUCTIONS,
            tools=part3_tools,
            history_provider=history_provider,
            file_access_store=LineEndingFileStore(str(_WORKING_DIR)) if not part4 or enable_file_access else None,
            disable_file_memory=True,  # his scoped FileMemoryProvider is in context_providers
            skills_provider=SkillsProvider(DeduplicatingSkillsSource(skills_source), disable_load_skill_approval=part4),
            background_agents=background_agents,
            auto_approval_rules=auto_approval_rules,
            context_providers=part3_providers,
            middleware=[steward_world_only, *gate_middleware],
            mode_provider=mode_provider,
            todo_provider=todo_provider,
            max_context_window_tokens=65_536,
            max_output_tokens=8_192,
            disable_web_search=True,
            # ADR-0001 item 3, as MAF's harness_research.py sample: in execute mode the harness
            # re-invokes Steward while his todos are still open, reminding him which ones, and stops
            # for any approval; plan mode stays interactive. Ten passes per turn at most.
            loop_should_continue=loop_should_continue,
            loop_next_message=loop_next_message,
            loop_max_iterations=10,
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
