"""The improvement loop's change step as a MAF workflow (ADR-0001 item 12): attempt, check, then keep or drop.

improvement_loop.py ends at a handoff for the coding agent; this workflow takes one change from it (or any
task) and runs it to a decision. A round that names no task ("improve:" alone in the Agent tab, or no task on
the command line) takes the handoff's first top priority (round_task, step 6, 6.4). It is MAF's checkpoint_with_human_in_the_loop.py sample
(samples/03-workflows/checkpoint), with Steward as the writer:

    prepare -> Steward (diagnose) -> hand-off -> Coder (edit) -> checks
            checks -> (failed, attempts left) repair -> Steward ...
                   -> (passed, or attempts spent) review -> keep | drop | guidance -> Steward

* Steward runs as an agent node, so each tool call that needs approval reaches Kyle as a request_info
  event, as in MAF's agents_with_approval_requests.py (samples/03-workflows/human-in-the-loop).
* The checks are the gate's own model-free checks, run as commands, never model-run evals (Kyle,
  2026-10-30). Their result routes on conditional edges, as in MAF's edge_condition.py.
* Kyle's review is a request_info: "keep", "drop", or guidance that sends the change back to Steward.
  Keep leaves the change in the workspace for its pull request through the gate; drop puts back every
  file the attempt changed or created, leaving files that were already changed before it as they were.
* Every superstep is checkpointed to improvement_loop/checkpoints, so a run paused on a review can be
  resumed later from its checkpoint, as in the sample.
* The fixer is split in two (2026-11-03, the operator: "the fixer doesn't need some big huge model"), Aider's
  architect and editor in MAF's pieces. Steward diagnoses on his own model (gpt-oss, which reads long prompts
  fast): he finds the failure, its cause and the exact lines, and hands each edit to the coder with his
  hand_to_coder tool. The coder is a small MAF Agent on Steward's own model (one model, the operator's ruling
  2026-11-05; STEWARD_CODER_MODEL names another) with only MAF's file tools: reads run at once and every
  write asks its card. Its
  prompt is the brief and the lines it changes, not the harness: round 1's fixer, Steward's whole harness on
  the coder model, opened at 13,466 tokens before reading any code and read about 50 tokens a second.
  The coder is a workflow step, not an agent-as-tool, because MAF does not carry a child agent's approvals to
  its caller (Agent.as_tool: "Use a workflow when approval is interactive").
* A round never changes what grades it (GRADERS: evals.py, harness/steward/evals/ (the eval sets and their
  baselines), diagnosis_feedback.json, .github/workflows/; test_harness.py takes only new tests at its end). edit_problem refuses such a hand-off, and
  refuse_grader_writes, MAF function middleware on the coder and the diagnoser, refuses such a write.

Run from worlds/steward:
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\improvement_loop_workflow.py "<task>"
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\improvement_loop_workflow.py   (the handoff's first priority)
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\improvement_loop_workflow.py --resume <checkpoint id>
"""

from __future__ import annotations

import ast
import asyncio
import copy
import json
import subprocess
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from agent_framework import (
    Agent,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentModeProvider,
    Content,
    Executor,
    FileAccessProvider,
    FileCheckpointStorage,
    FunctionInvocationContext,
    Message,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    function_middleware,
    handler,
    register_checkpoint_type,
    response_handler,
    set_agent_mode,
    tool,
)
from agent_framework._harness._file_access import _apply_replace, _apply_replace_lines, _line_edits
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent as steward  # noqa: E402

