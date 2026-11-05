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

Steward's team on the live build (part 4, every host): Steward himself (the orchestrator, OLLAMA_MODEL, e.g.
gpt-oss:20b: talks to the user, plans, uses tools) and two background agents on his model and client:
    * CodeExplorer     — explores one module read-only.
    * WebResearchAgent — searches the web with SecondBrain's web tools (only when SecondBrain is connected).
The improvement loop's coder (step 6) is its own agent on STEWARD_CODER_MODEL (qwen2.5-coder:14b), in
improvement_loop_workflow.py.

Environment variables:
    OLLAMA_HOST                — Ollama server (defaults to http://localhost:11434)
    OLLAMA_MODEL               — orchestrator model, e.g. gpt-oss:20b
    STEWARD_CODER_MODEL        — coder model (defaults to qwen2.5-coder:14b, the operator's choice 2026-11-03)
    STEWARD_WORKSPACE          — repo or folder Steward works in (defaults to this repo, worlds/steward,
                                 per ADR-0001 item 11: his own code is in reach; reads run without a
                                 card and writes ask, and the file store never reads, searches or
                                 lists a .env file)
    SECONDBRAIN_MCP_URL        — SecondBrain's MCP endpoint, e.g. http://127.0.0.1:43110/mcp
    SECONDBRAIN_MCP_KEY        — its share key (SecondBrain → Settings → Share); never printed
    STEWARD_SAFETY_OBSERVE     — "off" turns off MAF's FIDES in its record-only mode (default on); it only
                                 records, to halo_traces/fides.jsonl, and never refuses or changes a call
    STEWARD_FIDES_ENFORCE      — "on" turns on MAF's FIDES block_on_violation for his sinks (default off): a write,
                                 shell, commit, push or other change called after untrusted content (a web page, a
                                 note, an Estate log) is in his context is refused, and the refusal is his tool result
    STEWARD_CODE_SEARCH        — "off" drops his search_code tool (default on): the workspace's tracked .py and .md
                                 files searched by meaning, embedded on the CPU with embeddinggemma-2:270m; the
                                 vectors are kept in storage/code-search/embeddings.json (gitignored)
    STEWARD_SANDBOX            — "hyperlight" runs CodeAct in MAF's Hyperlight sandbox and closes run_shell once
                                 untrusted content is in his context (default off). Needs Windows Hypervisor
                                 Platform; probed once at start, and if it cannot run, one line is logged and
                                 nothing changes (<sandbox>)
"""

from __future__ import annotations

import ast
import asyncio
import copy
import difflib
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import sys
import time
import tokenize
import unicodedata
import uuid
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Annotated, Any

from agent_framework import (
    Agent,
    AgentContext,
    AgentModeProvider,
    AgentResponse,
    AggregatingSkillsSource,
    BackgroundAgentsProvider,
    CachingSkillsSource,
    ChatContext,
    ChatMiddleware,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    ContextProvider,
    DeduplicatingSkillsSource,
    FileAccessProvider,
    FileHistoryProvider,
    FileMemoryProvider,
    FileSkillsSource,
    FileSystemAgentFileStore,
    HistoryProvider,
    InMemoryCollection,
    InMemoryHistoryProvider,
    MCPSkillsSource,
    FunctionInvocationContext,
    FunctionTool,
    MCPStreamableHTTPTool,
    MemoryContextProvider,
    MemoryFileStore,
    Message,
    MiddlewareTermination,
    ResponseStream,
    SkillsProvider,
    TodoProvider,
    VectorStoreField,
    background_tasks_running,
    background_tasks_running_message,
    create_harness_agent,
    create_vector_search_tool,
    get_agent_mode,
    set_agent_mode,
    todos_remaining,
    todos_remaining_message,
    tool,
    vectorstoremodel,
)
from agent_framework.hyperlight import FileMount as HyperlightFileMount, HyperlightCodeActProvider
from agent_framework.monty import MontyCodeActProvider
from agent_framework_monty import FileMount
from agent_framework.ollama import OllamaChatClient, OllamaEmbeddingClient
from agent_framework.security import (
    IntegrityLabel,
    LabelTrackingFunctionMiddleware,
    PolicyEnforcementFunctionMiddleware,
    SecureMCPToolProxy,
)
from agent_framework.tools import (
    LocalShellTool,
    ShellEnvironmentProvider,
    ShellEnvironmentProviderOptions,
    ShellFamily,
    ShellPolicy,
    ShellRequest,
)
from dotenv import load_dotenv
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from ollama import AsyncClient as OllamaAsyncClient
from pydantic import Field
import httpx2

_STEWARD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_STEWARD_DIR))
from subprocess_script_runner import subprocess_script_runner  # noqa: E402

load_dotenv()
_WORKING_DIR = Path(os.environ.get("STEWARD_WORKSPACE") or _STEWARD_DIR.parents[1]).resolve()
_SKILLS_DIR = _STEWARD_DIR / "skills"
# The fixer's model (the operator, 2026-11-03): qwen2.5-coder:14b, the one coder that sits wholly on the 16 GB card
# at the fixer's 32K window (12.1 GB). Measured that day, one model loaded at a time: it read 227 tok/s on a 2.7K
# prompt and 49 on a 17K one, and wrote 28-46 tok/s. devstral-small-2:24b, the fixer of round 1, was dropped: at 32K
# and at 24K 5-7 of its 41 layers stayed on the CPU, and it wrote 3.5 tok/s.
_CODER_MODEL = os.environ.get("STEWARD_CODER_MODEL", "qwen2.5-coder:14b")
# The context Ollama loads each model with (num_ctx, a chat option). Ollama's own default here is
# 131,072, which put 4 GB of gpt-oss:20b in system RAM: 45.6 tok/s, against 84.6 at 65,536.
# Steward's prompts already reach ~23k tokens, so he keeps 65,536, matching the harness budget below;
# CodeExplorer shares his model and context so Ollama never reloads it between them.
_STEWARD_CONTEXT = 65_536

# Startup diagnostics go through ``logging`` so every host decides where they appear.
logger = logging.getLogger(__name__)
# His telemetry source name (create_harness_agent's otel_provider_name, agent_framework/_harness/_agent.py:537 and :700):
# his invoke_agent spans and metrics carry gen_ai.provider.name "steward", not MAF's "microsoft.agent_framework.harness".
OTEL_PROVIDER_NAME = "steward"

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
- You have skills for code-review, codebase-map, evals (running your own evals), github (lines of
  work, the send and pull requests), improve (fixing one eval failure in an improvement round),
  run-tests and secondbrain-notes. When a request matches a skill,
  load it and
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
# Audit 2026-11-04: git_commit ran `git add --all -- .`, so a commit took every change in the workspace, his or not.
# It now commits only the files his run wrote with MAF's file tools (FileAccessProvider._WRITE_TOOL_NAMES), as
# record_written_files keeps them in the run's session (its state is what MAF checkpoints, so a write made before a
# card's pause is still there after it). git_commit reads them through MAF's context injection (a parameter typed
# FunctionInvocationContext, agent_framework/_tools.py:779-786 and :1186-1187). `git commit --only -- <paths>` commits
# just those paths, whatever else is staged. A file a shell command changed is not his write and is left as it is.
WRITTEN_FILES_KEY = "steward_written_files"


def write_happened(result: Any) -> bool:
    """Whether a MAF file-writing tool's result says it wrote (its success texts, _file_access.py:2286, :2340, :2393,
    :2415), not a refusal. The result is a str or MAF's parsed list of Content."""
    if isinstance(result, list):
        result = "\n".join(str(getattr(c, "text", "") or "") for c in result)
    text = str(result or "")
    return text.startswith("Replaced ") or (text.startswith("File '") and text.endswith(("' written.", "' deleted.")))


def written_files(session: Any) -> list[str]:
    """The workspace-relative files his file tools wrote in this session (record_written_files), in order."""
    if session is None:
        return []
    return list(session.state.get(WRITTEN_FILES_KEY) or [])


async def record_written_files(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Function middleware: each file a MAF write tool wrote is kept in the session (WRITTEN_FILES_KEY), for git_commit.

    Outer to his write refusals (refuse_unicode_punctuation_in_code), so a refused write, whose result is the refusal,
    is not kept."""
    await call_next()
    if context.function.name not in FileAccessProvider._WRITE_TOOL_NAMES or not write_happened(context.result):
        return
    session = context.session or _RUN_SESSION.get()
    arguments = context.arguments
    arguments = arguments.model_dump() if hasattr(arguments, "model_dump") else dict(arguments or {})
    try:
        path = _inside_workspace(str(arguments.get("file_name") or "")).relative_to(_WORKING_DIR).as_posix()
    except ValueError:
        return
    if session is not None and path != ".":
        kept = session.state.setdefault(WRITTEN_FILES_KEY, [])
        if path not in kept:
            kept.append(path)


NOTHING_TO_COMMIT = "Nothing was committed: no file written with the file tools in this run has a change to commit."


# A FIDES sink, declared as Learn's FIDES page declares write_file ("Annotating sink tools": accepts_untrusted False).
@tool(approval_mode="always_require", additional_properties={"accepts_untrusted": False})
def git_commit(
    message: Annotated[str, Field(min_length=1, description="Imperative commit message, e.g. 'Fix total rounding'.")],
    ctx: FunctionInvocationContext | None = None,
) -> str:
    """Commit the files you wrote in this run with the file tools, and nothing else; the user approves before it runs."""
    session = (ctx.session if ctx is not None else None) or _RUN_SESSION.get()
    written = written_files(session)
    changed = set(
        _git("ls-files", "-z", "--modified", "--deleted", "--others", "--exclude-standard", "--", ".").stdout.split("\0")
    )
    paths = [p for p in written if p in changed and not _is_env_file(Path(p))]
    if not paths:
        return NOTHING_TO_COMMIT
    added = _git("add", "--all", "--", *paths)
    if added.returncode != 0:
        return f"git add failed: {added.stderr.strip()}"
    committed = _git("commit", "-m", message, "--only", "--", *paths)
    if committed.returncode != 0:
        return f"git commit failed: {(committed.stdout + committed.stderr).strip()}"
    return f"Committed {_git('rev-parse', '--short', 'HEAD').stdout.strip()}: {message}"


async def invoke_through_middleware(agent: Any, function: FunctionTool, arguments: dict[str, Any], session: Any) -> Any:
    """Run one approved call outside the model's loop as MAF's loop runs it (_tools.py:2329-2392, _auto_invoke_function):
    a FunctionInvocationContext with the session, through the client's and the agent's function middleware
    (FunctionMiddlewarePipeline, in the order AgentMiddlewareLayer.run and _get_function_middleware_pipeline give them,
    _middleware.py:2013-2020 and _tools.py:5709), then FunctionTool.invoke. Returns the result as text."""
    from agent_framework._middleware import FunctionMiddlewarePipeline, categorize_middleware  # noqa: PLC0415

    middleware = [*(getattr(agent.client, "function_middleware", None) or []), *categorize_middleware(agent.middleware)["function"]]
    context = FunctionInvocationContext(function=function, arguments=dict(arguments), session=session)
    outside = _RUN_SESSION.set(session)
    try:
        result = await FunctionMiddlewarePipeline(*middleware).execute(
            context, lambda c: function.invoke(arguments=c.arguments, context=c)
        )
    except MiddlewareTermination:
        result = context.result
    finally:
        _RUN_SESSION.reset(outside)
    if isinstance(result, list):
        return "\n".join(str(getattr(c, "text", "") or "") for c in result)
    return str(result if result is not None else "")


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


def _is_env_file(path: Path) -> bool:
    """A .env file holds keys (RULE 7): the explorer's own tools never read, search or list one, as the file store's
    guard keeps them from the file_access tools (audit 2026-11-04: read_file and search_code had no such check)."""
    return path.name.lower().startswith(".env")


def list_files(path: Annotated[str, "Folder relative to the workspace root, e.g. '.' or 'src'."] = ".") -> str:
    """List the files under a folder in the workspace (recursively, skipping build and VCS folders)."""
    root = _inside_workspace(path)
    files = [
        str(p.relative_to(_WORKING_DIR))
        for p in sorted(root.rglob("*"))
        if p.is_file() and not _is_env_file(p) and not _SKIP_DIRS.intersection(p.relative_to(_WORKING_DIR).parts)
    ]
    return "\n".join(files[:500]) or "(no files)"


def read_file(path: Annotated[str, "File path relative to the workspace root."]) -> str:
    """Read a text file from the workspace, with line numbers."""
    target = _inside_workspace(path)
    if _is_env_file(target):
        raise ValueError(".env files hold keys and are never read.")
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(f"{i:>5}  {line}" for i, line in enumerate(lines[:2000], 1))


def search_code(
    pattern: Annotated[str, "Regular expression to search for."],
    path: Annotated[str, "Folder relative to the workspace root."] = ".",
) -> str:
    """Search the workspace's text files for a regular expression; returns file:line: text matches."""
    regex = re.compile(pattern)
    hits: list[str] = []
    for p in sorted(_inside_workspace(path).rglob("*")):
        if not p.is_file() or _is_env_file(p) or _SKIP_DIRS.intersection(p.relative_to(_WORKING_DIR).parts):
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


# </background>


# <code_search>
# His search_code: the workspace's tracked .py and .md files found by meaning, MAF's RAG way (Learn, agents/rag and
# integrations/by-component/vector-stores, Python pivot): a @vectorstoremodel record in MAF's InMemoryCollection with an
# embedding_generator, exposed with create_vector_search_tool (agent_framework/_vectors.py:2551), approval_mode
# "never_require" as MAF's VectorCollectionContextProvider leaves its search ("get and search don't" ask). The index is
# built on the first search, not at startup, and a file is read again when its mtime changes. The collection is in
# memory; each chunk's vector is kept across restarts in CODE_SEARCH_CACHE, keyed by a hash of the model and the text,
# so only a new or changed chunk is ever embedded. No file-backed MAF collection is installed (the Qdrant, DuckDB and
# SQL connectors are separate packages), so the cache is one JSON file under storage/, which .gitignore already holds.
CODE_SEARCH_ENV = "STEWARD_CODE_SEARCH"
CODE_SEARCH_CACHE = _WORKING_DIR / "storage" / "code-search" / "embeddings.json"
CODE_EMBED_MODEL = "embeddinggemma-2:270m"
# The operator, 2026-11-02: the embedder runs on the CPU, beside the chat model on the GPU (Ollama's num_gpu 0).
CODE_EMBED_OPTIONS: dict[str, Any] = {"num_gpu": 0}
CODE_EMBED_DIMENSIONS = 768  # EmbeddingGemma's vector length; MAF checks every vector against it (_vectors.py:167)
_CODE_SUFFIXES = (".py", ".md")
# Not searched: sample outputs under working/, and the state folders (gitignored anyway) his runs write.
_CODE_SKIP_DIRS = _SKIP_DIRS | {"working", "storage", "halo_traces", "agent-memory", "agent-file-memory"}
_CHUNK_MAX_LINES = 80
_CHUNK_MAX_CHARS = 3_000
_EMBED_BATCH = 16


def code_search_on() -> bool:
    """Whether he has search_code (STEWARD_CODE_SEARCH, on unless "off", "0", "false" or "no")."""
    return os.environ.get(CODE_SEARCH_ENV, "on").strip().lower() not in {"off", "0", "false", "no"}


class CpuOllamaClient(OllamaAsyncClient):
    """Ollama's AsyncClient whose embed always runs on the CPU, given to MAF's OllamaEmbeddingClient as its client=.

    MAF's client forwards only model, input, truncate, keep_alive and dimensions to embed
    (agent_framework_ollama/_embedding_client.py:149-157), so Ollama's options (num_gpu) can only ride on the client.
    And MAF always asks for the vector field's dimensions (_vectors.py:375), which ollama 0.5.3's embed does not take
    (ollama/_client.py:871): it is dropped here, and MAF still checks each vector's length against the field.
    """

    async def embed(self, model: str = "", input: Any = "", truncate: bool | None = None, options: Any = None,
                    keep_alive: float | str | None = None, dimensions: int | None = None) -> Any:
        return await super().embed(
            model=model, input=input, truncate=truncate, options={**(options or {}), **CODE_EMBED_OPTIONS}, keep_alive=keep_alive
        )


def code_embedder() -> OllamaEmbeddingClient:
    """His code embedder: MAF's OllamaEmbeddingClient on CODE_EMBED_MODEL, on the CPU (CpuOllamaClient)."""
    return OllamaEmbeddingClient(model=CODE_EMBED_MODEL, client=CpuOllamaClient(host=os.environ.get("OLLAMA_HOST")))


# The Estate lock (Neiro, worlds/neiro/estate.lock.json): each model's digest as the Estate was locked, and who uses it.
# It is read only, from beside this repo (the Steward repo's parent's parent is the ground).
ESTATE_LOCK = _STEWARD_DIR.parents[1].parent.parent / "worlds" / "neiro" / "estate.lock.json"
_LOCK_USER = "steward"


async def _installed_models() -> dict[str, str]:
    """Ollama's installed models, name to digest: GET /api/tags through ollama's AsyncClient.list, as MAF's Ollama
    client talks to Ollama (agent_framework_ollama builds on ollama.AsyncClient). Five seconds at most."""
    listed = await OllamaAsyncClient(host=os.environ.get("OLLAMA_HOST"), timeout=5).list()
    return {m.model: m.digest or "" for m in listed.models if m.model}


async def warn_model_drift(
    lock_path: Path = ESTATE_LOCK, installed: Callable[[], Awaitable[Mapping[str, str]]] = _installed_models
) -> list[str]:
    """At a host's start: one warning line for each model the Estate lock gives Steward ("used_by": "steward") whose
    installed digest differs from the lock's, or that is not installed. Never fails the start: a missing or unreadable
    lock, or Ollama down, is one info line. Returns the lines logged as warnings."""
    try:
        locked = json.loads(lock_path.read_text(encoding="utf-8")).get("models") or []
    except (OSError, ValueError) as exc:
        logger.info("Model drift not checked: the Estate lock %s could not be read (%s).", lock_path, exc)
        return []
    try:
        present = await installed()
    except Exception as exc:  # noqa: BLE001 - Ollama down or refusing: the start goes on
        logger.info("Model drift not checked: Ollama's model list could not be read (%s).", exc)
        return []
    lines: list[str] = []
    for model in locked:
        name, digest = model.get("name"), model.get("digest")
        if not name or _LOCK_USER not in (model.get("used_by") or []):
            continue
        if name not in present:
            lines.append(f"Model drift: {name} is in the Estate lock but not installed in Ollama.")
        elif digest and present[name] != digest:
            lines.append(f"Model drift: {name} is installed as {present[name][:12]}, the Estate lock has {digest[:12]}.")
    for line in lines:
        logger.warning(line)
    return lines


@vectorstoremodel(collection_name="steward_code")
@dataclass
class CodeChunk:
    """One chunk of a workspace file: a top-level function or class, or a Markdown section (Learn's Hotel sample shape:
    the vector field holds the text to embed until MAF replaces it with its vector)."""

    key: Annotated[str, VectorStoreField("key")]
    path: Annotated[str, VectorStoreField("data", is_indexed=True)]
    start_line: Annotated[int, VectorStoreField("data")]
    end_line: Annotated[int, VectorStoreField("data")]
    text: Annotated[str, VectorStoreField("data")]
    embedding: Annotated[
        str | list[float] | None,
        VectorStoreField("vector", dimensions=CODE_EMBED_DIMENSIONS, distance_function="cosine_similarity"),
    ] = None


def _chunk_starts(path: str, lines: list[str]) -> list[int]:
    """The 1-based lines where a chunk starts: each top-level def or class (its decorators and the comment block right
    above it included) for .py, each heading outside a code fence for .md."""
    starts = {1}
    if path.endswith(".py"):
        try:
            body = ast.parse("\n".join(lines)).body
        except (SyntaxError, ValueError):
            body = []  # unparsable: bounded pieces only
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
                while start > 1 and lines[start - 2].startswith("#"):
                    start -= 1
                starts.add(start)
    else:
        fenced = False
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
            elif not fenced and line.startswith("#"):
                starts.add(number)
    return sorted(starts)


def code_chunks(path: str, text: str) -> list[tuple[int, int, str]]:
    """(start line, end line, text) for each chunk of a file, each at most _CHUNK_MAX_LINES lines and _CHUNK_MAX_CHARS."""
    lines = text.splitlines()
    starts = _chunk_starts(path, lines)
    chunks: list[tuple[int, int, str]] = []
    for start, end in zip(starts, [*starts[1:], len(lines) + 1]):
        piece_start, size = start, 0
        for number in range(start, end):
            size += len(lines[number - 1]) + 1
            if number + 1 == end or number + 1 - piece_start >= _CHUNK_MAX_LINES or size >= _CHUNK_MAX_CHARS:
                body = "\n".join(lines[piece_start - 1 : number])
                if body.strip():
                    chunks.append((piece_start, number, body[:_CHUNK_MAX_CHARS]))
                piece_start, size = number + 1, 0
    return chunks


class CodeIndex:
    """The workspace's code in MAF's InMemoryCollection, searched through MAF's SupportsVectorSearch.search: each search
    first embeds the tracked files that are new or changed (by mtime) and drops the ones that are gone."""

    def __init__(self, root: Path, embedding_generator: Any, cache_path: Path | None = None) -> None:
        self.root = root
        self.cache_path = cache_path
        self.model = str(getattr(embedding_generator, "model", None) or type(embedding_generator).__name__)
        self.collection: InMemoryCollection[str, CodeChunk] = InMemoryCollection(CodeChunk, embedding_generator=embedding_generator)
        self.definition = self.collection.definition  # read by create_vector_search_tool for its filters
        self._files: dict[str, tuple[int, list[str], list[str]]] = {}  # path -> (mtime_ns, its chunk keys, their hashes)
        self._vectors: dict[str, list[float]] | None = None  # the cache: chunk hash -> vector, read at the first search
        self._lock: asyncio.Lock | None = None
        self._lock_loop: Any = None

    def chunk_hash(self, embedded_text: str) -> str:
        """The cache key: the embedding model and the exact text embedded (a chunk's path and body)."""
        return hashlib.sha256(f"{self.model}\0{embedded_text}".encode()).hexdigest()

    def _read_cache(self) -> dict[str, list[float]]:
        if self.cache_path is None or not self.cache_path.is_file():
            return {}
        try:
            vectors = json.loads(self.cache_path.read_text(encoding="utf-8")).get("vectors", {})
        except (OSError, ValueError, AttributeError) as exc:  # a broken cache is only a slower first search
            logger.warning("Code search cache not read (%s): %s", self.cache_path, exc)
            return {}
        return {k: v for k, v in vectors.items() if isinstance(v, list) and len(v) == CODE_EMBED_DIMENSIONS}

    def _write_cache(self, vectors: dict[str, list[float]]) -> None:
        if self.cache_path is None:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            written = self.cache_path.with_suffix(".tmp")
            written.write_text(json.dumps({"model": self.model, "vectors": vectors}), encoding="utf-8")
            written.replace(self.cache_path)
        except OSError as exc:  # a cache that cannot be written never fails his search
            logger.warning("Code search cache not written (%s): %s", self.cache_path, exc)

    def tracked_files(self) -> dict[str, int]:
        """Each tracked .py and .md file under the root (git ls-files), outside the skipped folders, with its mtime."""
        listed = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=self.root, capture_output=True, text=True, timeout=30)
        files: dict[str, int] = {}
        for path in listed.stdout.split("\0") if listed.returncode == 0 else []:
            parts = Path(path).parts
            if not path.endswith(_CODE_SUFFIXES) or _CODE_SKIP_DIRS.intersection(parts) or Path(path).name.startswith(".env"):
                continue
            try:
                files[path] = (self.root / path).stat().st_mtime_ns
            except OSError:
                continue  # deleted in the working tree
        return files

    async def refresh(self) -> list[str]:
        """Read the new and changed files (by mtime) and drop the gone ones; a chunk whose vector is in the cache goes in
        as it is (generate_vectors=False), and only the others are embedded, through MAF's upsert. Returns the paths read."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock, self._lock_loop = asyncio.Lock(), loop
        async with self._lock:
            await self.collection.ensure_collection_exists()
            if self._vectors is None:
                self._vectors = self._read_cache()
            cached_before = len(self._vectors)
            tracked = self.tracked_files()
            read: list[str] = []
            embedded = 0
            for path in [p for p in self._files if p not in tracked]:
                await self.collection.delete(self._files.pop(path)[1])
            for path, mtime in tracked.items():
                if path in self._files and self._files[path][0] == mtime:
                    continue
                if path in self._files:
                    await self.collection.delete(self._files.pop(path)[1])
                text = (self.root / path).read_text(encoding="utf-8", errors="replace")
                records = [
                    CodeChunk(f"{path}:{start}", path, start, end, body, f"{path}\n{body}")
                    for start, end, body in code_chunks(path, text)
                ]
                hashes = [self.chunk_hash(str(r.embedding)) for r in records]
                known = [r for r, h in zip(records, hashes) if h in self._vectors]
                for record in known:
                    record.embedding = self._vectors[self.chunk_hash(str(record.embedding))]
                if known:
                    await self.collection.upsert(known, generate_vectors=False)
                fresh = [(r, h) for r, h in zip(records, hashes) if h not in self._vectors]
                for first in range(0, len(fresh), _EMBED_BATCH):
                    batch = fresh[first : first + _EMBED_BATCH]
                    keys = await self.collection.upsert([r for r, _ in batch])
                    stored = {c.key: c.embedding for c in await self.collection.get(keys, include_vectors=True)}
                    for record, digest in batch:
                        self._vectors[digest] = list(stored[record.key])
                    embedded += len(batch)
                self._files[path] = (mtime, [r.key for r in records], hashes)
                read.append(path)
            # Prune: keep only the vectors of chunks that still exist.
            live = {h for _, _, hashes in self._files.values() for h in hashes}
            pruned = {h: v for h, v in self._vectors.items() if h in live}
            if embedded or len(pruned) != cached_before:
                self._vectors = pruned
                self._write_cache(pruned)
            if read:
                logger.info("Code search: read %d file(s), embedded %d chunk(s).", len(read), embedded)
            return read

    async def search(self, values: Any = None, **kwargs: Any) -> Any:
        await self.refresh()
        return await self.collection.search(values, **kwargs)


_CODE_INDEXES: dict[Path, CodeIndex] = {}


def code_index() -> CodeIndex:
    """One index of the workspace per process: his hosts build Steward per request, and the index outlives each build."""
    if _WORKING_DIR not in _CODE_INDEXES:
        _CODE_INDEXES[_WORKING_DIR] = CodeIndex(_WORKING_DIR, code_embedder(), CODE_SEARCH_CACHE)
    return _CODE_INDEXES[_WORKING_DIR]


def _code_hit(result: Any) -> str:
    chunk = result["record"]
    return f"{chunk.path}:{chunk.start_line}-{chunk.end_line}\n{chunk.text}"


def code_search_tool(index: CodeIndex | None = None) -> FunctionTool:
    """His search_code tool, a fresh one per build (MAF's workflow host refuses a tool shared between requests)."""
    return create_vector_search_tool(
        index or code_index(),
        name="search_code",
        description=(
            "Search the workspace's tracked .py and .md files by meaning, not exact text: returns the 5 closest chunks "
            "(a top-level function or class, or a Markdown section) as path:start-end and the text. Use it to find where "
            "something is done when you do not know its name; use file_access_grep for exact text. The first search "
            "indexes the workspace and can take minutes."
        ),
        approval_mode="never_require",
        top=5,
        result_mapper=_code_hit,
    )


# </code_search>


# <atlas>
# The door's git tools and record that Steward may call (ADR-0001 items 5 and 6), by their names on the door.
# git_pr since 2026-10-31 (Kyle: "Yes, give it to him"): SecondBrain's door parks his open and merge for
# Kyle's Approve like every other write, so a change goes from his line to main through the door alone.
_ATLAS_GIT_TOOLS = ("git", "git_branch", "git_diff", "git_commit", "git_push", "git_pr", "records")
_STEWARD_WORLD = "steward"
# The Estate's repositories, by the names the door addresses them (2026-11-04, Kyle: Steward is the agent of the Estate).
# The door carries research, atlas, secondbrain and steward (SecondBrain electron/door/index.cjs worldsFor); neiro is
# the Estate lock's repository, which the door does not carry yet, so the door itself refuses it by name until it does.
ESTATE_WORLDS: dict[str, str] = {
    "research": "Manjuel, the ground (Desktop\\Research)",
    "atlas": "Aurora, Atlas (atlas/ in the ground)",
    "secondbrain": "Jesster, SecondBrain (worlds/jesster)",
    "steward": "Steward, your own repository (worlds/steward)",
    "neiro": "Neiro, the Estate lock (worlds/neiro)",
}
# The Estate as SecondBrain runs it, served on its MCP to him (SecondBrain electron/estate.cjs, 2026-11-04). The reads
# never ask; the writes always ask the user's card. app_update always asks: one name covers its check and its apply.
# hold_status (2026-11-04, the approvals skill) is the door's read of how one held call ended (SecondBrain
# electron/door/registry.cjs), served on the same MCP; read here beside approvals_history, so the door's gate is not on it.
ESTATE_READS = ("estate_status", "estate_logs", "approvals_history", "hold_status")
ESTATE_ASKS = ("service_control", "ollama_unload", "app_update")


def estate_approval(tools: Sequence[str]) -> dict[str, Any]:
    """MAF's per-tool approval_mode for SecondBrain's Estate tools (MCPSpecificApproval): the writes always ask, the
    reads never do, and any other name asks (default "always_require"), so a tool added later is never let through."""
    return {
        "always_require_approval": [t for t in tools if t not in ESTATE_READS],
        "never_require_approval": [t for t in tools if t in ESTATE_READS],
        "default": "always_require",
    }
# Hard refusals, at run time, whatever card would follow (the ground's RULE 1, RULE 6 and RULE 12; never the Archive).
# One list for both ways he reaches git: his shell (ShellPolicy's denylist, _build_shell) and the door (estate_door_gate,
# which reads the same patterns, and the door's flag pattern, over each argument but a commit message). A pattern is a
# plain str: MAF compiles it on the regex engine, case-insensitively, with a one-second bound (ShellPolicy, _policy.py).
ARCHIVE_PATH = r"(?:Desktop[\\/]+Archive|(?:\.\.[\\/]+)+Archive)(?![\w-])"
ESTATE_GIT_REFUSALS: tuple[tuple[str, str], ...] = (
    (r"\bgit\s+push\b", "a push outside the door (pushes go through atlas_git_push, on the user's card)"),
    (r"\bgit\s+tag\b|\bgit_tag\b", "a tag (tags are the user's)"),
    (r"\bgh\s+release\b|\brelease_step\b", "a release (releases are the user's)"),
    (r"\bgit\s+(?:rebase|filter-branch|filter-repo|replace|update-ref)\b|\bgit\s+commit\b[^|;&]*--amend\b", "a history rewrite"),
    (r"\bgit\s+branch\b[^|;&]*\s-(?:d|D|-delete)\b[^|;&]*\b(?:main|master)\b", "deleting the main line"),
    (ARCHIVE_PATH, "a path under Desktop\\Archive (never reached, never sent)"),
)
# Door tools that are refused by name even if a later change offered them: a tag and a release are the user's alone.
_DOOR_REFUSED = frozenset({"atlas_git_tag", "atlas_release_step"})
_MAIN_LINES = frozenset({"main", "master"})
# The door's git tools take no flags, so one passed in an argument is refused. Not in the shell's list (rm -f, ls --all).
_DOOR_FLAGS = (r"(?:^|\s)(?:--force(?:-with-lease)?|--mirror|--all|--tags|--delete|-f)(?![\w-])", "a force, mirror, all, tags or delete flag")
_DOOR_REFUSALS = (*ESTATE_GIT_REFUSALS, _DOOR_FLAGS)
_DOOR_POLICY = ShellPolicy(denylist=[pattern for pattern, _ in _DOOR_REFUSALS])


def estate_git_refusal(text: str) -> str | None:
    """The reason a door argument is refused (ESTATE_GIT_REFUSALS and the door's flags, matched by MAF's ShellPolicy as
    his shell matches its own), or None."""
    if not str(text).strip():
        return None  # ShellPolicy denies an empty command; an empty argument carries nothing to refuse
    decision = _DOOR_POLICY.evaluate(ShellRequest(command=str(text)))
    if decision.decision == "allow":
        return None
    return next((why for pattern, why in _DOOR_REFUSALS if decision.reason.endswith(pattern)), decision.reason)


async def estate_door_gate(
    context: FunctionInvocationContext,
    call_next: Callable[[], Awaitable[None]],
) -> None:
    """Keep every door call on an Estate repository, and refuse what is never his: MAF's middleware gating.

    The door's tools fall back to its default world (research) when no project is named, so a door call that names
    no Estate repository, or none, is answered with corrective feedback and never reaches the door. A tag or a
    release, closing the main line, and any argument but a commit message that carries a force, mirror, all, tags or
    delete flag or a path under Desktop\\Archive are refused here, before any card (ESTATE_GIT_REFUSALS).
    """
    name = context.function.name
    if name.startswith("atlas_"):
        arguments = context.arguments
        arguments = arguments.model_dump() if hasattr(arguments, "model_dump") else dict(arguments or {})
        project = str(arguments.get("project") or "").strip().lower()
        if project not in ESTATE_WORLDS:
            context.result = (
                f"Error: Atlas's door tools work only on the Estate's repositories ({', '.join(ESTATE_WORLDS)}). Call "
                f"{name} again with project set to one of them; your own is project=\"{_STEWARD_WORLD}\"."
            )
            return
        refusal: str | None = None
        if name in _DOOR_REFUSED:
            refusal = "a tag or a release (the user's alone)"
        elif (
            name == "atlas_git_branch"
            and str(arguments.get("action") or "").strip().lower() in {"close", "delete", "remove"}
            and str(arguments.get("name") or "").strip().lower() in _MAIN_LINES
        ):
            refusal = "closing the main line"
        else:
            refusal = next(
                (why for key, value in arguments.items() if key != "message" and (why := estate_git_refusal(str(value)))),
                None,
            )
        if refusal:
            context.result = f"Refused: {name} would be {refusal}. Nothing was sent to the door; this is never done."
            return
    await call_next()


# A pull request's outcome, seen through the door's one read of it (2026-11-04, Kyle: "make the doors push and PR
# results visible"). A door write parks a hold and answers "HELD: ... parked as hold_<ms>_<n>_<tool>" at once
# (SecondBrain electron/door/registry.cjs heldAnswer); what the hold did is told only to his glass: hold_list and
# hold_answer refuse a client (toolHoldList, toolHoldAnswer), and an answered hold leaves only a line in the world's
# state/holds.jsonl, which no door tool serves. So a push's own outcome cannot be read here yet. A pull request can:
# git_pr's "list" is a read the door runs at once for a client (tools.json reads ["list"], registry.cjs writesFor) and
# answers {"pull_requests": [{number, title, line, into, url, checks}]} for the OPEN ones, checks being one word:
# none, pending, passed or failed (gitctl.cjs prList, prChecks). pr_checks asks it until his Approve has opened the
# pull request and its checks have settled, as the door's own merge waits on them (gitctl.cjs prMerge, every 30 s).
# A tool waiting holds no model (MAF calls the model only between tool calls), and the wait stays under TOOL_CALLS'
# 1800 s pass budget, which MAF checks after a call ends and never cuts one short (_tools.py:1889-1899).
PR_CHECKS_TOOL = "pr_checks"
PR_CHECKS_WAIT_SECONDS = 20 * 60
PR_CHECKS_POLL_SECONDS = 30.0  # the door's own merge asks gh every 30 s (gitctl.cjs gh.poll)
_PR_SETTLED = frozenset({"passed", "failed"})


async def _door_text(door: Any, name: str, **arguments: Any) -> str:
    """One door call's text (MCPTool.call_tool returns MAF Contents); a refusal raised by MCP comes back as its text."""
    try:
        result = await door.call_tool(name, **arguments)
    except Exception as exc:  # noqa: BLE001 - the door's own refusal, reported as it is
        return f"Error: {exc}"
    return result if isinstance(result, str) else "\n".join(getattr(c, "text", "") or "" for c in result)


def pr_checks_tool(door: Any) -> FunctionTool:
    """Steward's pr_checks over the connected door (its MCP tool): a read, so it asks no card."""

    @tool(name=PR_CHECKS_TOOL, approval_mode="never_require")
    async def pr_checks(
        line: Annotated[str, Field(description="The line of work (branch) the pull request is from, e.g. 'fix-discount'.")] = "",
        number: Annotated[int, Field(description="The pull request's number, when you know it; 0 to find it by line.")] = 0,
        project: Annotated[str, Field(description="The Estate repository, as the door names it; your own is 'steward'.")] = _STEWARD_WORLD,
    ) -> str:
        """Wait for a pull request on an Estate repository to be opened and for its checks to finish, then return the result.

        Read-only: it never approves, opens or merges anything. Call it after atlas_git_pr action="open" (it waits for
        the user's Approve to open it) and before you report. It returns JSON: status "passed" or "failed" (the checks
        finished), "closed" (no longer open: merged or closed), or "timed_out" with the last state seen. The door gives
        the checks as one word for the whole pull request, not one result per check.
        """
        if not line.strip() and number <= 0:
            return "Error: name the pull request's line of work (line) or its number."
        project = (project or _STEWARD_WORLD).strip().lower()
        if project not in ESTATE_WORLDS:
            return f"Error: project is one of the Estate's repositories ({', '.join(ESTATE_WORLDS)})."
        clock = asyncio.get_running_loop()
        started = clock.time()
        seen: dict[str, Any] | None = None
        while True:
            text = await _door_text(door, "git_pr", action="list", project=project)
            try:
                listed = json.loads(text).get("pull_requests") or []
            except (ValueError, AttributeError):
                return f"The door did not list the pull requests, so their checks are not known: {text}"
            found = next(
                (p for p in listed if (number > 0 and p.get("number") == number) or (number <= 0 and p.get("line") == line.strip())),
                None,
            )
            waited = round(clock.time() - started)
            if found is not None:
                seen = found
                if found.get("checks") in _PR_SETTLED:
                    return json.dumps({"status": found["checks"], "waited_seconds": waited, "pull_request": found})
            elif seen is not None:
                return json.dumps({"status": "closed", "waited_seconds": waited, "pull_request": seen})
            left = PR_CHECKS_WAIT_SECONDS - (clock.time() - started)
            if left <= 0:
                return json.dumps({
                    "status": "timed_out", "waited_seconds": waited, "pull_request": seen,
                    "note": "not open yet: its open may still wait for the user's Approve" if seen is None else "checks still running",
                })
            await asyncio.sleep(min(PR_CHECKS_POLL_SECONDS, left))

    return pr_checks


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
# Superseded for the workflow's steps 2026-11-05: each step is offered only its own tools (steward_workflow.py,
# offered_in_step); a host without the graph is still offered every tool, and this gate stands behind both.
_PLAN_MODE = "plan"
_EXECUTE_MODE = "execute"
_CHANGES_THINGS = frozenset({
    *FileAccessProvider._WRITE_TOOL_NAMES,  # MAF's own set: file_access_write, _replace, _replace_lines, _delete
    "git_commit",
    "run_shell",
    # Skill scripts are not here (Kyle, 2026-10-31: "unless he has an actual skill he is calling, there is no
    # simple task"): a matching skill is followed directly, and its scripts keep their own approval card.
    *(f"atlas_{name}" for name in ("git_branch", "git_commit", "git_push", "git_pr")),
    # His notes' writes (the secondbrain-notes skill, 2026-11-02): they ask too, so plan mode leaves them alone.
    *(f"secondbrain_{name}" for name in ("write_note", "append_to_note")),
    # The Estate's writes (2026-11-04): a server started, stopped or restarted, a model unloaded, SecondBrain updated.
    *(f"secondbrain_{name}" for name in ESTATE_ASKS),
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
# Regression run 10: the switch to execute is the user's Approve (the gate refuses his own mode_set out of plan
# mode), so step 7 says what MAF itself says when the application does the switching (expose_mode_set=False).
_MAF_PLAN_STEP_7 = (
    "7. When approval is granted, always switch to execute mode (using the `mode_set` tool), "
    "and follow the steps for *Execute mode*."
)
_STEWARD_PLAN_STEP_7 = (
    "7. When the user approves, the application switches you to execute mode; do not call mode_set for it. "
    "Follow the steps for *Execute mode* once the mode has changed."
)
for _step in (_MAF_PLAN_STEP_3, _MAF_PLAN_STEP_7):
    if _step not in _MAF_MODE_INSTRUCTIONS[_PLAN_MODE]:
        # MAF changed its plan-mode text: refuse to start rather than lose the rule.
        raise RuntimeError("MAF's plan-mode instructions changed; update the plan steps in agent.py.")
STEWARD_MODE_INSTRUCTIONS = {
    **_MAF_MODE_INSTRUCTIONS,
    _PLAN_MODE: _MAF_MODE_INSTRUCTIONS[_PLAN_MODE]
    .replace(_MAF_PLAN_STEP_3, _STEWARD_PLAN_STEP_3)
    .replace(_MAF_PLAN_STEP_7, _STEWARD_PLAN_STEP_7)
    + PLAN_MODE_TOOL_POLICY,
}


# Regression runs 5-7 (2026-11-01, SecondBrain connected): asked to map a project, even "with the codebase-map
# skill", he read files by hand and never loaded the skill; asked to research three topics, he called no tool at
# all, or summarised an old memory file; asked for a share of lines, he estimated without CodeAct. Each rule is in
# his instructions and was not followed. The cookbook: "Task-specific guidance injected only when it is needed";
# Kyle's ruling on the harness study (2026-10-20): the model chooses, with "regex ... a fast path". So when the
# request itself clearly asks for one of these, one line naming the tool is added to that turn's instructions;
# he still chooses, and nothing is added when nothing matches. The patterns follow the skills' own descriptions.
# Each entry: (the request's pattern, the line he is given, the tool the work needs). A word inside a path never
# counts (_word): every path in this ground holds "Research", which matched the research pattern (2026-11-01).
def CODEACT_MOUNTS() -> list[FileMount]:
    """CodeAct's view of the files: the workspace's harness folder at /harness, read-only (regression runs 11, 13).

    MAF's Monty CodeAct reads files only through mounts. Read-only, so CodeAct is never a way around a write's card;
    harness/ and not the workspace root, which holds .env (RULE 7). At /harness (Monty's working folder is /), so
    the workspace-relative path he writes, harness/..., opens as it is (run 13: /input/harness was refused to him).
    """
    harness = _WORKING_DIR / "harness"
    return [FileMount(host_path=harness, mount_path="/harness", mode="read-only")] if harness.is_dir() else []


def _word(alternatives: str) -> str:
    return r"(?<![\\/])\b(?:" + alternatives + r")\b(?![\\/])"


REQUEST_HINTS: tuple[tuple[re.Pattern[str], str, tuple[str, ...]], ...] = (
    (
        re.compile(_word("map|codebase-map") + r"|how (?:is|it's) (?:it |this )?structured|where (?:do i|to) start", re.I),
        'This request matches your codebase-map skill: call load_skill("codebase-map") first and follow it, running its script.',
        ("run_skill_script",),
    ),
    (
        re.compile(_word("review"), re.I),
        'This request matches your code-review skill: call load_skill("code-review") first and follow it.',
        (),
    ),
    (
        re.compile(_word("research|latest news"), re.I),
        "This request is web research: start one WebResearchAgent background task per topic "
        "(background_agents_start_task), wait for them, and combine what they found. Never answer it from memory or local files.",
        ("background_agents_start_task",),
    ),
    (
        re.compile(_word("codeexplorer"), re.I),
        "This request names the CodeExplorer agent: start it as a background task (background_agents_start_task), "
        # Regression run 12: his summary named none of the files CodeExplorer read; the guide's CodeExplorer brief
        # asks for a summary "naming files and functions".
        "wait for it, and summarise only what it read, naming the files and functions it found.",
        ("background_agents_start_task",),
    ),
    (
        re.compile(_word("percentage|percent|how many") + r"|\bcount (?:the|how|all)\b", re.I),
        # Kyle, 2026-11-01: a project's lines are its code files' lines, not its README or docs. Run 11: pasting file
        # text into CodeAct truncated it (inventory.py "18"); CodeAct reads harness/ itself (CODEACT_MOUNTS).
        "This request asks for a number: count it with CodeAct (execute_code), never estimate. In CodeAct the "
        "workspace's harness folder opens by its workspace path (harness/...): count each file's lines with "
        "len(open(path).read().splitlines()), and never paste file text into the code. A project's lines are its "
        "code files' lines, not its README or other docs, unless the request says otherwise.",
        ("execute_code",),
    ),
    (
        re.compile(_word("evals?|eval sets?|small asks|diagnosis"), re.I),
        'This request matches your evals skill: call load_skill("evals") first and follow it, running the set once '
        "with run_shell and reporting every line as printed.",
        ("run_shell",),
    ),
    (
        # Not "commit": the workflow's own commit step says it, and his own git_commit is right there.
        re.compile(_word("pull requests?|PRs?|push|branch|line of work|save and send"), re.I),
        'This request matches your github skill: call load_skill("github") first and follow it.',
        (),
    ),
    (
        re.compile(_word("improvement round"), re.I),
        'This request is an improvement round: call load_skill("improve") first and follow it.',
        (),
    ),
    (
        # "the/my/your/all" only: the README eval ask says "how to run its tests" and must not change.
        re.compile(r"\brun (?:the|my|your|all(?: the)?) tests\b", re.I),
        'This request matches your run-tests skill: call load_skill("run-tests") first and follow it.',
        (),
    ),
    (
        re.compile(_word("secondbrain|my notes?|write (?:it|this|that) up"), re.I),
        'This request matches your secondbrain-notes skill: call load_skill("secondbrain-notes") first and follow it.',
        (),
    ),
)
# Regression run 9: in the Agent tab the work runs on the user's Approve turn, which matches no pattern, so a hint
# that lived only on the matching turn never reached the work. The request's hints and the tools they need are kept
# in his session until the work is done (ReturnToPlanWhenDone clears them), and the tools he calls are recorded, so
# the harness loop can check the work used them (the cookbook's evidence-coverage check before finishing).
# The tools a hint requires are the WORK's tools only, never load_skill: in his workflow he reads a skill while
# planning, and the work is checked in the execute step's own session, so a required load_skill read as missing
# and the loop told him to start over (live 2026-11-02: the evals skill, loaded in plan, ran the whole set twice).
HINTS_KEY = "steward_request_hints"
CALLED_KEY = "steward_called_tools"
NUDGED_KEY = "steward_required_nudged"
# A harness-written turn that carries a request (the workflow's execute_message, its repair turn) names the request
# in the message's additional_properties (MAF Message, _types.py), and only that is matched: the rest is the harness's
# own text and his plan. Live 2026-11-04 (evals.py small, run A): the discount ask's plan said "divide the discount
# percent by 100", the number hint matched "percent", and the loop's evidence check sent him to count the harness
# folder's lines in CodeAct; his last reply answered that ("**42**"), not the ask. A repair turn names "" (nothing new).
REQUEST_KEY = "steward_request"


def asked_request(messages: Sequence[Any]) -> str:
    """The request the run's last user turn asks: its REQUEST_KEY when a harness turn names one, else its text."""
    for message in reversed(messages or []):
        if message.role != "user":
            continue
        named = (getattr(message, "additional_properties", None) or {}).get(REQUEST_KEY)
        if isinstance(named, str):
            return named
        if (message.text or "").strip():
            return message.text
    return ""


def unmet_requirements(session: Any) -> list[list[str]]:
    """The stored [hint, tools] pairs with a tool he has not called for this request."""
    if session is None:
        return []
    called = set(session.state.get(CALLED_KEY) or [])
    return [pair for pair in session.state.get(HINTS_KEY) or [] if any(tool not in called for tool in pair[1])]


class RequestHints(ContextProvider):
    """The fast path: task-specific guidance for each REQUEST_HINTS pattern the request matches, kept for its work."""

    def __init__(self) -> None:
        super().__init__("request-hints")

    async def before_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        asked = asked_request(context.input_messages or [])
        matched =[[hint, list(tools)] for pattern, hint, tools in REQUEST_HINTS if pattern.search(asked)]
        # The paths the request names, kept for its work (refuse_a_bare_name_the_request_put_in_a_folder); a turn that
        # names none (a loop nudge, a repair's "") keeps the request's.
        if session is not None and (paths := named_paths(asked)):
            session.state[NAMED_PATHS_KEY] = paths
        if session is None:
            hints = matched
        else:
            stored = session.state.get(HINTS_KEY) or []
            # A new request with new hints replaces them; a loop nudge or a todo title that repeats them does not.
            if matched and any(pair not in stored for pair in matched):
                session.state[HINTS_KEY] = matched
                session.state[CALLED_KEY] = []
                session.state[NUDGED_KEY] = []
            hints = session.state.get(HINTS_KEY) or []
        if hints:
            context.extend_instructions(self.source_id, "## For this request\n\n" + "\n".join(f"- {pair[0]}" for pair in hints))


async def record_called_tools(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Function middleware: each tool he calls, kept for the request's evidence check (unmet_requirements)."""
    session = context.session or _RUN_SESSION.get()
    if session is not None and session.state.get(HINTS_KEY):
        called = session.state.setdefault(CALLED_KEY, [])
        if context.function.name not in called:
            called.append(context.function.name)
    await call_next()


# Live runs 2026-11-01: he calls "totos_add" about as often as "todos_add" (and once "tos_get_remaining"); MAF
# answers "not found" and he retries, a wasted round each time. The name is nowhere in his instructions: the model
# writes it piece by piece and mangles an odd word. The harness absorbs it: before MAF looks a call up, a name
# that is not one of the tools offered but is a clear near match to exactly one of them (score >= 0.8, and 0.1
# ahead of the next) is repaired. Anything unclear is left as it is, so MAF still answers "not found".
_NAME_CUTOFF = 0.8
_NAME_MARGIN = 0.1


def repaired_tool_name(name: str, offered: set[str]) -> str | None:
    """The one offered tool a misspelled name clearly means, or None."""
    if not name or name in offered:
        return None
    scored = sorted(((difflib.SequenceMatcher(None, name, o).ratio(), o) for o in offered), reverse=True)
    if not scored or scored[0][0] < _NAME_CUTOFF:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < _NAME_MARGIN:
        return None
    return scored[0][1]


def _repair_names(contents: Any, offered: set[str]) -> None:
    """Repair, in place, each function_call in contents whose name clearly means one offered tool."""
    for c in contents or []:
        if c.type == "function_call" and (right := repaired_tool_name(c.name, offered)):
            logger.info("Tool name repaired: %s -> %s", c.name, right)
            c.name = right


def names_repaired_as_they_pass(inner: ResponseStream[Any, Any], offered: set[str]) -> ResponseStream[Any, Any]:
    """The model's stream with each function_call's name repaired as its update passes; nothing is held back.

    Read inside a new ResponseStream, as held_back_when_it_could_be_a_call reads it and MAF's MessageInjectionMiddleware
    reads its inner stream (_sessions.py:1520-1541): a stream hook on the context is lost when streamed (see
    recover_text_tool_calls). MAF's loop finds the calls to run in the stream's final response (_tools.py:6168), which
    the injection middleware rebuilds from these updates (_sessions.py:1545-1556); the inner final response is repaired
    in place too, as the history middleware keeps it.
    """
    finals: list[ChatResponse[Any]] = []

    async def repaired() -> Any:
        async for update in inner:
            _repair_names(update.contents, offered)
            yield update
        final = await inner.get_final_response()
        for message in final.messages:
            _repair_names(message.contents, offered)
        finals.append(final)

    return ResponseStream(repaired(), finalizer=lambda updates: finals[-1])


async def repair_tool_names(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Chat middleware: repair clearly misspelled tool names in the model's reply, streamed or not."""
    offered = {n for n in (getattr(t, "name", None) for t in (context.options or {}).get("tools") or []) if n}
    await call_next()
    if isinstance(context.result, ResponseStream):
        # On the stream itself, as recover_text_tool_calls does: the context's stream_* lists are applied before
        # MAF's MessageInjectionMiddleware reads the rest of the chain (_middleware.py:1669, _sessions.py:1581).
        context.result = names_repaired_as_they_pass(context.result, offered)
    elif context.result is not None:
        for message in context.result.messages:
            _repair_names(message.contents, offered)


# Live 2026-11-03 (the diagnosis traces): gpt-oss sometimes ends a turn with a tool call's arguments written as its
# reply, e.g. {"directory":"steward/working","glob_pattern":""} (file_access_ls's), so nothing ran and nothing was
# written. MAF's place for it is chat middleware overriding the result (Learn, agents/middleware/chat-middleware and
# result-overrides): chat middleware runs inside the function-invocation loop (OllamaChatClient's layers,
# FunctionInvocationLayer over ChatMiddlewareLayer: agent_framework_ollama/_chat_client.py:295), and the loop runs the
# calls in the response the middleware hands back (_tools.py, _process_model_function_calls; streamed, the stream's
# final response, _tools.py:6168). So a reply that is one JSON object whose keys fit exactly one offered tool (its
# required parameters <= the keys <= its parameters) becomes that call. Everything else is left as it is: two tools
# that fit (but see 2026-11-04 below: one read-only fit among several), none, an empty object, or a reply that
# is the structured output its call asked for (the plan's JSON). Arguments are only ever the model's own.
# Live eval 2026-11-04 (the discount-bug ask): in the workflow's PLAN step (response_format StewardPlan) he replied
# with file_access_ls's arguments as text and the run ended with no plan card. So a call that asked for a Pydantic
# format is recovered too, but only when the reply does not validate as that format, as MAF itself parses it
# (model_validate_json, agent_framework/_types.py:3075-3079): a valid plan is never made a call. A dict schema is
# left as before (MAF reads any JSON as its value, _types.py:3080-3084, so no reply can be told apart from it).
# Live eval 2026-11-04 (the discount ask, again): the PLAN step's reply was {"file_name": ".../test_inventory.py"},
# which fits file_access_read, file_access_delete and file memory's read and delete, so it was left as text and no plan
# card came. So when several tools fit and exactly one of them is read-only, the reply is that read. Read-only is
# MAF's own word for it, never a name guess: the read-only auto-approval rules of its providers (FileAccessProvider
# _READ_ONLY_TOOL_NAMES, _harness/_file_access.py:2008, and SkillsProvider's, _skills.py:2193), the same rules his build
# hands ToolApprovalMiddleware (READ_ONLY_RULES). A tool that skips its card (approval_mode "never_require") is not
# read-only by that alone: file_memory_delete never asks. A write or delete is never chosen; zero or several read-only
# fits stay his text.
# Steps set 2026-11-04 (head 0016cf4): the PLAN step's last reply was {"edits": [...], "file_name": ".../inventory.py"},
# which fits file_access_replace_lines and file_memory_replace_lines, neither read-only, so it stayed text and no plan
# card came. In a call that asked for a Pydantic format (the plan step: plan_mode_turns' StewardPlan) a write written as
# text is made the call when exactly one of the fits is one of his gated writes (_CHANGES_THINGS), and only so that his
# plan-mode gate (plan_mode_gate's refuse_in_plan_mode) answers it with PLAN_MODE_REFUSAL as its plain tool result:
# "plan first; writes come after approval". It never runs there, and file memory's never-asking write is never chosen.
_FENCED_JSON =re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.S | re.I)
READ_ONLY_RULES: tuple[Callable[[Content], bool], ...] = (
    FileAccessProvider.read_only_tools_auto_approval_rule,
    SkillsProvider.read_only_tools_auto_approval_rule,
)


def is_read_only_tool(name: str) -> bool:
    """Whether MAF's read-only auto-approval rules (READ_ONLY_RULES) approve a local call to the tool named name."""
    call = Content.from_function_call(call_id="read-only", name=name, arguments={})
    return any(rule(call) for rule in READ_ONLY_RULES)


def _pydantic_format(response_format: Any) -> bool:
    """Whether response_format is a Pydantic model, the one kind of structured output a reply can be checked against."""
    from pydantic import BaseModel  # noqa: PLC0415

    return isinstance(response_format, type) and issubclass(response_format, BaseModel)


def is_the_asked_format(text: str, response_format: Any) -> bool:
    """Whether text (fenced or not) validates as the Pydantic response_format its call asked for."""
    if not _pydantic_format(response_format):
        return False
    body = (text or "").strip()
    if fenced := _FENCED_JSON.match(body):
        body = fenced.group(1)
    try:
        response_format.model_validate_json(body)
    except ValueError:  # pydantic's ValidationError is a ValueError
        return False
    return True


def tool_call_in_text(text: str, tools: Sequence[Any], planning: bool = False) -> tuple[str, dict[str, Any]] | None:
    """(tool name, arguments) when text is one JSON object that fits exactly one of the tools, or fits several of which
    exactly one is read-only (is_read_only_tool), or, ``planning``, exactly one is a gated write; else None."""
    body = (text or "").strip()
    if fenced := _FENCED_JSON.match(body):
        body = fenced.group(1)
    if not body.startswith("{"):
        return None
    try:
        arguments = json.loads(body)
    except ValueError:
        return None
    if not isinstance(arguments, dict) or not arguments:
        return None
    schemas = {offered.name: offered.parameters() or {} for offered in tools if isinstance(offered, FunctionTool)}
    return _the_tool_it_fits(arguments, schemas, planning)


def _the_tool_it_fits(
    arguments: dict[str, Any], schemas: Mapping[str, Mapping[str, Any]], planning: bool = False
) -> tuple[str, dict[str, Any]] | None:
    """(tool name, arguments) when the arguments fit exactly one tool's parameter schema (its required keys present, no
    key it lacks), or fit several of which exactly one is read-only (is_read_only_tool), or, ``planning``, exactly one
    is a gated write (_CHANGES_THINGS, which the plan-mode gate refuses); else None."""
    keys = set(arguments)
    fits = {
        name for name, schema in schemas.items()
        if set(schema.get("required") or ()) <= keys <= set(schema.get("properties") or {})
    }
    if len(fits) > 1:
        reads = {name for name in fits if is_read_only_tool(name)}
        gated = {name for name in fits if name in _CHANGES_THINGS}
        fits = reads if reads or not planning else gated
    return (fits.pop(), arguments) if len(fits) == 1 else None


def recovered_tool_call(
    response: ChatResponse[Any], tools: Sequence[Any], response_format: Any = None
) -> ChatResponse[Any] | None:
    """The response with its text-only tool call made a real one (a fresh call_id), or None when it holds none or its
    text is the response_format its call asked for."""
    if any(c.type in ("function_call", "function_approval_request") for m in response.messages for c in m.contents):
        return None
    spoken = [m for m in response.messages if m.role == "assistant" and (m.text or "").strip()]
    if len(spoken) != 1 or is_the_asked_format(spoken[0].text, response_format):
        return None
    if (found := tool_call_in_text(spoken[0].text, tools, planning=_pydantic_format(response_format))) is None:
        return None
    name, arguments = found
    logger.info("Tool call recovered from the reply's text: %s", name)
    call = Content.from_function_call(call_id=f"call_{uuid.uuid4().hex}", name=name, arguments=arguments)
    spoken[0].contents = [*(c for c in spoken[0].contents if c.type != "text"), call]
    return response


def _could_be_a_call(text: str) -> bool:
    """Whether a reply's opening text could be one tool call's arguments: a JSON object, or a fence around one."""
    return text.lstrip().startswith(("{", "```"))


def held_back_when_it_could_be_a_call(
    inner: ResponseStream[Any, Any], tools: Sequence[Any], response_format: Any = None
) -> ResponseStream[Any, Any]:
    """The model's stream, released as it comes unless its first text could be a call's arguments.

    MAF's stream hooks cannot do this: buffering is fixed before the first update is read (ResponseStream
    _ensure_content_configuration_mutable, _types.py:4929), an update transform cannot hold an update back (None keeps
    it, _types.py:4555), and flat_map has no end of stream to release held updates at (Ollama's last update need not
    carry a finish_reason, agent_framework_ollama/_chat_client.py:656). So the stream is read inside a new
    ResponseStream, as MAF's own MessageInjectionMiddleware reads its inner stream (_sessions.py:1520-1541). Updates
    before any text (his reasoning) and every update of a reply that opens with prose or a call pass at once. A reply
    that opens with "{" or a fence is held to its end: then it is released as it came, or, when it was one tool's
    arguments, as that call (its other contents, such as usage, kept). The final response is the inner one, so MAF's
    function loop and history middleware see the same response as before (rewritten in place when recovered). A held
    reply that is the response_format its call asked for is released as it came (recovered_tool_call).
    """
    finals: list[ChatResponse[Any]] = []

    async def released() -> Any:
        held: list[Any] = []
        text = ""
        holding: bool | None = None  # None until the reply's first text or call decides it
        async for update in inner:
            if holding is None:
                if any(c.type in ("function_call", "function_approval_request") for c in update.contents):
                    holding = False
                else:
                    text += update.text or ""
                    if text.strip():
                        holding = _could_be_a_call(text)
            if holding:
                held.append(update)
            else:
                yield update
        final = await inner.get_final_response()
        finals.append(final)
        if not holding:
            return
        if recovered_tool_call(final, tools, response_format) is None:
            for update in held:
                yield update
            return
        for update in held:
            if rest := [c for c in update.contents if c.type != "text"]:
                kept = copy.copy(update)
                kept.contents = rest
                yield kept
        call = next(c for m in final.messages for c in m.contents if c.type == "function_call")
        yield ChatResponseUpdate(contents=[call], role="assistant")

    return ResponseStream(released(), finalizer=lambda updates: finals[-1])


async def recover_text_tool_calls(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Chat middleware: a reply that is only a tool call's arguments runs as that call, streamed or not."""
    options = context.options or {}
    tools = list(options.get("tools") or [])
    response_format = options.get("response_format")
    await call_next()
    # A Pydantic format is checked reply by reply (recovered_tool_call); a dict schema is left alone, as before.
    if not tools or options.get("tool_choice") == "none" or (response_format is not None and not _pydantic_format(response_format)):
        return
    if isinstance(context.result, ResponseStream):
        # On the stream itself, as MAF's PerServiceCallHistoryPersistingMiddleware does (_sessions.py:1802): streamed,
        # MAF's MessageInjectionMiddleware runs the rest of the chain only when its stream is read (_sessions.py:1580),
        # after the pipeline has applied the context's stream_* lists (_middleware.py:1669), so those would be lost.
        # Only a reply that opens like a call is held back (held_back_when_it_could_be_a_call): the call has to reach
        # the caller's transcript, and a streamed update cannot be taken back; prose streams as before. MAF's history
        # middleware, inner to this one, persists the reply first; his hosts' InMemoryHistoryProvider keeps that same
        # Message, rewritten here.
        context.result = held_back_when_it_could_be_a_call(context.result, tools, response_format)
    elif context.result is not None:
        recovered_tool_call(context.result, tools, response_format)


# Bar run A (2026-11-04 22:05Z, head 06657a1, the item_count ask): his last reply was MAF's "Function invocation limit
# reached before a final answer could be produced." MAF's documented way when a limit trips (FunctionInvocationConfiguration,
# _tools.py:1879-1893: "the loop stops invoking tools and forces the model to produce a text response") is one more call
# with tool_choice "none" (_apply_batch_limit_decision, _tools.py:4850-4877), which OllamaChatClient sends without tools
# (agent_framework_ollama/_chat_client.py:483). Nothing tells the model so: on that call (traces 21:58:08Z) he wrote
# todos_complete again, MAF dropped the call it could not run and put its fallback text in (_tools.py:2938-2951). So
# that call carries one line saying the tools are off and the answer is due now, as a call-local message (a new list on
# the context, ChatContext's own messages: _middleware.py:1827-1838); his history and transcript never hold it.
TOOLS_OFF_ANSWER_NOW = (
    "Your tools are off for the rest of this request: no more tool calls can run. Answer the request now, in plain "
    "text, from what you have done: what is done, and what is left."
)


# The bar at 98d54d5 (2026-11-05): runs ended on an empty reply (small run 1's item_count ask: "Last reply misses
# ('item_count',): ''"; one EXECUTE call in the traces came back with no text and no call). An empty last reply is asked
# once more through MAF's harness loop (loop_should_continue/loop_next_message, plan_reply_loop): the next turn's
# message carries ANSWER_NOW_KEY, tools_off_to_answer_now turns that turn's tools off (tool_choice "none", which
# OllamaChatClient sends without tools), and answer_when_tools_are_off adds TOOLS_OFF_ANSWER_NOW, as when a limit trips.
# Not in plan mode, where READ_PLAN (the workflow) or plan_missing (a host's plan_reply_check) asks for the plan
# itself, unless the session answers in words (the workflow's ANSWER step) or his work there is done (returned to plan).
ANSWER_NOW_KEY = "steward_answer_now"
EMPTY_REPLY_NUDGE = "Your last reply was empty."
# A session whose state holds this answers in words: plan_mode_turns asks it for no plan (the workflow's answer step).
IN_WORDS_KEY = "steward_answers_in_words"
# A session whose state holds this reads for a plan (the workflow's EXPLORE step). The bar at 1b56963 (2026-11-05
# 07:55Z, the steps set): EXPLORE listed two folders, its next reply came back empty, and its reading ended there;
# the plan call then answered with reads twice and the run ended with no plan. An empty reply there is asked once to
# go on reading, with its tools on (READ_ON_NUDGE, a loop turn carrying READ_ON_KEY).
READS_FIRST_KEY = "steward_reads_first"
READ_ON_KEY = "steward_read_on"
READ_ON_NUDGE = (
    "Your last reply was empty. Go on reading what the plan needs with your tools (open the files the request is "
    "about), then say in a few lines what you found."
)


def ended_empty(response: Any) -> bool:
    """Whether a run's last assistant message holds no text and no call (or there is no assistant message), or the run
    ended on a tool's result with no reply after it.

    The confirmation bar at 5039e0e (2026-11-05 09:03Z, the item_count ask): after todos_get_remaining the model's
    reply came back with nothing in it, MAF kept no message for it, and the run's last assistant message was the call,
    so the empty reply was not seen and the run ended with no answer."""
    everything = list(getattr(response, "messages", None) or [])
    if everything and everything[-1].role == "tool":
        return True
    messages = [m for m in everything if m.role == "assistant"]
    if not messages:
        return True
    last = messages[-1]
    return not (last.text or "").strip() and not any(
        c.type in ("function_call", "function_approval_request") for c in last.contents
    )


def asks_to_answer_now(messages: Sequence[Any]) -> bool:
    """Whether the last user message is the harness loop's answer-now turn (ANSWER_NOW_KEY)."""
    last = next((m for m in reversed(messages or []) if m.role == "user"), None)
    return bool((getattr(last, "additional_properties", None) or {}).get(ANSWER_NOW_KEY))


async def tools_off_to_answer_now(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Chat middleware: the answer-now turn (asks_to_answer_now) is a call with tool_choice "none"."""
    if asks_to_answer_now(context.messages):
        context.options = {**(context.options or {}), "tool_choice": "none"}
    await call_next()


async def answer_when_tools_are_off(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Chat middleware: the call MAF makes with tool_choice "none" (a limit tripped) asks him for his answer in text.

    Not on a call with a response_format (the workflow's plan call, steward_workflow.plan_phases_turn): its answer is
    that format, which "in plain text" would contradict."""
    options = context.options or {}
    if options.get("tool_choice") == "none" and options.get("response_format") is None:
        context.messages = [*context.messages, Message(role="user", contents=[Content.from_text(TOOLS_OFF_ANSWER_NOW)])]
    await call_next()


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
        # Only when there was a plan and all of it is done, with the tools the request needed (unmet_requirements).
        if items and all(item.is_complete for item in items) and not unmet_requirements(session):
            set_agent_mode(session, _PLAN_MODE, source_id=self._modes.source_id, available_modes=self._modes.available_modes)
            # The work is done: the harness loop does not ask this run for a plan (plan_reply_loop).
            session.state[RETURNED_TO_PLAN_KEY] = True
            for key in (HINTS_KEY, CALLED_KEY, NUDGED_KEY):
                session.state.pop(key, None)


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
PLAN_MODE_SWITCH_REFUSAL = (
    "Refused: only the user's Approve switches you to execute mode. Present the plan for the user's approval; "
    "when the user approves, you are switched to execute mode without calling mode_set."
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
        # Regression run 10 (live, 2026-11-01): in plan mode he called mode_set("execute") himself and went on to
        # run the command, skipping the user's plan card. MAF only instructs the model to use mode_set when the
        # user allows it; the user's Approve switches the session itself (hosted.py, the console: set_agent_mode),
        # so his own mode_set out of plan mode is refused.
        if name == "mode_set" and planning:
            asked = context.arguments.get("mode") if hasattr(context.arguments, "get") else None
            if str(asked or "").strip().lower() != _PLAN_MODE:
                context.result = PLAN_MODE_SWITCH_REFUSAL
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


# Regression run 9: the cookbook's evidence-coverage check before finishing. When execute-mode work would end
# without a tool its request needs, the loop asks once, naming it (unmet_requirements).
REQUIRED_TOOLS_NUDGE = "Before you finish: this request needs a tool you have not used yet. Do this now, then finish:"
# Live 2026-11-04: his answer was complete but the plan's todos were open, so MAF's open-todo reminder
# (todos_remaining_message, "Continue working through them now") re-ran him, and he gave the same answer again. The
# reminder now says his words are already shown (the Agent tab also holds back a repeat: repeats_what_was_shown).
TODOS_ALREADY_SHOWN = (
    "Your replies so far are already shown to the user. If that work is done, mark those todos complete with "
    "todos_complete; do not repeat your answer, and say only what is new."
)
# A passage after a nudge is a repeat when at least this share of it is runs of at least this many characters
# already shown (whitespace collapsed). Live 2026-11-04: the repeated table was most of the second passage.
_REPEAT_SHARE = 0.5
_REPEAT_MIN_RUN = 20


def said_something(result: Any) -> bool:
    """Whether a loop iteration's result holds his own words (an assistant message with text)."""
    return any(m.role == "assistant" and (m.text or "").strip() for m in getattr(result, "messages", None) or [])


def repeats_what_was_shown(shown: str, words: str) -> bool:
    """Whether ``words`` (his passage after a loop nudge) mostly repeats ``shown`` (what the tab already shows)."""
    new, old = " ".join(words.split()), " ".join(shown.split())
    if not new or not old:
        return False
    blocks = difflib.SequenceMatcher(None, old, new, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks if b.size >= _REPEAT_MIN_RUN) >= _REPEAT_SHARE * len(new)


async def answer_once(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """A non-streaming run's response holds his answer once, and only his own words (2026-11-04, after PR #93).

    MAF's AgentLoopMiddleware returns a non-streaming run as one combined response: "each iteration's response
    messages plus the injected 'nudge' messages" (_harness/_loop.py, _process_non_streaming, then _aggregate_response,
    since return_final_only defaults to False). So when the open-todo reminder re-ran him after a complete answer, the
    MCP door's text (AgentResponse.text, every message's text) carried the reminder and the answer twice. Here, outside
    the loop, the loop's own user messages are dropped, as the Agent tab drops them (hosted._only_his_own_words), and a
    passage after a nudge that repeats what is already given (repeats_what_was_shown, the tab's rule) loses its text;
    his tool calls stay. A streamed run is the Agent tab's, which holds the repeat back itself.
    """
    await call_next()
    result = context.result
    if context.stream or not isinstance(result, AgentResponse):
        return
    given: list[str] = []
    kept: list[Message] = []
    nudged = False
    for message in result.messages:
        if message.role == "user":  # the loop's next_message: in an aggregate, only the loop adds user messages
            nudged = True
            continue
        text = message.text
        if nudged and text and repeats_what_was_shown("\n".join(given), text):
            contents = [c for c in message.contents if c.type != "text"]
            if not contents:
                continue
            message = copy.copy(message)  # the run's own message is not changed in place
            message.contents = contents
        elif text:
            given.append(text)
        kept.append(message)
    result.messages = kept


def denied_by_user(messages: Any) -> bool:
    """Whether a run's input carried the user's No on a card (MAF's loop passes that input as messages=).

    Live run 2026-11-01: a plan step he was denied (an unasked commit) stayed an open todo, so MAF's todos_remaining
    sent him back to it, card after card, until the run was stopped. The user's No ends the run; what is left is
    reported, not retried.
    """
    return any(
        c.type == "function_approval_response" and not c.approved
        for m in messages or []
        for c in getattr(m, "contents", None) or []
    )


def plan_reply_loop(
    mode_provider: AgentModeProvider, plan_reply_check: Callable[[str], Any] | None, todo_provider: TodoProvider | None = None
) -> tuple[Callable[..., Awaitable[Any]], Callable[..., Awaitable[str | None]]]:
    """The harness loop's (should_continue, next_message): the todos and the plan asked for again, then MAF's todo loop,
    then MAF's background-task loop."""
    todo_loop = todos_remaining(looping_modes=[_EXECUTE_MODE])
    # Step 4, 4.4: a turn could end while a background agent (CodeExplorer, WebResearchAgent) still ran. MAF's
    # background_tasks_running keeps the loop going while one does, and background_tasks_running_message names the
    # running tasks; checked last, so with no task running the loop is exactly as before. loop_max_iterations bounds it.
    background_loop = background_tasks_running()

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
            # Live run 14 (2026-11-01): todos_add succeeded, yet this read the list empty and nudged a good plan into
            # "{}"; not reproduced on the hosted server with a scripted model, so the cause is unproven. His own run
            # showing todos_add wins over the store, and the mismatch is logged for the next time.
            added = any(c.type == "function_call" and c.name == "todos_add" for m in messages for c in m.contents)
            if not added:
                return "todos"
            logger.warning(
                "Plan loop: todos_add ran in this run but the todo store reads empty (session %s); not nudged.",
                getattr(session, "session_id", None),
            )
        last = next((m.text for m in reversed(messages) if m.role == "assistant" and (m.text or "").strip()), "")
        return "plan" if plan_reply_check(last) is None else None

    def required_missing(session: Any, last_result: Any) -> bool:
        """In execute mode, a finished run that did not use a tool its request needs, not yet asked about."""
        if session is None:
            return False
        mode = get_agent_mode(
            session,
            source_id=mode_provider.source_id,
            default_mode=mode_provider.default_mode,
            available_modes=mode_provider.available_modes,
        )
        if mode != _EXECUTE_MODE:
            return False
        messages = list(getattr(last_result, "messages", None) or [])
        if any(c.type == "function_approval_request" for m in messages for c in m.contents):
            return False  # waiting on a card, not finished
        nudged = session.state.setdefault(NUDGED_KEY, [])
        fresh = [pair for pair in unmet_requirements(session) if pair[0] not in nudged]
        if not fresh:
            return False
        nudged.extend(pair[0] for pair in fresh)
        return True

    def answer_missing(session: Any, last_result: Any, messages: Any) -> bool:
        """A finished run whose last reply is empty, not already the answer-now turn, and not a plan to ask for."""
        if session is None or not ended_empty(last_result) or asks_to_answer_now(messages):
            return False
        mode = get_agent_mode(
            session,
            source_id=mode_provider.source_id,
            default_mode=mode_provider.default_mode,
            available_modes=mode_provider.available_modes,
        )
        return mode != _PLAN_MODE or bool(session.state.get(IN_WORDS_KEY)) or bool(session.state.get(RETURNED_TO_PLAN_KEY))

    def reading_stopped(session: Any, last_result: Any, messages: Any) -> bool:
        """A reading session (READS_FIRST_KEY) whose reply came back empty after it had begun reading (a tool call in
        this run), not already after READ_ON_NUDGE."""
        if session is None or not session.state.get(READS_FIRST_KEY) or not ended_empty(last_result):
            return False
        if not any(c.type == "function_call" for m in getattr(last_result, "messages", None) or [] for c in m.contents):
            return False  # nothing read yet: the plan call is asked for the plan, as before (ReadPlan)
        last = next((m for m in reversed(messages or []) if m.role == "user"), None)
        return not (getattr(last, "additional_properties", None) or {}).get(READ_ON_KEY)

    async def should_continue(*, session: Any = None, last_result: Any = None, iteration: int = 0, **kwargs: Any) -> Any:
        if denied_by_user(kwargs.get("messages")):
            return False
        if reading_stopped(session, last_result, kwargs.get("messages")):
            return (True, "read on")
        if missing := await plan_missing(session, last_result, iteration):
            return (True, missing)
        if await todo_loop(session=session, last_result=last_result, iteration=iteration, **kwargs):
            return True
        if required_missing(session, last_result):
            return (True, "required")
        if background_loop(session=session, last_result=last_result, iteration=iteration, **kwargs):
            return (True, "background")
        if answer_missing(session, last_result, kwargs.get("messages")):
            return (True, "answer")
        return False

    # Every turn the loop writes names no request (REQUEST_KEY ""), so RequestHints never matches the loop's own words.
    # The bar at 416ba41 (2026-11-05 04:57Z, the discount ask): the open-todo reminder quoted the plan's todo,
    # "interpret discount_percent as a percentage", the number hint matched "percentage", and the evidence check then
    # sent him to count the harness folder's lines in CodeAct; his last reply asked to run that, not the fix.
    def loop_turn(text: str | None, **properties: Any) -> Message | None:
        if not text:
            return None  # MAF's loop: None reuses the previous messages, as todos_remaining_message's None did
        return Message(role="user", contents=[Content.from_text(text)], additional_properties={**properties, REQUEST_KEY: ""})

    async def next_message(*, feedback: str | None = None, session: Any = None, **kwargs: Any) -> Any:
        if feedback == "read on":
            return loop_turn(READ_ON_NUDGE, **{READ_ON_KEY: True})
        if feedback == "answer":
            return loop_turn(EMPTY_REPLY_NUDGE, **{ANSWER_NOW_KEY: True})
        if feedback == "plan":
            return loop_turn(PLAN_REPLY_NUDGE)
        if feedback == "todos":
            return loop_turn(PLAN_TODOS_NUDGE)
        if feedback == "required":
            lines = "\n".join(f"- {pair[0]}" for pair in unmet_requirements(session))
            return loop_turn(f"{REQUIRED_TOOLS_NUDGE}\n{lines}")
        if feedback == "background":
            return loop_turn(background_tasks_running_message(session=session, **kwargs))
        reminder = await todos_remaining_message(feedback=feedback, session=session, **kwargs)
        # Only when he has said something: the bar at e532fea (2026-11-05 08:46Z, the README ask) had an empty reply,
        # the reminder still said "your replies are already shown ... say only what is new", and after the write his
        # whole answer was "Todos marked complete."
        return loop_turn(f"{reminder}\n\n{TODOS_ALREADY_SHOWN}" if reminder and said_something(kwargs.get("last_result")) else reminder)

    return should_continue, next_message


# </plan_mode>


# <shell>
def _shell_text_copies() -> None:
    """MAF's shell text (_ShellResultText, agent-framework-tools 1.0.0b261022) is a str built from its ShellResult,
    with no __reduce__, so copy and pickle rebuild it from the plain text and fail ("'str' object has no attribute
    'format_for_model'"). A workflow deep-copies every streamed update (WorkflowContext.yield_output), so an approved
    run_shell inside Steward's workflow failed the whole run (live, 2026-11-01). Rebuilt from its ShellResult, as its
    own __new__ takes it; nothing else about the tool changes."""
    from agent_framework_tools.shell._types import _ShellResultText  # noqa: PLC0415

    _ShellResultText.__reduce__ = lambda self: (_ShellResultText, (self.shell_result,))  # type: ignore[method-assign]


_shell_text_copies()


def _own_python_env() -> dict[str, str] | None:
    """His shell's environment with his own virtual environment active, as any developer's terminal for this repo
    is: `python`, `pip` and `pytest` resolve to the Python Steward runs on (sys.prefix), not the system one (live
    2026-11-02: he ran `python .../evals.py` and the system Python had no agent_framework). None when he runs outside
    a venv. shell_env puts it over the variables his shell is given.
    """
    if sys.prefix == sys.base_prefix:
        return None
    scripts = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    return {"VIRTUAL_ENV": sys.prefix, "PATH": str(scripts) + os.pathsep + os.environ.get("PATH", "")}


# Audit 2026-11-04: his shell inherited this process's environment after load_dotenv(), so every command could read
# SECONDBRAIN_MCP_KEY (RULE 7). MAF's LocalShellTool takes clean_env=True: "do not inherit os.environ; only the
# variables supplied in env are visible to commands" (agent_framework_tools/shell/_tool.py:124-125, :194-200), and the
# persistent shell starts with exactly that env (_session.py:180-185). So the shell gets only these names: what Windows,
# Git Bash, git, Python and pytest need to run, and his own Python first (_own_python_env). A name .env sets is never
# passed, nor one that reads as a secret, whatever the list says; a Python script he runs that needs .env reads it itself.
SHELL_ENV_NAMES = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "OS", "TEMP", "TMP", "TMPDIR",
    "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USER", "LOGNAME", "USERDOMAIN", "COMPUTERNAME",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "NUMBER_OF_PROCESSORS", "LANG", "LANGUAGE", "TERM", "SHELL", "TZ", "VIRTUAL_ENV",
})
SHELL_ENV_PREFIXES = ("PYTHON", "LC_")
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH", re.I)


def dotenv_names() -> set[str]:
    """The names the workspace's .env sets (the file load_dotenv() read), upper-cased; never their values."""
    from dotenv import dotenv_values, find_dotenv  # noqa: PLC0415

    found = find_dotenv()
    return {name.upper() for name in dotenv_values(found)} if found else set()


def shell_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The only variables his shell's commands see (MAF's clean_env): SHELL_ENV_NAMES and the SHELL_ENV_PREFIXES ones
    from this process, with his own Python first, never a name .env sets or a secret-looking one."""
    environ = os.environ if environ is None else environ
    withheld = dotenv_names()
    kept = {
        name: value
        for name, value in environ.items()
        if (name.upper() in SHELL_ENV_NAMES or name.upper().startswith(SHELL_ENV_PREFIXES))
        and name.upper() not in withheld
        and not _SECRET_NAME.search(name)
    }
    if own := _own_python_env():
        kept.update(own)
    return kept


def _build_shell() -> LocalShellTool:
    """Build a shell confined to the workspace, with his own Python first and none of this process's keys (shell_env);
    every command is surfaced for approval."""
    return LocalShellTool(
        env=shell_env(),
        clean_env=True,
        # Kyle, 2026-10-29: bash (Git Bash) by preference, through MAF's own shell override. Elsewhere (the gate's
        # Linux runner) MAF's own default, which resolves to /bin/bash (agent_framework_tools/shell/_resolve.py).
        shell=[r"C:\Program Files\Git\bin\bash.exe"] if os.name == "nt" else None,
        mode="persistent",
        workdir=str(_WORKING_DIR),
        confine_workdir=True,
        policy=ShellPolicy(
            denylist=[
                r"\brm\s+-[a-z]*r",
                r"\bRemove-Item\b.*-Recurse",
                r"\bdel\s+/s\b",
                # A push, a tag, a release, a history rewrite, deleting main, the Archive (ESTATE_GIT_REFUSALS).
                *(pattern for pattern, _ in ESTATE_GIT_REFUSALS),
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


# <sandbox>
# STEWARD_SANDBOX=hyperlight (off by default; the operator, 2026-11-04: "go for it"): MAF's Hyperlight sandbox
# (agent-framework-hyperlight 1.0.0b261030, hyperlight-sandbox 0.8.0), a micro-VM per run on Windows Hypervisor Platform.
#   * CodeAct: HyperlightCodeActProvider in place of MontyCodeActProvider, which "Mirrors
#     agent_framework_hyperlight.HyperlightCodeActProvider" (agent_framework_monty/_provider.py:23). Given no host tools,
#     as Monty is (FIDES does not see host-tool calls inside generated code). Its files are mounts under /input, copied
#     into a per-sandbox temp folder (_execute_code_tool.py:645-658, :805-813), so harness/ is read-only to it, as to Monty.
#   * The shell: MAF's own advice is "For untrusted input prefer a sandboxed executor (e.g. DockerShellTool or
#     HyperlightCodeActProvider)" (agent_framework_tools/shell/_tool.py:178-181; _policy.py:34). Hyperlight's guest runs
#     Python, not bash, so a run_shell after untrusted content (a web page, a note, an Estate log) is not run on the host:
#     SANDBOX_SHELL_REFUSAL is his tool result and sends the step to execute_code. "Untrusted" is FIDES's own context label
#     (LabelTrackingFunctionMiddleware puts it in context.metadata["context_label"], security.py:1976-1977) when FIDES is
#     wired, and in any case a call this session made to one of the untrusted sources (_SANDBOX_UNTRUSTED_SOURCES).
#   * The probe, once per process: what MAF's registry does on first use (_SandboxRegistry._build_sandbox,
#     _execute_code_tool.py:1502-1516): a Sandbox on the wasm backend, then run("None"). The backend's native module loads
#     winhvplatform.dll and fails with "Windows Hypervisor Platform is not available on this system". Never run when the
#     switch is off: importing the guest (python_guest.path) copies it to %LOCALAPPDATA% (python_guest/path.py:51).
#   * Off, or unavailable: one line is logged ("Hyperlight sandbox off: <reason>") and the build is today's exactly.
SANDBOX_ENV = "STEWARD_SANDBOX"
SANDBOX_OFF = "Hyperlight sandbox off: %s"
SANDBOX_SHELL_REFUSAL = (
    "run_shell did not run: untrusted content (a web page, a note or an Estate log) is in your context and the "
    "Hyperlight sandbox is on (STEWARD_SANDBOX=hyperlight), so no command runs on the host for the rest of this session. "
    "Do this step in Python with execute_code, which runs in the sandbox (the workspace's harness folder is at "
    "/input/harness), or tell Kyle it needs the shell and a new session."
)
_SANDBOX_UNTRUSTED_KEY = "steward_untrusted_in_context"
_SANDBOX_STATE: dict[str, bool] = {}  # the probe's answer, once per process


def _probe_hyperlight() -> None:
    """Start MAF's Hyperlight sandbox as its registry does on first use, and run nothing; raises when it cannot run."""
    from hyperlight_sandbox import Sandbox  # noqa: PLC0415

    Sandbox(backend="wasm").run("None")


def hyperlight_sandbox_on() -> bool:
    """Whether CodeAct and the untrusted shell go through Hyperlight: STEWARD_SANDBOX is "hyperlight" and the probe ran.
    Decided once per process; when it is off, one line says why. Never raises."""
    if "on" not in _SANDBOX_STATE:
        reason = None
        if os.environ.get(SANDBOX_ENV, "").strip().lower() != "hyperlight":
            reason = f"{SANDBOX_ENV} is not hyperlight"
        else:
            try:
                _probe_hyperlight()
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as exc:  # noqa: BLE001 - a PyO3 panic is a BaseException; start never fails
                text = str(exc).strip().splitlines()
                reason = f"{type(exc).__name__}: {text[0] if text else 'no message'}"
        if reason is None:
            logger.info("Hyperlight sandbox on: CodeAct and the shell after untrusted content run in it.")
        else:
            logger.warning(SANDBOX_OFF, reason)
        _SANDBOX_STATE["on"] = reason is None
    return _SANDBOX_STATE["on"]


def HYPERLIGHT_MOUNTS() -> list[HyperlightFileMount]:
    """CODEACT_MOUNTS for Hyperlight: the harness folder at /input/harness (its mounts live under /input)."""
    harness = _WORKING_DIR / "harness"
    return [HyperlightFileMount(host_path=harness, mount_path="harness")] if harness.is_dir() else []


def codeact_provider() -> ContextProvider:
    """His CodeAct: MAF's Hyperlight provider when the sandbox is on (hyperlight_sandbox_on), else Monty, as before."""
    if hyperlight_sandbox_on():
        return HyperlightCodeActProvider(approval_mode="never_require", file_mounts=HYPERLIGHT_MOUNTS())
    return MontyCodeActProvider(approval_mode="never_require", file_mounts=CODEACT_MOUNTS())


async def sandbox_untrusted_shell(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Function middleware, innermost (inside FIDES's label tracker), only when the sandbox is on: a run_shell called
    with untrusted content in his context gets SANDBOX_SHELL_REFUSAL and runs nothing; a call to an untrusted source marks
    the session."""
    name = context.function.name
    session = context.session or _RUN_SESSION.get()
    if name == "run_shell":
        label = context.metadata.get("context_label")
        seen = session is not None and bool(session.state.get(_SANDBOX_UNTRUSTED_KEY))
        if seen or getattr(label, "integrity", None) == IntegrityLabel.UNTRUSTED:
            context.result = SANDBOX_SHELL_REFUSAL
            return
    await call_next()
    if name in _SANDBOX_UNTRUSTED_SOURCES and session is not None:
        session.state[_SANDBOX_UNTRUSTED_KEY] = True


# </sandbox>


# <ollama_options>
# Step 4, 4.2: the Ollama options sent with every model call by Steward and his team (MAF's OllamaChatOptions):
# his own window, so it never depends on the server's default (2026-11-03: the app's context setting was set to 32K
# for a while, under a 64K compaction budget), and the model kept loaded between turns.
OLLAMA_OPTIONS: dict[str, Any] = {"num_ctx": _STEWARD_CONTEXT, "keep_alive": "30m"}
# </ollama_options>


# <tool_call_limits>
# Step 4, 4.3: MAF's FunctionInvocationConfiguration (agent_framework._tools), per pass of his loop. Calls run one
# at a time in the model's order (his writes and cards stay in order); a failing tool's error text goes back to
# the model, a local channel; and a pass stops calling tools after 40 calls or 30 minutes and answers in text.
# Earned 2026-11-03: round 1's fixer called todos_complete for a finished todo every 18 seconds for 13 minutes.
# include_detailed_errors (audit 2026-11-04): MAF's text is "Exception text may contain sensitive information regardless
# of its source, so enable this only for a trusted channel" (_tools.py:1909-1911). It is one switch per client
# (FunctionInvocationConfiguration; read at _tools.py:1999 and :2042), with no per-tool option. Off, his own tools'
# failures and his mangled arguments would come back as only "Error: Function failed." / "Error: Argument parsing
# failed." (:2014-2016, :2041-2043), which is what he repairs from. So it stays on, and the one untrusted source of
# exception text, an MCP server's error (MCPStreamableHTTPTool raises its isError text, _mcp.py:3471-3483), is withheld
# by function middleware before MAF formats it (withhold_untrusted_errors).
TOOL_CALLS: dict[str, Any] = {
    "allow_concurrent_invocation": False,
    "include_detailed_errors": True,
    "max_function_calls": 40,
    "max_duration_seconds": 1800.0,
}
UNTRUSTED_ERROR = (
    "{name} failed. Its error text is not shown: it comes from SecondBrain's MCP server, an untrusted source "
    "(notes, logs and the web). Try again with other arguments, or go on without it."
)


def withhold_untrusted_errors(sources: Sequence[Any]) -> Callable[..., Awaitable[None]]:
    """Function middleware: a call to one of the sources' MCP functions that raises is re-raised with UNTRUSTED_ERROR
    only, so MAF's detailed error ("Error: Function failed. Exception: ...") carries none of the server's text. Every
    other tool, and every result that is not an error, is left as it is. MAF's control signals pass unchanged."""
    from agent_framework import MiddlewareFailure, UserInputRequiredException  # noqa: PLC0415
    from agent_framework.exceptions import ToolExecutionException  # noqa: PLC0415

    async def withhold_untrusted_errors_(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        name = context.function.name
        if not any(f.name == name for source in sources for f in (getattr(source, "functions", None) or [])):
            await call_next()
            return
        try:
            await call_next()
        except (MiddlewareTermination, MiddlewareFailure, UserInputRequiredException):
            raise
        except Exception as exc:  # noqa: BLE001 - the server's text stays out of what he is shown
            logger.warning("%s failed (%s); its error text was withheld from the model.", name, type(exc).__name__)
            raise ToolExecutionException(UNTRUSTED_ERROR.format(name=name)) from None

    return withhold_untrusted_errors_
# </tool_call_limits>


# <tool_call_retry>
# Not chat middleware (checked 2026-11-03): streamed, the model call starts only when MAF's loop iterates the stream
# (_tools.py:6111), after the chat middleware pipeline has returned it (_middleware.py:1669), and Ollama's mid-stream
# "error parsing tool call" comes from that iteration unwrapped (agent_framework_ollama/_chat_client.py:398; only the
# opening call is wrapped, :393). A try/except around call_next never sees it, so the retry stays on the Ollama client.
_TOOL_CALL_RETRIES = 2
# Measured 2026-11-04: a long-lived Ollama runner (141,000+ tasks) returned garbage tool calls (raw='{"id": 3???????}')
# and "error parsing tool call" stormed through a whole eval, while a fresh runner on the same settings gave 20/20 valid
# calls. So when the retries are spent, the model is unloaded once (keep_alive 0 on a generate with no prompt, ollama
# AsyncClient.generate, ollama/_client.py:732-776) and the call asked once more, which starts a fresh runner. At most one
# unload per _RUNNER_UNLOAD_WINDOW_SECONDS per process, so a model that truly cannot write the call never thrashes.
_RUNNER_UNLOAD_WINDOW_SECONDS = 600.0
_RUNNER_UNLOADED_AT: float | None = None  # time.monotonic() of this process's last unload
# Eval run 2026-11-04 21:46 (small asks, README ask): the unload went through, and the call asked after it died on
# httpx's ReadError, the run with it: the unload ends the runner, and a connection it was serving (the call that
# follows while the model loads again, or another call in flight on the same model) is cut. So for this long after an
# unload, a call cut that way (ollama's AsyncClient is httpx: ReadError, RemoteProtocolError) is asked once more.
_AFTER_UNLOAD_SECONDS = 120.0


def _just_unloaded() -> bool:
    """Whether this process unloaded the runner within _AFTER_UNLOAD_SECONDS."""
    return _RUNNER_UNLOADED_AT is not None and time.monotonic() - _RUNNER_UNLOADED_AT < _AFTER_UNLOAD_SECONDS


def _may_unload_runner() -> bool:
    """Claim this process's one unload in the window: True (and the window starts now) when none was made in it."""
    global _RUNNER_UNLOADED_AT
    now = time.monotonic()
    if _RUNNER_UNLOADED_AT is not None and now - _RUNNER_UNLOADED_AT < _RUNNER_UNLOAD_WINDOW_SECONDS:
        return False
    _RUNNER_UNLOADED_AT = now
    return True


# Steps eval 2026-11-04 21:52 (head 90dc8d4): in EXECUTE, Ollama raised "error parsing tool call" three times and the
# step ended with no call (Calls: []), so the planted bug was never written. Two answers, both on the client:
#   * The call is often all there: Ollama's error carries the model's text (raw='...', err=...; Go's JSON parser rejects
#     a raw line break inside a string, which code in an edit carries, and text after the object). When that text
#     decodes leniently (json strict=False, the first object only) to arguments that fit exactly one offered tool (the
#     rule tool_call_in_text uses for a reply's text), or to {"name": tool, "arguments": {...}}, it is that call, given
#     back as Ollama's own tool call so MAF's loop runs it (agent_framework_ollama/_chat_client.py:717-738).
#   * When the retries (and the one unload) are spent, the model is asked once more with the parse error as a
#     correction turn, so it writes the call again knowing what was wrong, before the error is the run's.
_RAW_TOOL_CALL = re.compile(r"raw='(.*)'(?:, err=.*)?\Z", re.S)
TOOL_CALL_CORRECTION = (
    "Your last tool call could not be read: {error}. Call the tool again with valid JSON arguments: inside a string, "
    "write a line break as \\n and escape a double quote as \\\"; write nothing after the closing brace. Do not answer "
    "in text instead of the call."
)


def tool_call_in_raw(error: Exception, tools: Sequence[Any] | None) -> tuple[str, dict[str, Any]] | None:
    """(tool name, arguments) from the raw text of Ollama's "error parsing tool call", when it holds one offered tool's
    call; tools are the call's own as MAF sent them (FunctionTool.to_json_schema_spec dicts), else None."""
    found = _RAW_TOOL_CALL.search(str(error))
    if found is None or not tools:
        return None
    body = found.group(1).strip()
    if fenced := _FENCED_JSON.match(body):
        body = fenced.group(1)
    try:
        arguments, _ = json.JSONDecoder(strict=False).raw_decode(body)
    except ValueError:
        return None
    if not isinstance(arguments, dict) or not arguments:
        return None
    schemas: dict[str, Mapping[str, Any]] = {}
    for offered in tools:
        spec = offered.to_json_schema_spec() if isinstance(offered, FunctionTool) else offered
        function = spec.get("function") if isinstance(spec, Mapping) else None
        if isinstance(function, Mapping) and function.get("name"):
            schemas[function["name"]] = function.get("parameters") or {}
    named = arguments.get("name")
    if isinstance(named, str) and named in schemas and isinstance(arguments.get("arguments"), dict):
        return named, arguments["arguments"]
    return _the_tool_it_fits(arguments, schemas)


def _retry_malformed_tool_calls(client: OllamaChatClient) -> OllamaChatClient:
    """Retry a model turn whose tool call Ollama could not parse, instead of failing the run.

    gpt-oss sometimes emits invalid JSON for a tool call that carries code; Ollama then raises
    "error parsing tool call" mid-stream and the whole turn dies. The model samples again on a
    retry, so the same request is re-asked (without streaming) up to _TOOL_CALL_RETRIES times.
    When those fail too, the runner may be stale: the model is unloaded and asked once more.
    """
    import httpx  # noqa: PLC0415 - ollama's AsyncClient is built on httpx (ollama/_client.py)
    import ollama  # noqa: PLC0415
    from ollama import ResponseError

    chat = client.client.chat
    cut = (httpx.ReadError, httpx.RemoteProtocolError)

    async def _ask_after_unload(kwargs: dict[str, Any], exc: Exception) -> Any:
        """A call cut while the runner was unloaded and loaded again: asked once more, not streamed."""
        logger.warning("A call to Ollama was cut right after the runner was unloaded (%s); asking once more.", type(exc).__name__)
        return await chat(**{**kwargs, "stream": False})

    def _recovered(kwargs: dict[str, Any], error: Exception) -> Any:
        """Ollama's answer carrying the call found in the error's raw text (tool_call_in_raw), or None."""
        if (found := tool_call_in_raw(error, kwargs.get("tools"))) is None:
            return None
        name, arguments = found
        logger.warning("Malformed tool call from the model; recovered %s from its text.", name)
        call = ollama.Message.ToolCall(function=ollama.Message.ToolCall.Function(name=name, arguments=arguments))
        return ollama.ChatResponse(
            model=kwargs.get("model") or client.model, done=True, done_reason="stop",
            message=ollama.Message(role="assistant", content="", tool_calls=[call]),
        )

    async def _corrected(kwargs: dict[str, Any], error: ResponseError) -> Any:
        """The retries are spent: asked once more with the parse error as a correction turn; else the error is raised."""
        logger.warning("Malformed tool call from the model; asking again with the parse error as a correction.")
        said = (str(error).splitlines() or [type(error).__name__])[0][:600]
        turn = {"role": "user", "content": TOOL_CALL_CORRECTION.format(error=said)}
        try:
            return await chat(**{**kwargs, "messages": [*(kwargs.get("messages") or []), turn], "stream": False})
        except ResponseError as exc:
            if "error parsing tool call" not in str(exc):
                raise
            if (recovered := _recovered(kwargs, exc)) is not None:
                return recovered
            raise error from exc

    async def _ask_again(kwargs: dict[str, Any], first: ResponseError) -> Any:
        error = first
        if (recovered := _recovered(kwargs, error)) is not None:
            return recovered
        for attempt in range(1, _TOOL_CALL_RETRIES + 1):
            logger.warning("Malformed tool call from the model; asking again (%d/%d).", attempt, _TOOL_CALL_RETRIES)
            try:
                return await chat(**{**kwargs, "stream": False})
            except ResponseError as exc:
                if "error parsing tool call" not in str(exc):
                    raise
                error = exc
                if (recovered := _recovered(kwargs, error)) is not None:
                    return recovered
        if not _may_unload_runner():
            return await _corrected(kwargs, error)
        model = kwargs.get("model") or client.model  # MAF puts the model in the call's options (_chat_client.py:477-480)
        logger.warning(
            "Ollama's runner looks stale after repeated malformed tool calls; unloading %s for a fresh runner.", model
        )
        try:
            await client.client.generate(model=model, keep_alive=0)
        except Exception as exc:  # noqa: BLE001 - an unload that fails leaves the parse error as the run's error
            logger.warning("Unloading %s failed (%s); giving up on the malformed tool call.", model, type(exc).__name__)
            raise error from exc
        try:
            return await chat(**{**kwargs, "stream": False})
        except cut as exc:
            return await _ask_after_unload(kwargs, exc)
        except ResponseError as exc:
            if "error parsing tool call" not in str(exc):
                raise
            return _recovered(kwargs, exc) or await _corrected(kwargs, exc)

    async def chat_with_retry(*args: Any, **kwargs: Any) -> Any:
        if not kwargs.get("stream"):
            try:
                return await chat(*args, **kwargs)
            except ResponseError as exc:
                if "error parsing tool call" not in str(exc):
                    raise
                return await _ask_again(kwargs, exc)
            except cut as exc:
                if not _just_unloaded():
                    raise
                return await _ask_after_unload(kwargs, exc)
        try:
            stream = await chat(*args, **kwargs)
        except cut as exc:
            if not _just_unloaded():
                raise
            return _one(await _ask_after_unload(kwargs, exc))

        async def parts() -> Any:
            try:
                async for part in stream:
                    yield part
            except ResponseError as exc:
                if "error parsing tool call" not in str(exc):
                    raise
                yield await _ask_again(kwargs, exc)
            except cut as exc:
                if not _just_unloaded():
                    raise
                yield await _ask_after_unload(kwargs, exc)

        return parts()

    async def _one(response: Any) -> Any:  # a whole answer, given where a stream was asked for
        yield response

    client.client.chat = chat_with_retry  # type: ignore[method-assign]
    return client


# </tool_call_retry>

# <ollama_timings>
# Ollama's chat response carries its own timings (ollama/_types.py, BaseGenerateResponse: load_duration,
# prompt_eval_duration and eval_duration in nanoseconds, eval_count in tokens), and MAF's OllamaChatClient keeps only
# the token counts (agent_framework_ollama/_chat_client.py:658-713). MAF's UsageDetails is open for a provider's own
# fields ("any specific provider fields can be added as needed", agent_framework/_types.py:553-557) and names them by
# provider ("openai.cached_input_tokens", observability.py:382-392). So each chat call's timings go into its usage as
# "ollama.<field>", and onto the call's chat span under the same names: the span is current while Ollama answers
# (observability.py: _get_span's trace.use_span, and the stream's pull context manager, _activate_span).
OLLAMA_TIMINGS = ("load_duration", "prompt_eval_duration", "eval_count", "eval_duration")


def ollama_timings(response: Any) -> dict[str, int]:
    """The timings an Ollama chat response carries, as "ollama.<field>": int (absent fields left out)."""
    values = {field: getattr(response, field, None) for field in OLLAMA_TIMINGS}
    return {f"ollama.{k}": v for k, v in values.items() if isinstance(v, int) and not isinstance(v, bool)}


def _record_ollama_timings(client: OllamaChatClient) -> OllamaChatClient:
    """Each chat call's Ollama timings in its usage details and on its chat span, streamed or not."""
    from agent_framework import Content, UsageDetails  # noqa: PLC0415
    from opentelemetry import trace  # noqa: PLC0415

    parse = client._parse_response_from_ollama  # noqa: SLF001 - MAF's parsers, wrapped and called as they are
    parse_update = client._parse_streaming_response_from_ollama  # noqa: SLF001

    def parse_response(response: Any, **kwargs: Any) -> Any:
        result = parse(response, **kwargs)
        if timings := ollama_timings(response):
            result.usage_details = UsageDetails(**{**(result.usage_details or {}), **timings})
            trace.get_current_span().set_attributes(timings)
        return result

    def parse_streaming_response(response: Any) -> Any:
        update = parse_update(response)
        if getattr(response, "done", False) and (timings := ollama_timings(response)):
            usage = next((c for c in update.contents if c.type == "usage"), None)
            if usage is not None:
                usage.usage_details = UsageDetails(**{**(usage.usage_details or {}), **timings})
            else:
                update.contents.append(Content.from_usage(UsageDetails(**timings), merge_mode="replace"))
            trace.get_current_span().set_attributes(timings)
        return update

    client._parse_response_from_ollama = parse_response  # type: ignore[method-assign]  # noqa: SLF001
    client._parse_streaming_response_from_ollama = parse_streaming_response  # type: ignore[method-assign]  # noqa: SLF001
    return client


# </ollama_timings>



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


# <code_punctuation>
# Live 2026-11-04 (evals.py small, the item_count ask): gpt-oss wrote a .py file with U+2011 (a non-breaking hyphen)
# where a minus belonged, the file failed with a SyntaxError, the check failed and the run ended asking questions. MAF's
# place for it is function middleware that sets context.result and does not call call_next (Learn, agents/middleware,
# termination; as refuse_grader_writes in improvement_loop_workflow.py): a write to a .py file whose resulting text holds
# one of these characters outside a string or comment is refused with the character, its line and column and the ASCII
# one to use, and nothing is written. His content is never rewritten for him. Other files are left alone.
CODE_PUNCTUATION: dict[str, str] = {
    **dict.fromkeys("‐‑‒–—―−", "-"),
    **dict.fromkeys("‘’", "'"),
    **dict.fromkeys("“”", '"'),
    **dict.fromkeys("  ", " "),
}
CODE_PUNCTUATION_REFUSAL = (
    "Refused: {file} line {line}, column {column} has {char!r} (U+{code:04X} {name}) outside a string or comment, and "
    "Python cannot run it. Nothing was written. Use the ASCII character {ascii!r} instead, and write the change again."
)
# Tokens whose text Python never reads as code (tokenize, 3.12+: an f-string's literal parts are FSTRING_MIDDLE).
_TEXT_TOKENS = frozenset(
    getattr(tokenize, name) for name in ("STRING", "COMMENT", "FSTRING_MIDDLE", "TSTRING_MIDDLE") if hasattr(tokenize, name)
)


def code_punctuation_problem(file_name: str, content: str) -> str | None:
    """The refusal for a .py file's resulting text with Unicode punctuation outside a string or comment, or None.

    Python's tokenize reads such a character as a NAME token, so every token that is not a string or a comment is
    searched; a text that stops tokenizing (an edit made in parts) is searched up to where it stops. Then ast.parse,
    whose "invalid character" error names the position, catches one the tokens did not reach.
    """
    if not str(file_name).lower().endswith(".py") or not any(c in content for c in CODE_PUNCTUATION):
        return None
    found: tuple[int, int, str] | None = None
    try:
        for token in tokenize.generate_tokens(io.StringIO(content).readline):
            if token.type in _TEXT_TOKENS:
                continue
            at = next((i for i, c in enumerate(token.string) if c in CODE_PUNCTUATION), None)
            if at is not None:
                found = (token.start[0], token.start[1] + at + 1, token.string[at])
                break
    except (tokenize.TokenError, SyntaxError):
        pass
    if found is None:
        try:
            ast.parse(content)
        except SyntaxError as error:
            lines = content.splitlines()
            if error.lineno and error.offset and error.lineno <= len(lines) and 0 < error.offset <= len(lines[error.lineno - 1]):
                char = lines[error.lineno - 1][error.offset - 1]
                if char in CODE_PUNCTUATION:
                    found = (error.lineno, error.offset, char)
    if found is None:
        return None
    line, column, char = found
    return CODE_PUNCTUATION_REFUSAL.format(
        file=file_name, line=line, column=column, char=char, code=ord(char),
        name=unicodedata.name(char, "UNICODE CHARACTER"), ascii=CODE_PUNCTUATION[char],
    )


def _written_text(name: str, arguments: dict[str, Any]) -> str | None:
    """The text a call to MAF's write tools would leave in its file, by MAF's own edit functions
    (agent_framework/_harness/_file_access.py: file_access_replace :2387, file_access_replace_lines :2409), read with
    "\\n" endings as LineEndingFileStore reads it; None for a delete, a missing file or an edit MAF would refuse."""
    from agent_framework._harness._file_access import _apply_replace, _apply_replace_lines, _line_edits  # noqa: PLC0415

    def lf(text: Any) -> str:
        return str(text or "").replace("\r\n", "\n")

    if name == FileAccessProvider.WRITE_TOOL_NAME:
        return lf(arguments.get("content"))
    if name not in (FileAccessProvider.REPLACE_TOOL_NAME, FileAccessProvider.REPLACE_LINES_TOOL_NAME):
        return None
    try:
        path = _inside_workspace(str(arguments.get("file_name") or ""))
        old = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if name == FileAccessProvider.REPLACE_TOOL_NAME:
            return _apply_replace(old, lf(arguments.get("old_string")), lf(arguments.get("new_string")), bool(arguments.get("replace_all")))[0]
        return _apply_replace_lines(old, _line_edits(list(arguments.get("edits") or [])))
    except (OSError, ValueError, KeyError, TypeError):
        return None  # MAF's tool answers it itself, with its reason, and writes nothing


# Small run 1 (2026-11-04, head 0016cf4, the item_count ask): the request named
# harness/steward/working/sample-project/inventory.py, and besides it he wrote a bare "inventory.py", which MAF's file
# store took from its root, the repository's, so a stray inventory.py was left at the root and the checks failed on it.
# Such a write is refused, not moved: MAF's file tools take the path the model gives (FileAccessProvider resolves it
# under its store root), and the harness never rewrites a call's arguments (as recover_text_tool_calls keeps "only ever
# the model's own"). The refusal is his tool result, as refuse_in_plan_mode's is, and names the path the request meant,
# so his next call is right and the tool result says why. It applies only when the bare name is not a file at the root
# and the request names a folder holding a file of that name (or that file itself); anything else goes on as before.
NAMED_PATHS_KEY = "steward_named_paths"
_NAMED_PATH = re.compile(r"(?<![\w./-])(?:[\w.-]+/)+[\w-]+(?:\.\w+)?")
BARE_NAME_REFUSAL = (
    "Refused: '{file_name}' has no folder, so it would be written at the repository root, where no such file is. The "
    "request names {path}. Call the tool again with file_name '{path}'. Nothing was written."
)


def named_paths(text: str) -> list[str]:
    """The paths with a folder that text names (e.g. harness/steward/working/sample-project/inventory.py), once each."""
    return list(dict.fromkeys(_NAMED_PATH.findall((text or "").replace("\\", "/"))))


def bare_name_meant(file_name: str, named: Sequence[str]) -> str | None:
    """The one existing file a bare file_name means in a request naming ``named`` paths, or None: the name has no
    folder, is no file at the workspace root, and exactly one named path is that file or a folder holding it."""
    if not file_name or "/" in file_name or "\\" in file_name:
        return None
    try:
        if _inside_workspace(file_name).exists():
            return None
    except ValueError:
        return None
    meant = set()
    for path in named:
        candidate = path if path.rsplit("/", 1)[-1] == file_name else f"{path}/{file_name}"
        try:
            if _inside_workspace(candidate).is_file():
                meant.add(candidate)
        except ValueError:
            continue
    return meant.pop() if len(meant) == 1 else None


# The bar at 1b56963 (2026-11-05 07:32-07:40Z, the README ask): his memory's context says "Use MEMORY.md" (MAF's
# DEFAULT_MEMORY_CONTEXT_PROMPT, _memory.py), and he wrote MEMORY.md at the repository root with file_access_write, nine
# times over twenty rounds of cards. MEMORY.md is his memory's index, which MAF's memory store rebuilds from its topic
# files; the workspace's file tools never write it. Such a write is refused with the memory tool to use, and nothing
# is written; a MEMORY.md the workspace already has is left to the file tools as any file is.
MEMORY_INDEX_REFUSAL = (
    "Refused: '{file_name}' is your memory's index, which your memory keeps itself; the file tools do not write it. To "
    "remember something, call write_memory with a topic and the fact. Nothing was written."
)


def writes_memory_index(file_name: str) -> bool:
    """Whether a file tool's file_name is MAF's memory index (MEMORY.md) at the workspace root, where no such file is."""
    from agent_framework._harness._memory import DEFAULT_MEMORY_INDEX_FILE_NAME  # noqa: PLC0415

    name = str(file_name or "").replace("\\", "/").strip().lstrip("./")
    if name.lower() != DEFAULT_MEMORY_INDEX_FILE_NAME.lower():
        return False
    try:
        return not _inside_workspace(name).exists()
    except ValueError:
        return False


async def refuse_a_bare_name_the_request_put_in_a_folder(
    context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]
) -> None:
    """Function middleware on MAF's file writes: a bare file name the request meant in a named folder (bare_name_meant,
    over the paths RequestHints keeps in NAMED_PATHS_KEY) is refused with BARE_NAME_REFUSAL as the tool result."""
    if context.function.name in FileAccessProvider._WRITE_TOOL_NAMES:  # MAF's own set of its write tools
        session = context.session or _RUN_SESSION.get()
        named = (session.state.get(NAMED_PATHS_KEY) if session is not None else None) or []
        arguments = context.arguments
        arguments = arguments.model_dump() if hasattr(arguments, "model_dump") else dict(arguments or {})
        file_name = str(arguments.get("file_name") or "")
        if writes_memory_index(file_name):
            context.result = MEMORY_INDEX_REFUSAL.format(file_name=file_name)
            return
        if named and (path := bare_name_meant(file_name, named)):
            context.result = BARE_NAME_REFUSAL.format(file_name=file_name, path=path)
            return
    await call_next()


# The bar at 416ba41 (2026-11-05 05:29Z, the README ask's second run): the request named
# harness/steward/working/sample-project/README.md; he listed harness/working (dropping "steward"), found
# harness/working/sample-project empty and README.md "not found" there, and replied that the file did not exist. A read
# or listing of a path where nothing is, whose last part is a part of a path the request names, gets that path after
# MAF's own result, as the bare-name refusal names it: his call is never rewritten, and the next one can be right.
MISSED_PATH_HINT = "Nothing is at '{path}'. The request names {meant}: use that path."


def missed_path_meant(path: str, named: Sequence[str]) -> str | None:
    """The existing path a request's named path holds up to ``path``'s last part, when nothing is at ``path``, or None."""
    wanted = str(path or "").replace("\\", "/").strip().strip("/")
    if not wanted:
        return None
    try:
        if _inside_workspace(wanted).exists():
            return None
    except ValueError:
        return None
    last = wanted.rsplit("/", 1)[-1]
    for named_path in named:
        parts = named_path.split("/")
        if last not in parts:
            continue
        meant = "/".join(parts[: len(parts) - parts[::-1].index(last)])
        try:
            if meant != wanted and _inside_workspace(meant).exists():
                return meant
        except ValueError:
            continue
    return None


def _found_nothing(result: Any) -> bool:
    """Whether a MAF read tool's result says nothing is there: "not found", "Could not list", or an empty listing."""
    if isinstance(result, list) and result and all(hasattr(c, "type") for c in result):
        result = "\n".join(str(getattr(c, "text", "") or "") for c in result)
    if isinstance(result, list):
        return not result
    text = str(result or "").strip()
    return text in ("", "[]") or text.startswith("Could not list") or (text.startswith("File '") and text.endswith("' not found."))


async def point_a_missed_path_at_the_named_one(
    context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]
) -> None:
    """Function middleware on MAF's file reads: a read or listing that found nothing, of a path missing a part the
    request's named path has (missed_path_meant), gets MISSED_PATH_HINT after its result."""
    await call_next()
    name = context.function.name
    if name not in FileAccessProvider._READ_ONLY_TOOL_NAMES or not _found_nothing(context.result):  # MAF's own set
        return
    session = context.session or _RUN_SESSION.get()
    named = (session.state.get(NAMED_PATHS_KEY) if session is not None else None) or []
    arguments = context.arguments
    arguments = arguments.model_dump() if hasattr(arguments, "model_dump") else dict(arguments or {})
    path = str(arguments.get("file_name") or arguments.get("directory") or "")
    if named and (meant := missed_path_meant(path, named)):
        hint = MISSED_PATH_HINT.format(path=path, meant=meant)
        result = context.result
        if isinstance(result, list) and result and all(hasattr(c, "type") for c in result):
            context.result = [*result, Content.from_text(hint)]
        else:
            shown = "[]" if isinstance(result, list) else str(result or "")
            context.result = f"{shown}\n{hint}".strip()


# The bar at f7b5120 (2026-11-05 06:26Z, the discount ask): his plan's step was an object ("Edit file" and a path), he
# called todos_complete with {"title": "Edit file", "reason": ...}, MAF answered "Argument parsing failed. Exception:
# Invalid arguments for 'todos_complete'" twice, and his last reply was the call written as raw text. MAF shows a call
# whose arguments fail validation to function middleware before it refuses it (_tools.py: "Invalid provider arguments
# are intentionally exposed to middleware so it has a supported opportunity to repair them before final validation").
# The bar at 1b56963 (2026-11-05 07:30Z, the README ask): answered with the ids, he called todos_add (not offered in
# EXECUTE), decided the todo tools were missing, and the open-todo reminder kept him going for twenty rounds of cards.
# So an item whose title names exactly one open todo (backticks, case and spacing aside; one title the start of the
# other) is given that todo's id, as repair_tool_names gives a misspelled call its one tool; anything else is answered
# with TODO_IDS_REFUSAL and nothing is completed.
TODO_IDS_REFUSAL = (
    "Not completed: todos_complete takes each item's id (a number) and a reason, not its title. Your open todos: "
    "{open}. Call todos_complete again with items like {{\"id\": {first}, \"reason\": \"...\"}}."
)


def _todo_title_key(title: Any) -> str:
    return " ".join(str(title or "").replace("`", "").lower().split())


def todo_id_for_title(title: Any, open_todos: Sequence[Any]) -> int | None:
    """The id of the one open todo a title names (todo_ids_by_name), or None when none or several do."""
    key = _todo_title_key(title)
    if not key:
        return None
    exact = [t for t in open_todos if _todo_title_key(t.title) == key]
    if exact:
        return exact[0].id if len(exact) == 1 else None
    named = [t for t in open_todos if (k := _todo_title_key(t.title)) and (k.startswith(key) or key.startswith(k))]
    return named[0].id if len(named) == 1 else None


def todo_ids_by_name(todo_provider: TodoProvider | None) -> Callable[..., Awaitable[None]]:
    """Function middleware: a todos_complete whose items lack an id gets the id of the one open todo each title names,
    or is answered with TODO_IDS_REFUSAL."""

    async def todo_ids_by_name_(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        if todo_provider is not None and context.function.name == "todos_complete":
            arguments = context.arguments
            arguments = arguments.model_dump() if hasattr(arguments, "model_dump") else dict(arguments or {})
            items = arguments.get("items")
            if isinstance(items, list) and any(not isinstance(i, dict) or i.get("id") is None for i in items):
                session = context.session or _RUN_SESSION.get()
                todos = await todo_provider.store.load_items(session, source_id=todo_provider.source_id) if session is not None else []
                left = [t for t in todos if not t.is_complete]
                ids = [i.get("id") if isinstance(i, dict) and i.get("id") is not None else todo_id_for_title((i or {}).get("title") if isinstance(i, dict) else None, left) for i in items]
                if left and all(found is not None for found in ids) and len(set(ids)) == len(ids):
                    repaired = [{**i, "id": found} for i, found in zip(items, ids, strict=True)]
                    context.arguments = {**arguments, "items": [{k: v for k, v in i.items() if k != "title"} for i in repaired]}
                elif left:
                    named = "; ".join(f'id {t.id}: "{t.title}"' for t in left)
                    context.result = TODO_IDS_REFUSAL.format(open=named, first=left[0].id)
                    return
        await call_next()

    return todo_ids_by_name_


async def refuse_unicode_punctuation_in_code(
    context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]
) -> None:
    """Function middleware on his file writes (and the improvement round's coder's): a .py file is never left with
    Unicode punctuation outside a string or comment (code_punctuation_problem); the refusal is his tool result."""
    name = context.function.name
    if name in FileAccessProvider._WRITE_TOOL_NAMES:  # MAF's own set of its write tools
        arguments = context.arguments
        arguments = arguments.model_dump() if hasattr(arguments, "model_dump") else dict(arguments or {})
        file_name = str(arguments.get("file_name") or "")
        text = _written_text(name, arguments) if file_name.lower().endswith(".py") else None
        if text is not None and (refusal := code_punctuation_problem(file_name, text)):
            context.result = refusal
            return
        if name == FileAccessProvider.WRITE_TOOL_NAME and text is not None and (refusal := whole_write_problem(file_name, text)):
            context.result = refusal
            return
        if name != FileAccessProvider.WRITE_TOOL_NAME and text is not None and (refusal := edit_breaks_python(file_name, text)):
            context.result = refusal
            return
    await call_next()


# The bar at a3a3519's parent (2026-11-05 05:33Z, the steps set): EXECUTE's file_access_replace_lines put order_total's
# two body lines at 8 spaces under a 4-space docstring, inventory.py no longer parsed, the check failed on collection
# ("1 error during collection"), and REPAIR made the same edit twice. An edit of a .py file that parsed before and would
# not parse after is refused like a whole write that is not Python: nothing is written, and the refusal names Python's
# error and shows the lines around it as they would be, numbered, so the indentation is in front of him.
EDIT_CONTEXT_LINES = 3


def edit_breaks_python(file_name: str, content: str) -> str | None:
    """The refusal for an edit (file_access_replace, _replace_lines) that leaves a parsing .py file unparsable, or None.

    ``content`` is the text the edit would leave (_written_text). A file that did not parse before is not judged: an
    edit may be the one that mends it."""
    if not str(file_name).lower().endswith(".py"):
        return None
    try:
        ast.parse(content)
        return None
    except SyntaxError as error:
        problem = error
    try:
        ast.parse(_inside_workspace(file_name).read_text(encoding="utf-8"))
    except (OSError, ValueError, SyntaxError):
        return None
    lines = content.split("\n")
    at = problem.lineno or 1
    shown = "\n".join(
        f"{number:>4}| {lines[number - 1]}"
        for number in range(max(1, at - EDIT_CONTEXT_LINES), min(len(lines), at + EDIT_CONTEXT_LINES) + 1)
    )
    return (
        f"Refused: after this edit {file_name} would not be Python ({problem.msg}, line {problem.lineno}), so nothing "
        f"was written. The lines around it would be:\n{shown}\nKeep each line's indentation as the lines around it "
        "have it (a function's body one level in from its def), and make the edit again."
    )


def whole_write_problem(file_name: str, content: str) -> str | None:
    """The refusal for a whole-file write of a .py file whose text is not Python, or None.

    2026-11-04 10:14: he overwrote the sample project's inventory.py with only its docstring's first words and "...", a shortened
    stand-in for the file, and every eval after it ran on a file with no code. A whole write is the whole file, so it
    must parse; an edit made in parts goes through file_access_replace, which this does not judge."""
    if not str(file_name).lower().endswith(".py"):
        return None
    try:
        ast.parse(content)
    except SyntaxError as error:
        return (
            f"Refused: {file_name} would not be Python ({error.msg}, line {error.lineno}), so nothing was written. "
            "file_access_write replaces the whole file: give its complete text, never a shortened one, "
            "or change part of it with file_access_replace."
        )
    return None


# </code_punctuation>


# <history>
# His conversation history on disk (2026-11-04): MAF's FileHistoryProvider (agent_framework/_sessions.py), one
# append-only JSON Lines file per session_id under the Steward repo's gitignored storage/history, so a console or MCP
# session keeps its history across a restart; InMemoryHistoryProvider kept it in the session's state only. The
# Responses host keeps its own checkpoints and stays on InMemoryHistoryProvider. A session's file is kept for the
# host-state window (hosted.py's <retention>, STEWARD_STATE_RETENTION_DAYS, 14 days) since it was last written:
# FileHistoryProvider has no expiry of its own, so older files are removed when the provider is made, at host start.
STATE_RETENTION_DAYS = 14
STATE_RETENTION_DAYS_ENV = "STEWARD_STATE_RETENTION_DAYS"
HISTORY_DIR = _STEWARD_DIR.parents[1] / "storage" / "history"


def state_retention_days() -> int:
    """Days the host keeps its state: STEWARD_STATE_RETENTION_DAYS, or STATE_RETENTION_DAYS."""
    return int(os.environ.get(STATE_RETENTION_DAYS_ENV, STATE_RETENTION_DAYS))


def steward_history_provider(path: Path = HISTORY_DIR, *, now: float | None = None) -> FileHistoryProvider:
    """His history provider for the console and the MCP door: FileHistoryProvider on ``path``, after removing each
    session's file not written within state_retention_days()."""
    provider = FileHistoryProvider(path)  # makes the folder
    cutoff = (time.time() if now is None else now) - 86_400 * state_retention_days()
    removed = 0
    for old in path.glob("*.jsonl"):
        if old.stat().st_mtime < cutoff:
            old.unlink(missing_ok=True)
            removed += 1
    logger.info("History in %s; %d session(s) older than %d days removed.", path, removed, state_retention_days())
    return provider


# </history>


# <automatic_memory>
# Step 5 (5.1, 5.2): MAF's MemoryContextProvider beside his conversation history: topic files under a MEMORY.md index,
# written by him with its write_memory tool; before each turn the index and the three best-matching topics are put in
# front of him; transcripts are kept and topics consolidated over time. Its automatic extraction is off
# (max_extractions=0, Kyle 2026-11-04: "Deliberate only"): live, gpt-oss saved his own answers and his memory eval's
# output as facts and doubled what he had saved himself, whatever its extraction prompt said. One
# owner, "steward", so what he learns in one conversation is there in the next. A host passes the store (memory_store);
# evals pass a throwaway one. It replaces the unused Mem0 path (2026-11-03: a second store and an embedder for what
# MAF's own provider does; its store is in agent-file-memory/attic/2026-11-03-old-session-memory/mem0-store).
MEMORY_DIR = _WORKING_DIR / "agent-memory"
MEMORY_OWNER_KEY = "steward_memory_owner"
MEMORY_OWNER = "steward"


def steward_memory_store(base: str | Path | None = None) -> MemoryFileStore | None:
    """His memory store: MAF's MemoryFileStore under MEMORY_DIR (or base), owned by MEMORY_OWNER. The default store
    is off when STEWARD_AUTOMATIC_MEMORY is "off" (the harness tests set it); a base given here is always used."""
    if base is None and os.environ.get("STEWARD_AUTOMATIC_MEMORY", "").lower() == "off":
        return None
    return MemoryFileStore(base or MEMORY_DIR, owner_state_key=MEMORY_OWNER_KEY)


def plain_tool_results(message: Message) -> Message:
    """MAF's history_message_filter for his memory's transcripts: a tool result's text as a plain str.

    An approved run_shell's result is MAF's _ShellResultText (agent_framework_tools/shell/_types.py), a str subclass,
    and the transcript's msgspec encoder (agent_framework/_sessions.py, _default_json_dumps) refuses it: with automatic
    memory on, every approved command failed the hosted run ("Encoding objects of type _ShellResultText is
    unsupported"). A function_result keeps its text in result and in its text items (_types.py,
    Content.from_function_result), so both are made plain, on copies (Content.__copy__): the message itself is the
    run's and is left as it is. Any other message is returned unchanged.
    """

    def plain(value: Any) -> Any:
        return str(value) if isinstance(value, str) and type(value) is not str else value

    def plain_text(item: Any) -> Any:
        if getattr(item, "type", None) != "text" or plain(item.text) is item.text:
            return item
        item = copy.copy(item)
        item.text = plain(item.text)
        return item

    contents = []
    changed = False
    for content in message.contents:
        if content.type == "function_result":
            result, items = plain(content.result), [plain_text(i) for i in content.items or []]
            if result is not content.result or any(a is not b for a, b in zip(items, content.items or [])):
                content = copy.copy(content)
                content.result = result
                content.items = items if content.items is not None else None
                changed = True
        contents.append(content)
    if not changed:
        return message
    message = copy.copy(message)
    message.contents = contents
    return message


def steward_memory(memory_store: Any) -> MemoryContextProvider:
    """His memory: MAF's MemoryContextProvider on memory_store, holding what he saves with write_memory; no automatic
    extraction (max_extractions=0 skips it, _harness/_memory.py _extract_memories). His transcripts go through MAF's
    history_message_filter ("rewrite or drop messages before transcript save"), plain_tool_results."""
    return MemoryContextProvider(store=memory_store, max_extractions=0, history_message_filter=plain_tool_results)


async def memory_owner(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Every session he runs in belongs to his one memory owner (MemoryFileStore reads it from the session's state)."""
    if context.session is not None:
        context.session.state.setdefault(MEMORY_OWNER_KEY, MEMORY_OWNER)
    await call_next()


# </automatic_memory>


_CHARTER_NOTE = "steward-charter"
# The notes Steward reads in the live path (plan-steward-context-memory-reads, piece 2); reads only.
# Reads run at once; writing and appending a note ask the user (the secondbrain-notes skill, 2026-11-02: the live
# Steward could read his notes but had no tool to write one, though the skill and the user expect it).
_SECONDBRAIN_NOTES_TOOLS = ("search_notes", "read_note", "list_notes", "write_note", "append_to_note")
_SECONDBRAIN_NOTES_ASK = ("write_note", "append_to_note")
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


# <safety_observe>
# ADR-0001 item 8, observe only: MAF's FIDES (Learn, agents/security, Python pivot:
# https://learn.microsoft.com/en-us/agent-framework/agents/security?pivots=programming-language-python) records what it
# would have blocked, and refuses, delays or changes nothing.
#   * The page's "Dry run" (enable_policy_enforcement=False) records nothing: SecureAgentConfig then builds no policy
#     enforcer and get_audit_log returns [] (agent_framework/security.py:3465-3476, :3580-3581). The enforcer's own
#     record-only branch is block_on_violation=False with approval_on_violation=False: each violation goes to its audit
#     log (:3174-3175, :3330-3337), it warns "(allowed)" and calls the tool (:3206-3209). That is the one used.
#   * The page's standalone classes ("exposed as standalone classes ... for advanced setups"), not SecureAgentConfig as a
#     context provider: that one also adds quarantined_llm, inspect_variable and their instructions to every turn
#     (:3537-3539), which would change what he is shown. auto_hide_untrusted=False ("the picture with
#     auto_hide_untrusted=False"): no result is swapped for a variable. So no quarantine client either (no second model).
#   * default_integrity TRUSTED: his repo and his own tools are the closed, vetted set the page names for it; untrusted
#     content is labelled at its source, MAF's SecureMCPToolProxy on his notes (source_integrity "untrusted", Tier 2,
#     security.py:4396). MAF's MCP labelling makes every MCP tool a sink (accepts_untrusted False, :4401), so the reads
#     over MCP are the page's allow_untrusted_tools, the data fetchers that "must be callable in any context".
#   * CodeAct: the page's warning is that FIDES does not see host-tool calls inside generated code. His Monty provider
#     is given no host tools (MontyCodeActProvider(tools=None), agent_framework_monty/_provider.py:42) and mounts harness/
#     read-only, so every sink stays a direct tool, the page's arrangement; nothing in Monty refuses FIDES beside it.
#   * SecondBrain's web tools are labelled untrusted at their source too (secondbrain_web_tools, audit 2026-11-04), on
#     WebResearchAgent, which records with its own fides_observer; web_search and web_fetch are its data fetchers.
#   * STEWARD_FIDES_ENFORCE=on (off by default: "FIDES later") turns on the enforcer's blocking branch,
#     block_on_violation=True (:3204-3205, _block_policy_violation :3035-3054): for his sinks (_CHANGES_THINGS) only, a
#     second enforcer sets the refusal as context.result and raises MiddlewareTermination, which the tool loop returns
#     as the function result (_tools.py:2412-2437, :2529-2538). Every other tool keeps the record-only enforcer, so a
#     read after a note still runs. The record carries "blocked".
#   * Not labelled, because MAF has no option for it yet (#7455 B1): harness-made tools. What WebResearchAgent found
#     reaches Steward through its background results (background_agents_get_task_results,
#     _harness/_background_agents.py:585), and SecondBrain's skill notes through load_skill and read_skill_resource.
# Agent Hooks (Learn, agents/agent-hooks) are not wired: their bundle buffers every streamed run in evaluate_only too
# (_agent_hooks.py:1332 and :1462 set stream_buffer_updates whatever the mode), so the Agent tab would stop streaming;
# the test test_agent_hooks_still_hold_back_a_streamed_reply measures it.
SAFETY_OBSERVE_ENV = "STEWARD_SAFETY_OBSERVE"
SAFETY_LOG_DIR = _WORKING_DIR / "halo_traces"  # gitignored, beside HALO's traces
FIDES_LOG_NAME = "fides.jsonl"
# The untrusted sources and the reads over MCP: FIDES's data fetchers (allow_untrusted_tools).
_UNTRUSTED_NOTE_READS = frozenset(f"secondbrain_{name}" for name in ("search_notes", "read_note", "list_notes"))
_DOOR_READS = frozenset({*(f"atlas_{name}" for name in ("git", "git_diff", "records")), PR_CHECKS_TOOL})
_ESTATE_READ_TOOLS = frozenset(f"secondbrain_{name}" for name in ESTATE_READS)  # the Estate's reads fetch data too
_WEB_READS = frozenset(f"secondbrain_{name}" for name in ("web_search", "web_fetch"))  # WebResearchAgent's fetchers
# What puts untrusted content in his context, for the sandbox's shell (<sandbox>): his notes, the Estate's logs, the web,
# and the background agents' results, which carry WebResearchAgent's pages and which FIDES does not label (#7455 B1).
_SANDBOX_UNTRUSTED_SOURCES = _UNTRUSTED_NOTE_READS | _ESTATE_READ_TOOLS | _WEB_READS | {"background_agents_get_task_results"}


def safety_observe_on() -> bool:
    """Whether FIDES records (STEWARD_SAFETY_OBSERVE, on unless "off", "0", "false" or "no")."""
    return os.environ.get(SAFETY_OBSERVE_ENV, "on").strip().lower() not in {"off", "0", "false", "no"}


FIDES_ENFORCE_ENV = "STEWARD_FIDES_ENFORCE"


def fides_enforce_on() -> bool:
    """Whether FIDES refuses his sinks in an untrusted context (STEWARD_FIDES_ENFORCE, off unless "on", "1", "true" or
    "yes")."""
    return os.environ.get(FIDES_ENFORCE_ENV, "off").strip().lower() in {"on", "1", "true", "yes"}


def fides_on() -> bool:
    """Whether FIDES is wired at all: recording (safety_observe_on) or enforcing (fides_enforce_on)."""
    return safety_observe_on() or fides_enforce_on()


def fides_observer() -> list[Any]:
    """FIDES in record-only mode, for the end of his middleware list: (recorder, MAF's label tracker, MAF's enforcer).

    Last, so it sees only the calls that reach their tool (the plan-mode gate and the door's world check refuse first),
    and the recorder outermost of the three, so it reads the enforcer's audit log after each call. Each entry is one line
    of halo_traces/fides.jsonl, marked with whether the tool is one of his sinks (_CHANGES_THINGS), then the log is
    cleared (PolicyEnforcementFunctionMiddleware.clear_audit_log), so it never grows in his session.

    With STEWARD_FIDES_ENFORCE on, his sinks go to a second enforcer with block_on_violation=True: in an untrusted context
    the sink is refused, MAF's refusal is his tool result, and its record says "blocked": true. Both enforcers keep one
    audit log, the session's standalone FIDES scope (_STANDALONE_SESSION_STATE_KEY, security.py:1184-1193), so the
    recorder reads and clears it once.
    """
    labels = LabelTrackingFunctionMiddleware(default_integrity=IntegrityLabel.TRUSTED, auto_hide_untrusted=False)
    fetchers = set(_UNTRUSTED_NOTE_READS | _DOOR_READS | _ESTATE_READ_TOOLS | _WEB_READS)
    policy = PolicyEnforcementFunctionMiddleware(
        allow_untrusted_tools=fetchers, block_on_violation=False, approval_on_violation=False
    )
    blocker = (
        PolicyEnforcementFunctionMiddleware(allow_untrusted_tools=fetchers, block_on_violation=True)
        if fides_enforce_on()
        else None
    )

    async def enforce(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        if blocker is not None and context.function.name in _CHANGES_THINGS:
            await blocker.process(context, call_next)
        else:
            await policy.process(context, call_next)

    async def record_would_block(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        try:
            await call_next()
        finally:
            entries = policy.get_audit_log(context.session)
            if entries:
                policy.clear_audit_log(context.session)
                session_id = getattr(context.session, "session_id", None)
                stamp = datetime.now(timezone.utc).isoformat()
                lines = [
                    json.dumps(
                        {
                            "ts": stamp,
                            "session_id": session_id,
                            "sink": entry.get("function") in _CHANGES_THINGS,
                            "blocked": blocker is not None and entry.get("function") in _CHANGES_THINGS,
                            **entry,
                        },
                        default=str,
                    )
                    for entry in entries
                ]
                try:
                    SAFETY_LOG_DIR.mkdir(parents=True, exist_ok=True)
                    with (SAFETY_LOG_DIR / FIDES_LOG_NAME).open("a", encoding="utf-8") as log:
                        log.write("\n".join(lines) + "\n")
                except OSError as exc:  # a record that cannot be written never fails his call
                    logger.warning("FIDES record not written: %s", exc)

    return [record_would_block, labels, enforce]


async def labelled_mcp_tool(stack: AsyncExitStack, mcp_tool: MCPStreamableHTTPTool, integrity: IntegrityLabel) -> Any:
    """Connect mcp_tool, under MAF's SecureMCPToolProxy when FIDES records: every function it loads, now or later, is
    labelled with integrity (source_integrity) and marked a sink (security.py:4368-4403, :4882). Returns the MCP tool."""
    if not fides_on():
        return await stack.enter_async_context(mcp_tool)
    proxy = await stack.enter_async_context(SecureMCPToolProxy(mcp_tool, default_integrity=integrity))
    return proxy.mcp_tool


# </safety_observe>


# <tool_policy>
# SecondBrain's tool-policy shelf (2026-11-04): a read-only table of which of his tools ask for a card, written by the
# live build to storage/tool-policy.json (gitignored). Read off the built agent, never kept by hand: his own and MCP tools
# from its tool list (an MCP tool's functions carry the approval_mode its approval_mode setting gave each), the
# providers' tools from their before_run on a throwaway session (the memory providers on copies over a throwaway store,
# so nothing of his is read or written), and each "always_require" tool tried against the auto-approval rules the build
# hands MAF's ToolApprovalMiddleware, in order, as it tries them (_tool_approval.py _matches_auto_rule), with an empty
# call outside any run. A rule that approves that call decides the tool ("rule"); one that needs a run or arguments to
# approve (the plan-mode gate) leaves it "always". A write that fails is a logged warning; the build goes on.
TOOL_POLICY_PATH = _WORKING_DIR / "storage" / "tool-policy.json"
_PROVIDER_SOURCES: tuple[tuple[type, str], ...] = (
    (FileAccessProvider, "file access"),
    (SkillsProvider, "skills"),
    (FileMemoryProvider, "memory"),
    (MemoryContextProvider, "memory"),
    (MontyCodeActProvider, "codeact"),
    (HyperlightCodeActProvider, "codeact"),
    (BackgroundAgentsProvider, "background"),
    (TodoProvider, "todos"),
    (AgentModeProvider, "modes"),
)
_MCP_SOURCES = {
    "secondbrain_notes": "mcp:secondbrain", "secondbrain": "mcp:secondbrain", "secondbrain_estate": "mcp:secondbrain", "atlas": "mcp:door"
}
_TOOL_SOURCES = {"get_repo_status": "built-in", "git_commit": "git", "run_shell": "shell", "search_code": "search_code", PR_CHECKS_TOOL: "mcp:door"}


def _rule_entry(rule: Any) -> dict[str, str]:
    doc = (getattr(rule, "__doc__", None) or "").strip()
    return {"name": getattr(rule, "__qualname__", None) or repr(rule), "description": doc.splitlines()[0] if doc else ""}


async def _deciding_rule(name: str, rules: Sequence[Any]) -> Any:
    """The first auto-approval rule that approves an empty call to name outside any run, or None."""
    call = Content.from_function_call(call_id="tool-policy", name=name, arguments={})
    outside = _RUN_SESSION.set(None)
    try:
        for rule in rules:
            try:
                approved = rule(call)
                if asyncio.iscoroutine(approved) or isinstance(approved, Awaitable):
                    approved = await approved
            except Exception:  # noqa: BLE001 - a rule that cannot judge an empty call does not decide it
                continue
            if approved:
                return rule
    finally:
        _RUN_SESSION.reset(outside)
    return None


async def _provider_tools(agent: Agent[Any], scratch: Path) -> list[tuple[str, Any]]:
    """(source, tool) for each tool the agent's providers offer, from their before_run on a throwaway session."""
    from agent_framework import AgentSession, SessionContext  # noqa: PLC0415

    session = AgentSession()
    session.state[MEMORY_OWNER_KEY] = MEMORY_OWNER  # as memory_owner sets it on every run
    found: list[tuple[str, Any]] = []
    for provider in agent.context_providers or []:
        source = next((s for kind, s in _PROVIDER_SOURCES if isinstance(provider, kind)), None)
        if source is None:
            continue
        if isinstance(provider, FileMemoryProvider):
            provider = copy.copy(provider)
            provider.store = FileSystemAgentFileStore(scratch / "file-memory")
        elif isinstance(provider, MemoryContextProvider):
            provider = copy.copy(provider)
            provider.store = MemoryFileStore(scratch / "memory", owner_state_key=MEMORY_OWNER_KEY)
        context = SessionContext(session_id=session.session_id, input_messages=[])
        try:
            await provider.before_run(agent=agent, session=session, context=context, state={})
        except Exception as exc:  # noqa: BLE001 - a provider that cannot list its tools is left out, and said
            logger.warning("Tool policy: %s's tools not read: %s", type(provider).__name__, exc)
            continue
        found.extend((source, t) for t in context.tools)
    return found


async def tool_policy(agent: Agent[Any], rules: Sequence[Any], scratch: Path) -> dict[str, Any]:
    """The tool-policy table of a built agent: each tool's name, source, approval ("always", "never" or "rule", with
    the rule's name and description) and notes."""
    offered: list[tuple[str, Any]] = []
    # MAF's Agent keeps MCP tools apart from the rest (Agent.mcp_tools, agent_framework/_agents.py:1067).
    for item in [*((agent.default_options or {}).get("tools") or []), *(getattr(agent, "mcp_tools", None) or [])]:
        if isinstance(item, MCPStreamableHTTPTool):
            offered.extend((_MCP_SOURCES.get(item.name, f"mcp:{item.name}"), f) for f in item.functions)
        else:
            offered.append((_TOOL_SOURCES.get(getattr(item, "name", ""), "built-in"), item))
    offered.extend(await _provider_tools(agent, scratch))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source, item in offered:
        name = getattr(item, "name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        row: dict[str, Any] = {"name": name, "source": source}
        if getattr(item, "approval_mode", None) != "always_require":
            row["approval"] = "never"
        elif (rule := await _deciding_rule(name, rules)) is not None:
            row["approval"] = "rule"
            row["rule"] = _rule_entry(rule)
        else:
            row["approval"] = "always"
        notes = []
        if name in _CHANGES_THINGS:
            notes.append("refused without a card in plan mode (the plan-mode gate)")
        if source == "mcp:door" and name != PR_CHECKS_TOOL:
            notes.append("SecondBrain's door holds its writes for approval there")
        if name in {f"secondbrain_{t}" for t in ESTATE_ASKS}:
            notes.append("an Estate write: SecondBrain serves it only while it allows writes (Settings, Share)")
        if notes:
            row["notes"] = "; ".join(notes)
        rows.append(row)
    return {"ts": datetime.now(timezone.utc).isoformat(), "tools": rows}


async def write_tool_policy(agent: Agent[Any], rules: Sequence[Any], path: Path | None = None) -> None:
    """Write the agent's tool-policy table to path (TOOL_POLICY_PATH), atomically; a failure is a logged warning."""
    import tempfile  # noqa: PLC0415

    path = path or TOOL_POLICY_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent) as scratch:
            table = await tool_policy(agent, rules, Path(scratch))
        written = path.with_suffix(".tmp")
        written.write_text(json.dumps(table, indent=1), encoding="utf-8")
        written.replace(path)
    except Exception as exc:  # noqa: BLE001 - the table never fails his build
        logger.warning("Tool policy not written (%s): %s", path, exc)


# </tool_policy>


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


async def secondbrain_web_tools(stack: AsyncExitStack, client: Client) -> MCPStreamableHTTPTool:
    """SecondBrain's web tools, connected: a web page is untrusted content to FIDES, labelled at its source as his notes
    are (labelled_mcp_tool, IntegrityLabel.UNTRUSTED; audit 2026-11-04: they were connected unlabelled)."""
    return await labelled_mcp_tool(stack, _secondbrain_web_tools(client), IntegrityLabel.UNTRUSTED)


def _build_web_research_agent(client: OllamaChatClient, web_tools: MCPStreamableHTTPTool) -> Agent[Any]:
    """The guide's lean, web-search-only research agent (claw_step04 _build_research_agent). Its own middleware: the
    web server's error text withheld (withhold_untrusted_errors), and FIDES recording as on Steward (fides_observer)."""
    return Agent(
        client=client,
        name="WebResearchAgent",
        description="Searches the web for recent news and documentation about a single library, tool or topic.",
        tools=[web_tools],
        middleware=[withhold_untrusted_errors([web_tools]), *(fides_observer() if fides_on() else [])],
        instructions=(
            "You research a single library, tool or topic. Use the web search tool to find the most recent, "
            "relevant news and documentation, then return a short, factual summary (3-4 bullet points) "
            "with no preamble."
        ),
        default_options=OLLAMA_OPTIONS,
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
    default_options: dict[str, Any] | None = None,
    extra_tools: Sequence[Any] = (),
    memory_store: Any = None,
    eval_build: bool = False,
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
        default_options: Chat options sent with every model call (MAF's create_harness_agent default_options),
            such as Ollama's num_ctx for the window the model is loaded with.
        extra_tools: Tools a caller adds to his own (the improvement loop's hand_to_coder, step 6).
        memory_store: His automatic memory's store (step 5: MAF's MemoryContextProvider, beside his history).
            Hosts pass steward_memory_store(); evals pass a throwaway one; None leaves it off.
        eval_build: True for an eval's Steward (evals.py passes it): SecondBrain's reads stay (notes, the Charter,
            skills, the web), but the Atlas door (atlas_* and pr_checks) and the note writes are not offered, so an
            eval never parks a card in the user's SecondBrain (live 2026-11-04). A build argument, not an
            environment variable, so the live host cannot be left in it. An eval's build writes no tool-policy
            table; the live build writes storage/tool-policy.json (<tool_policy>).

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
                tools.append(await secondbrain_web_tools(stack, secondbrain_client))
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
            context_providers: list[Any] = [steward_memory(memory_store)] if memory_store is not None else []
            return create_harness_agent(
                client=client or OllamaChatClient(),
                name="Steward",
                agent_instructions=PART2_INSTRUCTIONS,
                tools=[*tools, git_commit],
                history_provider=history_provider,
                file_access_store=FileSystemAgentFileStore(str(_WORKING_DIR)),
                auto_approval_rules=[FileAccessProvider.read_only_tools_auto_approval_rule, small_commit_auto_approval_rule],
                context_providers=context_providers or None,
                # record_written_files: his git_commit commits only the files his file tools wrote (<git_commit>).
                middleware=[record_written_files, *([memory_owner] if memory_store is not None else [])],
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
            # Each chat call's Ollama timings (load, prompt and generation) in its usage and on its span.
            part3_client = _record_ollama_timings(part3_client)
        # Step 4, 4.3: MAF's own tool-call settings on the one client he, his team and the fixer use.
        part3_client.function_invocation_configuration.update(TOOL_CALLS)
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
            default_options=OLLAMA_OPTIONS,
        )
        background_agents: list[Any] = [explorer_agent]
        skill_sources: list[Any] = [FileSkillsSource(str(_SKILLS_DIR), script_runner=subprocess_script_runner)]
        if secondbrain_client is not None:
            # The guide's background research agent and its managed (Foundry Toolbox) skills, on this PC:
            # the research agent searches with SecondBrain's web tools, and SecondBrain's skill notes are
            # read with MCPSkillsSource over the same client, beside the file skills (claw_step04).
            web_tools = await secondbrain_web_tools(stack, secondbrain_client)
            background_agents.append(_build_web_research_agent(part3_client, web_tools))
            skill_sources.append(MCPSkillsSource(client=secondbrain_client))
        skills_source = skill_sources[0] if len(skill_sources) == 1 else AggregatingSkillsSource(skill_sources)
        # Part 4, as MAF's claw_step04 build_claw_agent: the shell and file access can be switched off
        # for a host, skill scripts auto-approved for unattended evals, and load_skill asks no approval
        # ("it only reads a skill's own body"); everything else is Part 3's agent.
        part4 = part == 4
        # A copy per build: MAF's native workflow host builds Steward for every request and refuses a tool object
        # shared between requests (agent_framework_foundry_hosting WorkflowResolver), and git_commit is module-level.
        part3_tools: list[Any] = [*tools, copy.copy(git_commit), *extra_tools]
        if code_search_on():
            # His search_code (<code_search>): reads only, so no card; nothing is embedded until his first search.
            part3_tools.append(code_search_tool())
        # ADR-0001 items 5 and 6: Atlas's door. SecondBrain serves the door's tools on the same MCP
        # client Steward already holds (its share key, as a client: reads run, writes park as holds for
        # the operator), and the door carries his repository as the world `steward`. So the door is one
        # more MCPStreamableHTTPTool on that client, with allowed_tools, as MAF's local-MCP page shows.
        # The door keeps its own authorization, as MAF says host tools must. Only the git tools and the
        # record are offered, the pieces of the branch-check-keep loop; estate_door_gate keeps every
        # call on an Estate repository (ESTATE_WORLDS) and refuses what is never his. An eval's build has no door (eval_build): live 2026-11-04 an eval's commit through
        # it parked a real hold card in the user's SecondBrain.
        if secondbrain_client is not None and not eval_build:
            # His own door: trusted reads; its branch, commit, push and PR are FIDES sinks (labelled_mcp_tool).
            door = await labelled_mcp_tool(
                stack,
                MCPStreamableHTTPTool(
                    name="atlas",
                    mcp_client=secondbrain_client,
                    tool_name_prefix="atlas",
                    allowed_tools=list(_ATLAS_GIT_TOOLS),
                    approval_mode="never_require",
                    load_prompts=False,
                ),
                IntegrityLabel.TRUSTED,
            )
            # And pr_checks over it, one per build like the door itself: a pull request's checks, waited for.
            part3_tools.extend([door, pr_checks_tool(door)])
        # STEWARD_SANDBOX=hyperlight: MAF's Hyperlight CodeAct, if it can run here; Monty otherwise (<sandbox>).
        part3_providers: list[Any] = [codeact_provider()]
        # The MCP tools whose content is untrusted (his notes, the Estate): their error text is withheld from him.
        untrusted_sources: list[Any] = []
        if secondbrain_client is not None:
            # plan-steward-context-memory-reads, piece 2: his notes, to look up the plans and rulings
            # himself (reads, never a card), and his Charter, read through them and put in his
            # instructions before every turn (CharterProvider, design step 1).
            # What a note says is untrusted content to FIDES (labelled_mcp_tool); writing one is a sink.
            # An eval's build reads his notes but never writes one (eval_build): MCPStreamableHTTPTool's allowed_tools.
            note_tools = [t for t in _SECONDBRAIN_NOTES_TOOLS if not (eval_build and t in _SECONDBRAIN_NOTES_ASK)]
            notes = await labelled_mcp_tool(
                stack,
                MCPStreamableHTTPTool(
                    name="secondbrain_notes",
                    mcp_client=secondbrain_client,
                    tool_name_prefix="secondbrain",
                    allowed_tools=note_tools,
                    approval_mode={
                        "always_require_approval": [t for t in note_tools if t in _SECONDBRAIN_NOTES_ASK],
                        "never_require_approval": [t for t in note_tools if t not in _SECONDBRAIN_NOTES_ASK],
                    },
                    load_prompts=False,
                ),
                IntegrityLabel.UNTRUSTED,
            )
            part3_tools.append(notes)
            untrusted_sources.append(notes)
            part3_providers.append(CharterProvider(notes))
            # The Estate (2026-11-04, Kyle: Steward is the agent of the Estate): SecondBrain's estate tools on the same
            # client, MAF's allowed_tools and per-tool approval_mode (estate_approval): the reads never ask, the writes
            # always ask the user's card. An eval's build gets the reads only. A server's log is untrusted to FIDES.
            estate_tools = list(ESTATE_READS if eval_build else (*ESTATE_READS, *ESTATE_ASKS))
            estate = await labelled_mcp_tool(
                stack,
                MCPStreamableHTTPTool(
                    name="secondbrain_estate",
                    mcp_client=secondbrain_client,
                    tool_name_prefix="secondbrain",
                    allowed_tools=estate_tools,
                    approval_mode=estate_approval(estate_tools),
                    load_prompts=False,
                ),
                IntegrityLabel.UNTRUSTED,
            )
            part3_tools.append(estate)
            untrusted_sources.append(estate)
        # plan-steward-context-memory-reads, piece 3: MAF's file memory with one explicit scope, so what
        # he saves in one session is in front of him in the next ("Pass an explicit scope to group
        # memories differently ... across sessions"); the factory's per-session one is switched off.
        part3_providers.append(
            FileMemoryProvider(file_memory_store or FileSystemAgentFileStore(_WORKING_DIR / "agent-file-memory"), scope=_FILE_MEMORY_SCOPE)
        )
        # Step 5: file memory holds what he deliberately keeps; automatic memory, the facts that should just stick
        # (the guide's Part 2 pairs the two).
        if memory_store is not None:
            part3_providers.append(steward_memory(memory_store))
        if not part4 or enable_shell:
            shell = await stack.enter_async_context(_build_shell())
            # Kyle, 2026-10-29: MAF's run_shell text never names the shell, so it is named here
            # (as_function's description), and Steward's own line-ending store keeps a CRLF file CRLF.
            run_shell = shell.as_function(description=shell.as_function().description + " The shell is bash (Git Bash on Windows).")
            # A FIDES sink (Learn's "Annotating sink tools"); as_function takes no additional_properties, so it is set here.
            run_shell.additional_properties = {**(run_shell.additional_properties or {}), "accepts_untrusted": False}
            part3_tools.append(run_shell)
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
        # Step 4, 4.5: reading a skill (load_skill, read_skill_resource) never asks a card, by MAF's own rule;
        # run_skill_script runs code and keeps its card unless the run is unattended.
        # The same rules recover_text_tool_calls reads as "read-only" (READ_ONLY_RULES).
        auto_approval_rules: list[Any] = [*READ_ONLY_RULES]
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
        part3_providers.append(RequestHints())
        gate_middleware, gate_rule = plan_mode_gate(mode_provider)
        auto_approval_rules.insert(0, gate_rule)
        loop_should_continue, loop_next_message = plan_reply_loop(mode_provider, plan_reply_check, todo_provider)
        agent = create_harness_agent(
            client=part3_client,
            name="Steward",
            description="Software engineering and development assistant." if part4 else None,
            agent_instructions=PART3_INSTRUCTIONS,
            tools=part3_tools,
            history_provider=history_provider,
            file_access_store=LineEndingFileStore(str(_WORKING_DIR)) if not part4 or enable_file_access else None,
            disable_file_memory=True,  # his scoped FileMemoryProvider is in context_providers
            # Step 4, 4.5: MAF's CachingSkillsSource under the dedup, as SkillsProvider.from_paths composes it, so the
            # skills are discovered once per build, not every turn. A caller's source is never cached by MAF itself.
            skills_provider=SkillsProvider(
                DeduplicatingSkillsSource(CachingSkillsSource(skills_source)), disable_load_skill_approval=part4
            ),
            background_agents=background_agents,
            auto_approval_rules=auto_approval_rules,
            context_providers=part3_providers,
            middleware=[
                memory_owner, estate_door_gate, *gate_middleware, record_written_files,
                refuse_a_bare_name_the_request_put_in_a_folder, refuse_unicode_punctuation_in_code, todo_ids_by_name(todo_provider),
                point_a_missed_path_at_the_named_one,
                # Before the three that read tool_choice: an empty reply's answer-now turn is a tools-off call.
                tools_off_to_answer_now,
                repair_tool_names, recover_text_tool_calls, answer_when_tools_are_off, record_called_tools,
                withhold_untrusted_errors(untrusted_sources),
                # ADR-0001 item 8: FIDES records what it would block, last (fides_observer); STEWARD_SAFETY_OBSERVE=off drops it.
                *(fides_observer() if fides_on() else []),
                # STEWARD_SANDBOX=hyperlight: innermost, inside FIDES's labels, the shell after untrusted content (<sandbox>).
                *([sandbox_untrusted_shell] if hyperlight_sandbox_on() else []),
            ],
            mode_provider=mode_provider,
            todo_provider=todo_provider,
            # The compaction budget is the window he asks Ollama for (OLLAMA_OPTIONS), so the two cannot drift.
            max_context_window_tokens=_STEWARD_CONTEXT,
            max_output_tokens=8_192,
            disable_web_search=True,
            # ADR-0001 item 3, as MAF's harness_research.py sample: in execute mode the harness
            # re-invokes Steward while his todos are still open, reminding him which ones, and stops
            # for any approval; plan mode stays interactive. Ten passes per turn at most.
            loop_should_continue=loop_should_continue,
            loop_next_message=loop_next_message,
            loop_max_iterations=10,
            # Step 4, 4.2: his Ollama options; a caller's own (the fixer's 32K window) win.
            default_options={**OLLAMA_OPTIONS, **(default_options or {})},
            otel_provider_name=OTEL_PROVIDER_NAME,
        )
        # Outside the loop (create_harness_agent puts AgentLoopMiddleware first, outermost of its own), so it reads the
        # loop's combined non-streaming response, as hosted.py puts the Agent tab's middleware outside it.
        agent.middleware = [answer_once, *(agent.middleware or [])]
        # SecondBrain's tool-policy shelf (<tool_policy>): his live build only. An eval's build writes nothing, nor
        # does a build with a caller's extra tools (the improvement round's diagnoser), which is not the agent he serves.
        if part4 and not eval_build and not extra_tools:
            await write_tool_policy(agent, auto_approval_rules)
        return agent
    raise ValueError(f"Steward is built in parts 1 to 4, not part {part}.")


# </build_steward_agent>