_REPO_DIR = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = _REPO_DIR / "improvement_loop" / "checkpoints"
# The gate's model-free legs (.github/workflows/gate.yml): the sample project's tests and the harness checks.
GATE_CHECKS: tuple[tuple[str, ...], ...] = (
    (sys.executable, "-m", "pytest", "-q", "harness/steward/working/sample-project"),
    (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "harness/steward/step04_production_ready/test_harness.py"),
    # Step 6, 6.2: the eval gate, run once on Steward's model; it fails when the small-ask checks drop below the
    # recorded baseline (harness/steward/evals/baselines.json).
    (sys.executable, "-W", "ignore", "harness/steward/step04_production_ready/evals.py", "small", "--gate"),
)
MAX_ATTEMPTS = 3
# The coder's window: its prompt is the brief and the lines it changes, a few thousand tokens, so 16K is ample and
# leaves the card room (a separate coder, qwen2.5-coder:14b, was 12.1 GB at 32K, measured 2026-11-03).
FIXER_CONTEXT = 16_384
# The most lines one edit may hand the coder: a function's worth, so its prompt stays short.
EDIT_SPAN_MAX = 80
_EXCERPT_MARGIN = 3
HAND_TO_CODER = "hand_to_coder"
CODER_INSTRUCTIONS = (
    "You are the coder. You are given one or more edits: a file, its numbered lines as they are now, and the "
    "change wanted. Make each edit with file_access_replace (old_string: the exact current text, without the "
    "line numbers; new_string: the new text) or file_access_replace_lines. Read more lines with "
    "file_access_read_lines only if you must. Keep the file's indentation and style. Change nothing else. Then "
    "stop and say, one line per edit, what you changed."
)

# What grades a round is never changed in one (audit, 2026-11-03: the improve skill only asked). Paths are relative to
# the workspace; one ending in "/" is a folder.
GRADERS = (
    "harness/steward/step04_production_ready/evals.py",
    "harness/steward/evals/",
    "harness/steward/step04_production_ready/diagnosis_feedback.json",
    ".github/workflows/",
)
# The gate's own tests take a round's new test (the improve skill's step 4) and nothing else: new test functions added
# after the file's last line. An existing test, changed or shadowed by a same-named one, would grade the round too.
GATE_TESTS = "harness/steward/step04_production_ready/test_harness.py"
GRADER_REFUSAL = (
    "Refused: {file} grades the improvement round, so a round never changes it. Fix the harness itself; the gate's "
    "checks judge the change."
)
GATE_TESTS_REFUSAL = (
    "Refused: {file} holds the gate's own tests. A round only adds new test functions (def test_..., no decorator, a "
    "name not already in the file) after its last line; it never changes or removes what is committed."
)


def _workspace_path(name: str) -> Path:
    return (steward._WORKING_DIR.resolve() / str(name).replace("\\", "/")).resolve()  # noqa: SLF001


def grader_named(name: str) -> str | None:
    """The grader a workspace path is (or is inside), or None."""
    path = _workspace_path(name)
    for grader in GRADERS:
        target = _workspace_path(grader)
        if path == target or (grader.endswith("/") and path.is_relative_to(target)):
            return grader
    return None


def adds_only_new_tests(old: str, new: str) -> bool:
    """Whether new is old with only new, undecorated test functions after its last line (read by ast)."""
    if not new.startswith(old if not old or old.endswith("\n") else old + "\n"):
        return False
    try:
        before, after = ast.parse(old), ast.parse(new)
    except SyntaxError:
        return False
    names = {getattr(statement, "name", None) for statement in before.body}
    added = after.body[len(before.body):]
    return bool(added) and all(
        isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
        and s.name.startswith("test_") and s.name not in names and not s.decorator_list
        for s in added
    )


def grader_write_problem(name: str, arguments: Mapping[str, Any]) -> str | None:
    """Why a call to one of MAF's write tools may not run in a round, or None (any other call, any other file)."""
    if name not in FileAccessProvider._WRITE_TOOL_NAMES:  # noqa: SLF001 - MAF's own set of its write tools
        return None
    file = str(arguments.get("file_name") or "")
    if grader_named(file):
        return GRADER_REFUSAL.format(file=file)
    if _workspace_path(file) != _workspace_path(GATE_TESTS):
        return None
    old = _workspace_path(GATE_TESTS).read_text(encoding="utf-8")  # universal newlines: "\n", as Steward's store reads

    def lf(text: Any) -> str:
        return str(text or "").replace("\r\n", "\n")

    try:  # the file the call would leave, by MAF's own edit functions (agent_framework/_harness/_file_access.py)
        if name == FileAccessProvider.REPLACE_TOOL_NAME:
            new, _ = _apply_replace(old, lf(arguments.get("old_string")), lf(arguments.get("new_string")), bool(arguments.get("replace_all")))
        elif name == FileAccessProvider.REPLACE_LINES_TOOL_NAME:
            new = _apply_replace_lines(old, _line_edits(list(arguments.get("edits") or [])))
        elif name == FileAccessProvider.WRITE_TOOL_NAME:
            new = lf(arguments.get("content"))
        else:
            return GATE_TESTS_REFUSAL.format(file=file)  # a delete
    except (ValueError, KeyError, TypeError):
        return None  # MAF's tool refuses it itself, with its reason, and writes nothing
    # Against the committed file, so the round can still repair the test it added.
    return None if adds_only_new_tests(gate_tests_at_head(), new) else GATE_TESTS_REFUSAL.format(file=file)


def gate_tests_at_head() -> str:
    """The gate's tests as committed ("\\n" endings), or as on disk outside a repository."""
    shown = subprocess.run(
        ["git", "show", f"HEAD:{GATE_TESTS}"], cwd=steward._WORKING_DIR, capture_output=True,  # noqa: SLF001
        text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    text = shown.stdout if shown.returncode == 0 else _workspace_path(GATE_TESTS).read_text(encoding="utf-8")
    return text.replace("\r\n", "\n")


@function_middleware
async def refuse_grader_writes(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """MAF function middleware on the round's coder and diagnoser: a write to a grader is answered with the reason and
    never runs. Learn concepts/agents/middleware/termination: set context.result and do not call call_next."""
    arguments = context.arguments
    arguments = arguments.model_dump() if isinstance(arguments, BaseModel) else dict(arguments or {})
    if refusal := grader_write_problem(context.function.name, arguments):
        context.result = refusal
        return
    await call_next()


@tool(name=HAND_TO_CODER)
def hand_to_coder(
    file: Annotated[str, "The file to change, relative to the workspace, e.g. harness/steward/step04_production_ready/agent.py"],
    start_line: Annotated[int, "The first line to change (1-based)"],
    end_line: Annotated[int, f"The last line to change (inclusive; at most {EDIT_SPAN_MAX} lines in all)"],
    change: Annotated[str, "The change in plain words: what these lines must say or do after the edit"],
) -> str:
    """Hand one edit to the coder, who makes it: the coder sees only these lines and your words. Call it once per
    edit (the fix and the test that proves it are two edits), then stop. Do not edit files yourself."""
    return "Handed to the coder."


def fixer_client() -> Any:
    """The coder's chat client (Steward's own model unless STEWARD_CODER_MODEL names another), with Steward's
    governance, malformed-tool-call retry and Ollama timings, so a coder on another model shows its loads in traces."""
    from agent_framework_ollama import OllamaChatClient  # noqa: PLC0415

    client = OllamaChatClient(model=steward._coder_model(), middleware=steward._build_governance_middleware())  # noqa: SLF001
    return steward._record_ollama_timings(steward._retry_malformed_tool_calls(client))  # noqa: SLF001


def build_coder(client: Any = None) -> Agent[Any]:
    """The coder: a small MAF Agent on the coder model with only MAF's file tools (reads at once, every write on
    its card), Steward's tool-call limits, and a 16K window."""
    client = client or fixer_client()
    client.function_invocation_configuration.update(steward.TOOL_CALLS)
    files = FileAccessProvider(
        steward.LineEndingFileStore(str(steward._WORKING_DIR)),  # noqa: SLF001
        disable_readonly_tool_approval=True,
    )
    return Agent(
        client=client,
        name="Coder",
        description="Makes the edits Steward hands it, and nothing else.",
        instructions=CODER_INSTRUCTIONS,
        context_providers=[files],
        default_options={**steward.OLLAMA_OPTIONS, "num_ctx": FIXER_CONTEXT},
        # The graders' gate. It refuses after the card, as the write would run: no rule skips the card for it, so
        # without the gate a grader's write is only ever a card, never written unasked. And Steward's own gate on
        # Unicode punctuation in code (agent.refuse_unicode_punctuation_in_code), for the coder's writes too.
        middleware=[refuse_grader_writes, steward.refuse_unicode_punctuation_in_code],
    )


async def build_diagnoser(stack: AsyncExitStack, client: Any = None, **build: Any) -> Any:
    """The diagnoser: Steward's own harness on his own model, with hand_to_coder beside his tools, and the graders'
    gate on his file tools (only here: outside a round he edits tests as ever)."""
    # A copy per build: MAF's workflow host refuses a tool object shared between requests (as git_commit).
    agent = await steward.build_steward_agent(stack, client=client, extra_tools=[copy.copy(hand_to_coder)], **build)
    agent.middleware = [refuse_grader_writes, *(agent.middleware or [])]
    return agent


@dataclass
class Edit:
    """One edit Steward handed to the coder."""

    file: str
    start_line: int
    end_line: int
    change: str


def handed_edits(response: AgentExecutorResponse) -> list[Edit]:
    """The edits in Steward's hand_to_coder calls this turn, in order."""
    edits: list[Edit] = []
    for message in response.agent_response.messages:
        for content in message.contents:
            if content.type != "function_call" or content.name != HAND_TO_CODER:
                continue
            args = content.arguments
            args = json.loads(args) if isinstance(args, str) else dict(args or {})
            edits.append(Edit(str(args.get("file", "")), int(args.get("start_line", 0)), int(args.get("end_line", 0)), str(args.get("change", ""))))
    return edits


def _lines(edit: Edit) -> list[str]:
    return (steward._WORKING_DIR / edit.file).read_text(encoding="utf-8").splitlines()  # noqa: SLF001


def edit_problem(edit: Edit) -> str | None:
    """Why an edit cannot go to the coder, or None: a file in the workspace and no grader, real lines, a short span."""
    root = steward._WORKING_DIR.resolve()  # noqa: SLF001
    path = (root / edit.file).resolve()
    if not edit.file or not path.is_relative_to(root) or not path.is_file():
        return f"{edit.file!r} is not a file in the workspace."
    if grader_named(edit.file):
        return GRADER_REFUSAL.format(file=edit.file)
    count = len(_lines(edit))
    added_from = len(gate_tests_at_head().splitlines()) + 1 if path == _workspace_path(GATE_TESTS) else 0
    if added_from and edit.end_line != count and edit.start_line < added_from:  # neither the last line nor a new test
        return (
            f"{edit.file} lines {edit.start_line}-{edit.end_line}: the gate's own tests only take a new test after the "
            f"file's last line; hand line {count} and say 'add after it'."
        )
    if not 1 <= edit.start_line <= edit.end_line <= count:
        return f"{edit.file} lines {edit.start_line}-{edit.end_line}: the file has {count} lines."
    if edit.end_line - edit.start_line + 1 > EDIT_SPAN_MAX:
        return f"{edit.file} lines {edit.start_line}-{edit.end_line}: more than {EDIT_SPAN_MAX} lines; split it."
    if not edit.change.strip():
        return f"{edit.file} lines {edit.start_line}-{edit.end_line}: no change was described."
    return None


def coder_prompt(edits: Sequence[Edit]) -> str:
    """The coder's whole prompt: each edit's change and its lines as they are now, numbered, with a margin."""
    parts = []
    for number, edit in enumerate(edits, start=1):
        lines = _lines(edit)
        first = max(1, edit.start_line - _EXCERPT_MARGIN)
        last = min(len(lines), edit.end_line + _EXCERPT_MARGIN)
        shown = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(first, last + 1))
        parts.append(
            f"EDIT {number}: {edit.file}, lines {edit.start_line}-{edit.end_line}\n"
            f"CHANGE: {edit.change.strip()}\n"
            f"LINES NOW (lines {first}-{last}):\n{shown}"
        )
    return "\n\n".join(parts) + "\n\nMake these edits, then stop and say what you changed."
_OUTPUT_TAIL = 3000


def _changed_paths() -> tuple[set[str], set[str]]:
    """(changed tracked files, untracked files) in the workspace, from git status."""
    lines = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "."],
        cwd=steward._WORKING_DIR, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    tracked = {line[3:] for line in lines if not line.startswith("??")}
    untracked = {line[3:] for line in lines if line.startswith("??")}
    return tracked, untracked


def round_task(task: str) -> str:
    """The round's task: the failure the user named, or, when the round names none, the diagnosis's first top
    priority from improvement_loop.py's handoff (the cookbook's handoff to the coding agent). No handoff, or one
    without top_priorities, stops the round with the reason."""
    task = task.strip()
    if task.lower().startswith("improve:"):  # the Agent tab's improve conversations (step 6, 6.3)
        task = task[len("improve:"):].strip()
    if task:
        return task
    import improvement_loop as diagnosis  # noqa: PLC0415

    return diagnosis.handoff_task(diagnosis.HANDOFF_PATH)


@dataclass
class CheckReport:
    """One attempt's check results, routed by the edges after the checks."""

    attempt: int
    passed: bool
    summary: str
    output: str


@dataclass
class ReviewRequest:
    """Kyle's review of a checked attempt (serialised into checkpoints)."""

    prompt: str = ""
    summary: str = ""
    passed: bool = False
    attempt: int = 0
    changed: list[str] = field(default_factory=list)
    output: str = ""


@dataclass
class LoopResult:
    """The workflow's output: what was decided, and which files the attempt touched."""

    decision: str
    passed: bool
    attempts: int
    changed: list[str] = field(default_factory=list)
    summary: str = ""


class PrepareTask(Executor):
    """Records what was already changed in the workspace, then hands Steward the task."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def prepare(self, task: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        task = round_task(task)
        tracked, untracked = _changed_paths()
        ctx.set_state("task", task.strip())
        ctx.set_state("before_tracked", sorted(tracked))
        ctx.set_state("before_untracked", sorted(untracked))
        prompt = (
            "This is an improvement round: follow your improve skill. Find the cause, then hand each edit to the "
            f"coder with {HAND_TO_CODER} and stop; you do not edit files yourself. The gate's checks run after the "
            f"coder.\n\nTASK: {task.strip()}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )


class RunChecks(Executor):
    """Runs the checks after each attempt and reports the result."""

    def __init__(self, id: str, checks: Sequence[Sequence[str]]) -> None:
        super().__init__(id=id)
        self._checks = [list(check) for check in checks]
        self._attempt = 0

    @handler
    async def run_checks(self, response: AgentExecutorResponse, ctx: WorkflowContext[CheckReport]) -> None:
        self._attempt += 1
        outputs: list[str] = []
        passed = True
        for check in self._checks:
            done = await asyncio.to_thread(
                subprocess.run, check, cwd=_REPO_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            outputs.append(f"$ {' '.join(check)}\n(exit {done.returncode})\n{(done.stdout + done.stderr)[-_OUTPUT_TAIL:]}")
            passed = passed and done.returncode == 0
        await ctx.send_message(
            CheckReport(self._attempt, passed, response.agent_response.text, "\n\n".join(outputs))
        )

    async def on_checkpoint_save(self) -> dict[str, Any]:
        return {"attempt": self._attempt}

    async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
        self._attempt = state.get("attempt", 0)


class HandToCoder(Executor):
    """Takes the edits Steward handed over: good ones go to the coder with their lines; a bad one goes back to
    Steward with the reason (twice at most); a turn with no edit goes straight to the checks."""

    def __init__(self, id: str, coder_id: str, diagnoser_id: str, checks_id: str) -> None:
        super().__init__(id=id)
        self._coder_id, self._diagnoser_id, self._checks_id = coder_id, diagnoser_id, checks_id
        self._returned = 0

    @handler
    async def hand(
        self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest | AgentExecutorResponse]
    ) -> None:
        edits = handed_edits(response)
        problems = [problem for edit in edits if (problem := edit_problem(edit))]
        if problems and self._returned < 2:
            self._returned += 1
            prompt = (
                f"These edits could not go to the coder:\n- " + "\n- ".join(problems)
                + f"\nCall {HAND_TO_CODER} again with corrected edits, then stop."
            )
            await ctx.send_message(
                AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
                target_id=self._diagnoser_id,
            )
            return
        good = [edit for edit in edits if edit_problem(edit) is None]
        if not good:
            await ctx.send_message(response, target_id=self._checks_id)
            return
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[coder_prompt(good)])], should_respond=True),
            target_id=self._coder_id,
        )

    async def on_checkpoint_save(self) -> dict[str, Any]:
        return {"returned": self._returned}

    async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
        self._returned = state.get("returned", 0)


def needs_repair(report: Any) -> bool:
    """Edge condition: the checks failed and attempts are left."""
    return isinstance(report, CheckReport) and not report.passed and report.attempt < MAX_ATTEMPTS


def ready_for_review(report: Any) -> bool:
    """Edge condition: the checks passed, or the attempts are spent."""
    return isinstance(report, CheckReport) and (report.passed or report.attempt >= MAX_ATTEMPTS)


class AskForRepair(Executor):
    """Sends the failing checks back to Steward."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def ask(self, report: CheckReport, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        prompt = (
            f"The checks failed after attempt {report.attempt} of {MAX_ATTEMPTS}. Find the cause and hand the fix to "
            f"the coder with {HAND_TO_CODER}, then stop.\n\nCheck output:\n{report.output}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )


class ReviewGateway(Executor):
    """Kyle's review: keep, drop, or guidance back to Steward (the sample's ReviewGateway)."""

    def __init__(self, id: str, agent_id: str) -> None:
        super().__init__(id=id)
        self._agent_id = agent_id

    @handler
    async def on_report(self, report: CheckReport, ctx: WorkflowContext) -> None:
        tracked, untracked = _changed_paths()
        before = set(ctx.get_state("before_tracked") or []) | set(ctx.get_state("before_untracked") or [])
        await ctx.request_info(
            request_data=ReviewRequest(
                prompt="Reply 'keep', 'drop', or guidance for another attempt.",
                summary=report.summary,
                passed=report.passed,
                attempt=report.attempt,
                changed=sorted((tracked | untracked) - before),
                output=report.output,
            ),
            response_type=str,
        )

    @response_handler
    async def on_review(
        self, original_request: ReviewRequest, reply: str, ctx: WorkflowContext[AgentExecutorRequest, LoopResult]
    ) -> None:
        decision = reply.strip()
        if decision.lower() in {"keep", "drop"}:
            if decision.lower() == "drop":
                self._drop(ctx)
            await ctx.yield_output(
                LoopResult(
                    decision=decision.lower(), passed=original_request.passed, attempts=original_request.attempt,
                    changed=original_request.changed, summary=original_request.summary,
                )
            )
            return
        prompt = (
            f"Kyle reviewed attempt {original_request.attempt}. Revise the change, handing each edit to the coder "
            f"with {HAND_TO_CODER}: {decision}"
        )
        await ctx.send_message(
            AgentExecutorRequest(messages=[Message("user", contents=[prompt])], should_respond=True),
            target_id=self._agent_id,
        )

    def _drop(self, ctx: WorkflowContext[Any, Any]) -> None:
        """Put back what the attempt changed: tracked files to HEAD, new files removed; earlier changes stay."""
        tracked, untracked = _changed_paths()
        restore = sorted(tracked - set(ctx.get_state("before_tracked") or []))
        if restore:
            subprocess.run(
                ["git", "restore", "--source=HEAD", "--staged", "--worktree", "--", *restore],
                cwd=steward._WORKING_DIR, check=True,
            )
        for path in sorted(untracked - set(ctx.get_state("before_untracked") or [])):
            (steward._WORKING_DIR / path).unlink(missing_ok=True)


def create_workflow(
    agent: Any,
    coder: Any,
    checkpoint_storage: FileCheckpointStorage | None,
    checks: Sequence[Sequence[str]] = GATE_CHECKS,
) -> Workflow:
    """The loop's graph, the same for a new run and for a resume."""
    register_checkpoint_type(CheckReport)
    register_checkpoint_type(ReviewRequest)
    register_checkpoint_type(LoopResult)
    # The loop is the user's go for the change, so Steward works it in execute mode (2026-11-01: plan mode's
    # gate refuses changes); the application sets the mode, as MAF allows, and every write still asks its card.
    session = agent.create_session()
    modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
    set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
    attempt = AgentExecutor(agent, session=session, id="steward")
    edit = AgentExecutor(coder, id="coder")
    hand_off = HandToCoder(id="hand_off", coder_id="coder", diagnoser_id="steward", checks_id="checks")
    prepare = PrepareTask(id="prepare", agent_id="steward")
    checks_executor = RunChecks(id="checks", checks=checks)
    repair = AskForRepair(id="repair", agent_id="steward")
    review = ReviewGateway(id="review", agent_id="steward")
    return (
        WorkflowBuilder(
            # A fixed name: the host checks a reply's rebuilt graph against the stored one by name and signature.
            name="steward_improve",
            # Each attempt is about four supersteps; this leaves room for MAX_ATTEMPTS and two reviews.
            max_iterations=40,
            start_executor=prepare,
            checkpoint_storage=checkpoint_storage,
            output_from=[review],
        )
        .add_edge(prepare, attempt)
        .add_edge(attempt, hand_off)
        .add_edge(hand_off, edit)
        .add_edge(hand_off, attempt)  # an edit that cannot go to the coder goes back with the reason
        .add_edge(hand_off, checks_executor)  # no edit handed: straight to the checks
        .add_edge(edit, checks_executor)
        .add_edge(checks_executor, repair, condition=needs_repair)
        .add_edge(checks_executor, review, condition=ready_for_review)
        .add_edge(repair, attempt)
        .add_edge(review, attempt)  # Kyle's guidance loops back
        .build()
    )


def _answer(request_id: str, data: Any) -> Any:
    """Ask Kyle in the console: a tool approval (y/n) or the review (keep, drop or guidance)."""
    if isinstance(data, Content) and data.type == "function_approval_request" and data.function_call is not None:
        print(f"\n=== Approval: {data.function_call.name} {data.function_call.arguments} ===")
        return data.to_function_approval_response(approved=input("Approve? (y/n): ").strip().lower() == "y")
    if isinstance(data, ReviewRequest):
        print(f"\n=== Review: attempt {data.attempt}, checks {'passed' if data.passed else 'failed'} ===")
        print(data.summary, "\nChanged:", ", ".join(data.changed) or "(nothing)", "\n" + data.output[-1500:])
        return input(data.prompt + " ").strip()
    raise ValueError(f"Unexpected request {request_id}: {type(data).__name__}")


async def run_loop(workflow: Workflow, *, task: str | None = None, checkpoint_id: str | None = None) -> LoopResult:
    """Run until the review decides, answering each request in the console (the sample's interactive session)."""
    responses: dict[str, Any] | None = None
    while True:
        if responses:
            events = await workflow.run(responses=responses)
        elif task is not None:
            events = await workflow.run(task)
        else:
            events = await workflow.run(checkpoint_id=checkpoint_id)
        if outputs := events.get_outputs():
            return outputs[0]
        requests = events.get_request_info_events()
        if not requests:
            raise RuntimeError("The workflow stopped without a decision or a request.")
        responses = {request.request_id: _answer(request.request_id, request.data) for request in requests}


async def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(_REPO_DIR / ".env")
    resume = len(sys.argv) == 3 and sys.argv[1] == "--resume"
    if not resume and len(sys.argv) > 2:
        raise SystemExit(__doc__)
    storage = FileCheckpointStorage(storage_path=CHECKPOINT_DIR)
    async with AsyncExitStack() as stack:
        agent = await stack.enter_async_context(await build_diagnoser(stack))
        workflow = create_workflow(agent, build_coder(), storage)
        if resume:
            result = await run_loop(workflow, checkpoint_id=sys.argv[2])
        else:
            result = await run_loop(workflow, task=sys.argv[1] if len(sys.argv) == 2 else "")
    print(f"\nDecision: {result.decision} after {result.attempts} attempt(s); checks {'passed' if result.passed else 'failed'}.")
    print("Changed:", ", ".join(result.changed) or "(nothing)")


if __name__ == "__main__":
    asyncio.run(main())
