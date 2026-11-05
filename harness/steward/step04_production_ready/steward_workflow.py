"""Steward's stages as a MAF workflow (Kyle, 2026-11-01: "the harness makes it actually follow the rules").

MAF's builder skill (references/harness-agent-builder.md): "Use a workflow instead when explicit graph topology,
routing, checkpointed stages, or intermediate outputs define correctness." Plan, approve, execute, check and report
are such stages, so their order is the graph's, not the model's choice.

Pieces 1 to 4 of the build order:

    request -> route (one structured-output call: Route) -> (answer) answer (AgentExecutor, plain words; plan mode,
            so reads run and writes are refused) | (task, or no Route: Default) plan
    plan (AgentExecutor, plan mode, structured output StewardPlan) -> read_plan
            -> ask_approval (the workflow pauses: ctx.request_info) -> execute (AgentExecutor, execute mode) -> check
            -> (failed, attempts left) repair -> execute -> check ...
            -> (passed on changed code) ask_commit ("Checks passed") -> commit (one structured-output call writes the
               message: CommitMessage; the workflow raises his git_commit's card with it, and runs it on Approve)
            -> (nothing changed, or attempts spent) report

* ROUTE comes first (live 2026-11-03: a question came back as an approval card, "No further action needed"). Learn,
  Workflows > Edges, switch-case (python pivot): a classifier with structured output gives a typed message and
  add_switch_case_edge_group routes it, with a Default branch. One short call on Steward's own client.
* PLAN and EXECUTE are MAF AgentExecutors, so evaluate_workflow can score each step ("Ensure the workflow uses
  AgentExecutor-based agents", agent_framework/_evaluation.py). Each keeps its own session, which MAF saves in
  the workflow's checkpoint at the pause and restores on the answer.
* The plan is structured output (the guide's PlanningResponse, plus its steps), read in code (the cookbook:
  "Validate JSON ... in code"). A clarification, or a reply that holds no plan, ends the run with that reply;
  the user's answer is the next request.
* The approval is a function_approval_request, so MAF's host sends it as the Responses mcp_approval_request
  (agent_framework_foundry_hosting/_workflow_responses.py) and the Agent tab shows its Allow/Deny card. Denied,
  the run ends and nothing has run.
* Approved, EXECUTE is asked to carry the plan out. The approved plan rides on that message, and approved_plan_turn
  (agent middleware) puts EXECUTE's own session in execute mode and writes the plan's steps as its todos, so he
  never has to remember todos_add and the todos live where MAF checkpoints them. MAF's todo loop keeps him going
  until they are done; every write still asks on its own card.
* CHECK is model-free, as the improvement loop's (improvement_loop_workflow.py, after MAF's edge_condition.py):
  the Python files EXECUTE wrote (MAF's own write tools, FileAccessProvider._WRITE_TOOL_NAMES) have the tests in
  their folders run. Failing with attempts left, REPAIR hands EXECUTE the output; passing, or after MAX_ATTEMPTS,
  REPORT gives his answer with the checks' result. Nothing written, nothing run. The attempt count is workflow
  state, so it is in the checkpoint across a write card's pause.
* COMMIT takes only the files EXECUTE's run wrote with MAF's file tools (agent.record_written_files keeps them in
  EXECUTE's session, which MAF checkpoints; a new approved plan starts the list again), never every change in the
  workspace (audit 2026-11-04), and his git_commit runs through the agent's function middleware as any approved call.
* COMMIT does not leave the tool call to the model (live evals 2026-11-04, three runs: gpt-oss asked "Do you approve
  this commit?" in words and never called git_commit; Ollama's tool_choice takes only auto or none). The model only
  writes the message, as structured output (CommitMessage, as ROUTE's Route), and the workflow raises git_commit's
  card itself with it (ctx.request_info, as ASK_APPROVAL's approve_plan); Approve runs his git_commit, Deny commits
  nothing. A message that fails to parse is asked again once, then a fixed one is built from the request and files.
* Hosting (MAF native, Kyle's choice 2026-11-01): ResponsesHostServer(workflow=factory) builds a fresh graph and a
  fresh Steward for every request ("Native workflow requests cannot share workflows, executors, agents, clients,
  or providers", _workflow_source.py), so the factory is in hosted.py.

Run one request through it on Ollama (PLAN only reads; it stops at the approval):
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\steward_workflow.py "<request>"
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agent_framework import (
    Agent,
    AgentContext,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentModeProvider,
    Case,
    Content,
    Default,
    Executor,
    FileAccessProvider,
    Message,
    TodoItem,
    TodoProvider,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    agent_middleware,
    handler,
    response_handler,
    set_agent_mode,
)
from agent_framework._workflows._message_utils import normalize_messages_input
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console.observers.planning_models import PlanningQuestion, PlanningResponse, PlanningResponseType  # noqa: E402
from hosted import IN_WORDS_KEY, planning_response_in, plan_mode_turns  # noqa: E402
# write_happened is agent.py's (his write recorder's), named here as the evals and tests have read it.
from agent import ESTATE_READS, REQUEST_KEY, WRITTEN_FILES_KEY, invoke_through_middleware, write_happened, written_files  # noqa: E402, F401

logger = logging.getLogger(__name__)

# A fixed name: the host checks a reply's rebuilt graph against the stored one by name and signature.
WORKFLOW_NAME = "steward"
ROUTE_STEP = "route"
ANSWER_STEP = "answer"
PLAN_STEP = "plan"
READ_PLAN_STEP = "read_plan"
ASK_APPROVAL_STEP = "ask_approval"
EXECUTE_STEP = "execute"
CHECK_STEP = "check"
REPAIR_STEP = "repair"
REPORT_STEP = "report"
COMMIT_STEP = "commit"
# EXECUTE's attempts at a plan before REPORT says the checks still fail (the improvement loop's MAX_ATTEMPTS).
MAX_ATTEMPTS = 3
_ATTEMPT_KEY = "steward_check_attempt"
_OUTPUT_TAIL = 1500
# The approval card's name: what the user is approving is the plan, carried in its arguments.
APPROVE_PLAN = "approve_plan"
# The approved plan's steps, on the message that asks EXECUTE to carry it out (read by approved_plan_turn).
APPROVED_PLAN_KEY = "steward_approved_plan"
NOT_APPROVED = "The plan was not approved, so nothing was run. Tell me what to change and I will plan again."
# The commit comes after the checks pass (the cookbook's improvement loop: "the system proposes the change set and a
# developer approves the diff before merge"); his git_commit runs on the user's card (the guide's Part 2). The model
# writes only the message (CommitMessage); the workflow raises the card (Commit).
# A repair's one step: the message carries it as his plan, so approved_plan_turn puts EXECUTE back in execute mode with
# it as the todo (live 2026-11-02: his finished todos had returned him to plan mode, and each repair came back a plan).
REPAIR_TODO = "Fix the failing checks"
# The commit message's structured call: COMMIT_PROMPT as its instruction, COMMIT_NOW as the change it describes.
COMMIT_PROMPT = (
    "Write the git commit message for the change below: one line of at most 72 characters, imperative, naming what "
    "changed (the function, file or behaviour), e.g. 'Add item_count to inventory.py'. Never a bare word such as "
    "'Update' or 'Fix'."
)
COMMIT_NOW = "The checks passed on this change. Write its commit message.\n\nRequest: {request}\n\nChanged files:\n{files}\n\nChecks:\n{output}"
# Sent once when the message did not parse (the cookbook's "Validate JSON ... in code": a bad reply is asked again).
COMMIT_AGAIN = "That is not a valid commit message ({error}). Reply with the JSON object only."
# Says which change was not committed (2026-11-04: the bare sentence left a denied run's last reply naming nothing).
COMMIT_NOT_APPROVED = 'The commit "{message}" was not approved, so nothing was committed.'
# The card's tool: his own git_commit (agent.py), found by name on the agent the graph is built over.
GIT_COMMIT = "git_commit"
_COMMIT_SUMMARY_MAX = 72
# The approved request and plan, kept in the workflow's state (so in its checkpoint) for the commit message.
_APPROVED_REQUEST_KEY = "steward_approved_request"
# Sent to PLAN once when its reply was empty; ReadPlan keeps whether it has been sent in the workflow's state.
PLAN_AGAIN = "Your reply was empty. Reply with your plan for the request above."
_PLAN_ASKED_AGAIN_KEY = "steward_plan_asked_again"
# Sent to PLAN once when its reply was a clarification offering no choices (live 2026-11-02, three times in one
# conversation: "Should I proceed?" with the whole plan in its steps). The cookbook's repair loops: "failures become
# structured feedback instead of a dead end"; the definitions are the guide's own (PlanningResponseType).
PLAN_IS_APPROVAL = (
    "Your reply was a clarification that offers no choices, with your plan in its steps. A clarification is for when "
    "you need clarification and want to present the user with options to choose from. An approval is for when you "
    "are ready to start execution but need approval to start executing; the user's Approve on it switches you to "
    "execute mode. If you are asking to go ahead, reply with type approval, a summary of the plan as its one "
    "question, and your steps. If you need an answer first, reply with a clarification whose question lists the "
    "choices."
)
# Sent to PLAN once when its reply was (or ended with) a JSON object that is no plan: a tool call's arguments written
# as text (the bar at 0016cf4, 2026-11-04: '{"query":"pytest"}' in the README ask, the discount fix's
# '{"edits": [...], "file_name": ".../inventory.py"}' in the steps set). recover_text_tool_calls already runs such a
# reply when it names one read (and refuses one gated write); this is what is left, asked again as PLAN_AGAIN is.
PLAN_NOT_A_CALL = (
    "Your reply was a tool call's arguments written as text, not your plan, so nothing ran. A tool runs only as a "
    "tool call. In plan mode only reads run; writes come after the user approves the plan. Reply now with your plan "
    "as the JSON object asked for: type approval, a summary of the plan as its one question, and your steps."
)
_TRAILING_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```\s*\Z", re.S | re.I)
# The router's one instruction, and the line the answer step is given with a question: short, since the graph routes.
ROUTE_PROMPT = (
    'Classify the user\'s request. "answer": a question to answer in words, reading files or read-only tools at '
    "most: what is, show, list, how many, status, logs, history (e.g. 'What is the estate status? Read it with "
    "estate_status.'). \"task\": it asks to change, create, run, fix, commit or send something."
)
# A request that names one of the Estate's read-only tools and asks for no change is a question, whatever the model
# says (live 2026-11-04: "Read it with estate_status and list each service" was routed to the plan).
_CHANGE_WORDS = re.compile(
    r"\b(write|fix|add|commit|restart|update|delete|change|create|edit|remove|send|push|install|stop|start|run|unload|apply)\b",
    re.IGNORECASE,
)
ANSWER_IN_WORDS = "Answer this question in plain words. Read what you need; change nothing; no plan."


class Route(BaseModel):
    """The router's structured output: the classifier's typed result the switch-case edge group routes on."""

    kind: Literal["answer", "task"]


@dataclass
class RoutedRequest(AgentExecutorRequest):
    """The request with its route, as the AgentExecutorRequest both branches take. kind is None when the router's
    reply was no Route, which falls to the Default branch (the plan)."""

    kind: str | None = None


def asks_only_to_read(request: str) -> bool:
    """Whether the request names one of the Estate's read-only tools (ESTATE_READS) and no change (_CHANGE_WORDS)."""
    return any(name in request for name in ESTATE_READS) and not _CHANGE_WORDS.search(request)


def routed_to_answer(request: Any) -> bool:
    """The switch-case's one Case: the router said this is a question to answer in words."""
    return isinstance(request, RoutedRequest) and request.kind == "answer"


class Router(Executor):
    """The classifier before the plan (Learn, Workflows > Edges, switch-case; _workflow_builder.py
    add_switch_case_edge_group): one call on Steward's own client with Route as response_format. Its input handlers
    are AgentExecutor's own (str, Message, list[Message]), so every host starts the graph as it started PLAN."""

    def __init__(self, client: Any, options: dict[str, Any], id: str = ROUTE_STEP) -> None:
        super().__init__(id=id)
        self._client = client
        self._options = options

    @handler
    async def from_str(self, text: str, ctx: WorkflowContext[RoutedRequest]) -> None:
        await self._route(normalize_messages_input(text), ctx)

    @handler
    async def from_message(self, message: Message, ctx: WorkflowContext[RoutedRequest]) -> None:
        await self._route(normalize_messages_input(message), ctx)

    @handler
    async def from_messages(self, messages: list[str | Message], ctx: WorkflowContext[RoutedRequest]) -> None:
        await self._route(normalize_messages_input(messages), ctx)

    async def _route(self, messages: list[Message], ctx: WorkflowContext[RoutedRequest]) -> None:
        request = next((m.text for m in reversed(messages) if m.role == "user" and (m.text or "").strip()), "")
        reply = await self._client.get_response(
            [Message(role="system", contents=[Content.from_text(ROUTE_PROMPT)]), Message(role="user", contents=[Content.from_text(request)])],
            options={**self._options, "response_format": Route},
        )
        try:
            kind: str | None = Route.model_validate_json((reply.text or "").strip()).kind
        except ValueError:
            kind = None  # no Route: the Default branch, the plan as before
        if asks_only_to_read(request):
            kind = "answer"
        if kind == "answer":
            messages = [Message(role="system", contents=[Content.from_text(ANSWER_IN_WORDS)]), *messages]
        await ctx.send_message(RoutedRequest(messages=messages, kind=kind))


class StewardPlan(PlanningResponse):
    """The guide's PlanningResponse with the plan's steps, which become his todo list."""

    # Required and at least one ("required", "minItems": 1 in the schema): Ollama's structured output (format = this
    # schema) enforces only what the schema says, and a model left free sent no steps, or "[ ]" (live, 2026-11-01);
    # a plan without steps has nothing to approve or run.
    steps: list[str] = Field(
        min_length=1,
        description=(
            "The plan's steps in order, one short imperative line each (e.g. 'Read inventory.py', 'Fix the discount "
            "line'). They become your todo list. For a clarification, the first step you will take once answered."
        ),
    )
    # The guide's own description says one or more (exactly one for an approval), but its schema left the list free,
    # and live 2026-11-01 a "clarification" came with no questions and its answer stuffed into steps.
    questions: list[PlanningQuestion] = Field(
        min_length=1, description=PlanningResponse.model_fields["questions"].description
    )


def clarification_text(plan: StewardPlan) -> str:
    """His questions as the user reads them (the run ends on them; the answer is the next request)."""
    lines = []
    for question in plan.questions:
        choices = f" ({' / '.join(question.choices)})" if question.choices else ""
        lines.append(f"{question.message}{choices}")
    return "\n\n".join(lines)


def steward_plan_in(text: str) -> StewardPlan | None:
    """The StewardPlan ending a reply, or None: an approval needs its steps, a clarification its questions."""
    plan = planning_response_in(text, model=StewardPlan)
    if plan is None or (plan.type == PlanningResponseType.APPROVAL and not plan.steps):
        return None
    return plan


def ends_with_a_json_object(text: str) -> bool:
    """Whether text is, or ends with, one non-empty JSON object (fenced or not)."""
    body = (text or "").strip()
    if fenced := _TRAILING_FENCE.search(body):
        body = fenced.group(1)
    if not body.endswith("}"):
        return False
    decoder = json.JSONDecoder()
    for start in (i for i, char in enumerate(body) if char == "{"):
        try:
            value, end = decoder.raw_decode(body, start)
        except ValueError:
            continue
        if end == len(body):
            return isinstance(value, dict) and bool(value)
    return False


def offers_no_choices(plan: StewardPlan) -> bool:
    """A clarification none of whose questions offers a choice: by the guide's definition it presents options."""
    return plan.type == PlanningResponseType.CLARIFICATION and not any(q.choices for q in plan.questions)


def _last_text(response: AgentExecutorResponse) -> str:
    messages = response.agent_response.messages
    return next((m.text for m in reversed(messages) if m.role == "assistant" and (m.text or "").strip()), "")


def _first_user_text(response: AgentExecutorResponse) -> str:
    return next((m.text for m in response.full_conversation or [] if m.role == "user" and (m.text or "").strip()), "")


def execute_message(request: str, plan: str, steps: list[str]) -> Message:
    """The message that asks EXECUTE to carry out the approved plan, with the plan's steps on it."""
    numbered = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1))
    text = (
        f"The user approved your plan. Carry it out now.\n\nRequest: {request}\n\nPlan: {plan}\n\nSteps (your todos):\n"
        f"{numbered}\n\nWork through the todos in order and mark each one complete when it is done. Do not commit: "
        "the checks run when you finish, and once they pass you will be asked to commit."
    )
    # REQUEST_KEY: his request hints match the request alone, never the plan's wording (agent.asked_request).
    return Message(
        role="user", contents=[Content.from_text(text)],
        additional_properties={APPROVED_PLAN_KEY: list(steps), REQUEST_KEY: request},
    )


def approved_plan_turn(mode_provider: AgentModeProvider, todo_provider: TodoProvider) -> Callable[..., Awaitable[None]]:
    """On the message carrying an approved plan: this session goes to execute mode and its todos are the plan's steps.

    Agent middleware, so it runs before the run's mode is read (plan_mode_turns) and acts on the run's own session,
    the one MAF checkpoints and restores (an executor holding a session would hold a stale one after a restore).
    """

    @agent_middleware
    async def approved_plan_turn_(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        steps = approved_steps(context.messages)
        if steps and context.session is not None:
            if list(steps) != [REPAIR_TODO]:
                # A new approved plan is a new run of work: the files it writes are the ones its commit takes.
                context.session.state[WRITTEN_FILES_KEY] = []
            set_agent_mode(
                context.session, "execute", source_id=mode_provider.source_id, available_modes=mode_provider.available_modes
            )
            items = [TodoItem(id=n, title=str(step)) for n, step in enumerate(steps, start=1)]
            await todo_provider.store.save_state(
                context.session, items, next_id=len(items) + 1, source_id=todo_provider.source_id
            )
        await call_next()

    return approved_plan_turn_


def approved_steps(messages: Sequence[Message] | None) -> list[str] | None:
    """The approved plan's steps carried on a message of this run (execute_message, Repair), or None."""
    return next(
        (
            m.additional_properties[APPROVED_PLAN_KEY]
            for m in messages or []
            if APPROVED_PLAN_KEY in (getattr(m, "additional_properties", None) or {})
        ),
        None,
    )


# Per-step model options (2026-11-04), so each step's reasoning effort and sampling can be measured on its own:
# STEWARD_<STEP>_THINK, STEWARD_<STEP>_TEMPERATURE and STEWARD_<STEP>_SEED, read once when the graph is built. A step
# with none set sends exactly the options it sent before. REPAIR runs on EXECUTE's executor and session (Repair sends
# to EXECUTE_STEP), so it is told apart by the REPAIR_TODO its message carries.
STEP_OPTION_STEPS = (ROUTE_STEP, PLAN_STEP, ANSWER_STEP, EXECUTE_STEP, REPAIR_STEP)
_THINK_VALUES: dict[str, str | bool] = {"low": "low", "medium": "medium", "high": "high", "true": True, "false": False}
# Which step an AgentExecutor's session belongs to, and whether EXECUTE's session is on a repair: session state, so
# both are in the workflow's checkpoint across a card's pause (AgentExecutor.on_checkpoint_save, agent_session).
STEP_KEY = "steward_step"
_REPAIRING_KEY = "steward_repairing"


def step_options_from_env(environ: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Each step's option overrides from the environment; a step with none set is absent. A bad value raises.

    think is Ollama's own top-level chat argument: MAF's OllamaChatClient passes a key that is not a model option to
    AsyncClient.chat unchanged (agent_framework_ollama/_chat_client.py, _prepare_options lines 454-464, then
    **options_dict at 387 and 413), and ollama's chat takes bool or "low" | "medium" | "high" (ollama/_client.py 815),
    as improvement_loop.structured already sends it. temperature and seed are ChatOptions MAF puts in Ollama's nested
    `options` (OLLAMA_MODEL_OPTIONS, _chat_client.py 248 and 252); temperature is held to MAF's own range
    (agent_framework/_types.py validate_chat_options: 0.0 to 2.0).
    """
    environ = os.environ if environ is None else environ
    steps: dict[str, dict[str, Any]] = {}
    for step in STEP_OPTION_STEPS:
        prefix = f"STEWARD_{step.upper()}_"
        options: dict[str, Any] = {}
        if raw := environ.get(f"{prefix}THINK", "").strip():
            if raw.lower() not in _THINK_VALUES:
                raise ValueError(f"{prefix}THINK={raw!r}: use low, medium, high, true or false")
            options["think"] = _THINK_VALUES[raw.lower()]
        if raw := environ.get(f"{prefix}TEMPERATURE", "").strip():
            try:
                temperature = float(raw)
            except ValueError:
                temperature = -1.0
            if not 0.0 <= temperature <= 2.0:
                raise ValueError(f"{prefix}TEMPERATURE={raw!r}: use a number from 0.0 to 2.0")
            options["temperature"] = temperature
        if raw := environ.get(f"{prefix}SEED", "").strip():
            try:
                options["seed"] = int(raw)
            except ValueError:
                raise ValueError(f"{prefix}SEED={raw!r}: use a whole number") from None
        if options:
            steps[step] = options
    return steps


def step_options_turn(step_options: Mapping[str, Mapping[str, Any]]) -> Callable[..., Awaitable[None]]:
    """Agent middleware: this run's options get its step's overrides, as plan_mode_turns sets response_format.

    context.options is the run's options (agent_framework/_middleware.py 2122, AgentMiddlewareLayer._middleware_handler),
    which Agent.run merges over the agent's default_options (agent_framework/_agents.py 1552), so one agent and one
    client serve every step. The step is the run's session's STEP_KEY; EXECUTE's session is on REPAIR from a message
    carrying REPAIR_TODO until a message carries another approved plan, so a repair's resumed run after a card is too.
    """

    @agent_middleware
    async def step_options_turn_(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        session = context.session
        step = session.state.get(STEP_KEY) if session is not None else None
        if session is not None and step == EXECUTE_STEP:
            steps = approved_steps(context.messages)
            if steps is not None:
                session.state[_REPAIRING_KEY] = list(steps) == [REPAIR_TODO]
            if session.state.get(_REPAIRING_KEY):
                step = REPAIR_STEP
        if overrides := step_options.get(str(step)):
            context.options = {**(context.options or {}), **overrides}
        await call_next()

    return step_options_turn_


def step_session(agent: Agent[Any], step: str) -> Any:
    """A new session of the agent's, marked as this step's (STEP_KEY), for the step's AgentExecutor."""
    session = agent.create_session()
    session.state[STEP_KEY] = step
    return session


@dataclass
class CheckReport:
    """One attempt's checks: output is empty when nothing was there to check."""

    attempt: int
    passed: bool
    output: str
    answer: str


# A check: given EXECUTE's messages, (passed, output), or None when there is nothing to check.
Checks = Callable[[Sequence[Message]], "tuple[bool, str] | None"]

# The progress event's type: not one MAF reserves for itself (_workflow_context.py, add_event refuses "output",
# "intermediate", "started", "status" and "failed" from an executor), and not one a host forwards as output.
PROGRESS = "progress"


class StewardProgress(WorkflowEvent[str]):
    """A progress line from CHECK or REPAIR ("checking: pytest -q tests", "check passed", "repair attempt 2/3"), a
    custom event emitted with ctx.add_event, as MAF's Workflow documents: "Can emit custom events via ctx.add_event()
    ... Only workflow-level events (outputs, custom events) and status events are observable to callers"
    (_workflows/_workflow.py). The Responses host passes on only output and request_info events, so it shows nothing
    there yet; a caller streaming the workflow (the console, the evals) reads ``event.data``."""

    def __init__(self, text: str, *, executor_id: str) -> None:
        super().__init__(PROGRESS, text, executor_id=executor_id)  # type: ignore[arg-type]  # a custom type


# How a check, run in a worker thread (asyncio.to_thread copies the context), reports what it is about to run.
_CHECK_PROGRESS: ContextVar[Callable[[str], None] | None] = ContextVar("steward_check_progress", default=None)


def check_progress(text: str) -> None:
    """Report a check's step to the running CHECK, if any (a check run outside the workflow reports nothing)."""
    report = _CHECK_PROGRESS.get()
    if report is not None:
        report(text)


def written_python_files(messages: Sequence[Message]) -> list[str]:
    """The .py files EXECUTE's calls to MAF's file-writing tools named, in order, once each.

    A write that waited on the user's card is not in the response as a call: after the pause, the AgentExecutor's
    response starts from the user's answer (_agent_executor.py), and the call it approves rides on that answer
    (function_approval_response.function_call). So approved answers count, and denied ones do not.

    A call whose tool result is in the messages counts only when the result says the write happened (MAF's own
    words, _file_access.py: "File '...' written.", "Replaced ...", "File '...' deleted."): an approved card can still
    be refused by his write middleware (whole_write_problem, the Unicode-punctuation check) or fail in the tool
    ("already exists"), and nothing is written (audit 2026-11-04). A response with no tool results (MAF's
    WorkflowAgent forwards assistant messages only) is read as before; the evals then ask the disk.
    """
    results = {
        content.call_id: str(content.result or "")
        for message in messages
        for content in message.contents or []
        if content.type == "function_result" and content.call_id
    }
    files: list[str] = []
    for message in messages:
        for content in message.contents or []:
            if content.type == "function_call":
                call = content
            elif content.type == "function_approval_response" and content.approved:
                call = content.function_call
            else:
                continue
            if call is None or call.name not in FileAccessProvider._WRITE_TOOL_NAMES:  # noqa: SLF001
                continue
            if call.call_id in results and not write_happened(results[call.call_id]):
                continue
            name = str((call.parse_arguments() or {}).get("file_name") or "")
            if name.endswith(".py") and name not in files:
                files.append(name)
    return files


# Set on the check's own pytest, so a workflow run inside those tests does not start the check again.
_CHECK_RUNNING = "STEWARD_CHECK_RUNNING"
# pytest's exit code when it collected no tests (pytest.ExitCode.NO_TESTS_COLLECTED).
_NO_TESTS_COLLECTED = 5
NO_TESTS_RAN = "No tests ran for the changed files in {target}: add a test there that covers the change."


def changed_python_files(workspace: Path) -> list[str]:
    """The .py files in the workspace that differ from the committed state (changed or new), as git lists them."""
    done = subprocess.run(
        ["git", "ls-files", "--modified", "--others", "--exclude-standard", "--", "*.py"],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return sorted(set(done.stdout.split())) if done.returncode == 0 else []


def changed_files(workspace: Path | None = None) -> list[str]:
    """The files under the workspace that differ from the committed state (changed, new or deleted), as git lists
    them. Since the audit of 2026-11-04 his git_commit stages only the files his run wrote (agent.written_files), and
    the commit step lists those; this is every change, his or not."""
    if workspace is None:
        from agent import _WORKING_DIR as workspace  # noqa: PLC0415 - the folder his git_commit commits in

    done = subprocess.run(
        ["git", "ls-files", "--modified", "--deleted", "--others", "--exclude-standard", "--", "."],
        cwd=workspace, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return sorted(set(done.stdout.split())) if done.returncode == 0 else []


def python_tests_for_changes(messages: Sequence[Message], workspace: Path | None = None) -> tuple[bool, str] | None:
    """The tests in the folder of each changed .py file (pytest). None when no code changed (a docs-only change).

    A folder where pytest collects no tests (its exit 5) fails the check with NO_TESTS_RAN, which the repair reads: a
    code change nothing tested has passed nothing (audit, 2026-11-03: the check passed vacuously). The cookbook's
    repair loops: the artifact "has to satisfy the checks that matter".

    The check reads the files on disk, not EXECUTE's messages: the cookbook's repair loops validate the artifact itself
    ("The repaired notebook has to satisfy the checks that matter"), and MAF's AgentExecutor hands the next step only
    the messages since the last card (_agent_executor.py, _run_agent_and_emit), so a write approved before a later
    card was missed (live 2026-11-02: an edit card, then two commit cards). The workspace starts each run at the
    committed state, so what differs is his run's work, whichever tool or card wrote it.
    """
    if os.environ.get(_CHECK_RUNNING):
        return None  # inside a check's own pytest: a workflow under test must not start the check again
    if workspace is None:
        from agent import _WORKING_DIR as workspace  # noqa: PLC0415 - the folder his file tools write in

    files = changed_python_files(workspace)
    if not files:
        return None
    targets = sorted({str(Path(f).parent) if str(Path(f).parent) != "." else f for f in files})
    outputs: list[str] = []
    passed = True
    for target in targets:
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target]
        check_progress(f"checking: pytest -q {target}")
        done = subprocess.run(
            command, cwd=workspace, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
            env={**os.environ, _CHECK_RUNNING: "1"},
        )
        output = f"$ pytest -q {target}\n(exit {done.returncode})\n{(done.stdout + done.stderr)[-_OUTPUT_TAIL:]}"
        if done.returncode == _NO_TESTS_COLLECTED:
            output += "\n" + NO_TESTS_RAN.format(target=target)
        outputs.append(output)
        passed = passed and done.returncode == 0
    return passed, "\n\n".join(outputs)


class ReadPlan(Executor):
    """Reads PLAN's reply in code: an approval goes on for the user's approval; anything else ends the run as it is.

    An empty reply (live 2026-11-01: the model's whole answer stayed in its reasoning) is sent back to PLAN once for
    the plan, as the cookbook's "Validate JSON ... in code" has a bad reply asked again; a reply in words is not. So is
    a clarification that offers no choices (live 2026-11-02: his plan, labelled a question), with the guide's
    definitions as the feedback (the cookbook's repair loops). Once per run; the second reply is read as it is.
    """

    def __init__(self, id: str = READ_PLAN_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def read(
        self, response: AgentExecutorResponse, ctx: WorkflowContext[dict[str, Any] | AgentExecutorRequest, Any]
    ) -> None:
        last = _last_text(response)
        plan = steward_plan_in(last)
        if not last.strip():
            again = PLAN_AGAIN
        elif plan is not None:
            again = PLAN_IS_APPROVAL if offers_no_choices(plan) else None
        else:
            again = PLAN_NOT_A_CALL if ends_with_a_json_object(last) else None
        if again and not ctx.get_state(_PLAN_ASKED_AGAIN_KEY, False):
            ctx.set_state(_PLAN_ASKED_AGAIN_KEY, True)
            await ctx.send_message(AgentExecutorRequest(messages=[Message(role="user", contents=[Content.from_text(again)])]), target_id=PLAN_STEP)
            return
        ctx.set_state(_PLAN_ASKED_AGAIN_KEY, False)
        if plan is None:
            await ctx.yield_output(last)
        elif plan.type != PlanningResponseType.APPROVAL:
            await ctx.yield_output(clarification_text(plan))
        else:
            plan_data = {"request": _first_user_text(response), "plan": plan.questions[0].message, "steps": plan.steps}
            await ctx.send_message(plan_data, target_id=ASK_APPROVAL_STEP)


class AskApproval(Executor):
    """The user's approval of the plan (MAF's human input: ctx.request_info). The plan rides in the request, so it is
    in the checkpoint while the run waits. Approved: EXECUTE is asked to carry it out. Denied: nothing runs."""

    def __init__(self, id: str = ASK_APPROVAL_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def ask(self, plan: dict[str, Any], ctx: WorkflowContext[Any, Any]) -> None:
        call_id = f"{APPROVE_PLAN}-{uuid.uuid4().hex[:12]}"
        call = Content.from_function_call(call_id=call_id, name=APPROVE_PLAN, arguments=plan)
        # The card's id is the request's id, as MAF's AgentExecutor raises its approvals (_agent_executor.py), so an
        # answer through workflow.as_agent() (WorkflowAgent keys answers by the approval's id) finds this request.
        await ctx.request_info(
            request_data=Content.from_function_approval_request(id=call_id, function_call=call),
            response_type=Content,
            request_id=call_id,
        )

    @response_handler
    async def on_answer(
        self, original_request: Content, response: Content, ctx: WorkflowContext[AgentExecutorRequest, Any]
    ) -> None:
        if not getattr(response, "approved", False):
            await ctx.yield_output(NOT_APPROVED)
            return
        plan = original_request.function_call.parse_arguments() or {}
        ctx.set_state(_ATTEMPT_KEY, 0)
        ctx.set_state(_APPROVED_REQUEST_KEY, {"request": str(plan.get("request", "")), "plan": str(plan.get("plan", ""))})
        message = execute_message(str(plan.get("request", "")), str(plan.get("plan", "")), list(plan.get("steps") or []))
        await ctx.send_message(AgentExecutorRequest(messages=[message]))


class Check(Executor):
    """Runs the checks on what EXECUTE did (model-free) and reports the attempt."""

    def __init__(self, checks: Checks, id: str = CHECK_STEP) -> None:
        super().__init__(id=id)
        self._checks = checks

    @handler
    async def check(self, response: AgentExecutorResponse, ctx: WorkflowContext[CheckReport]) -> None:
        attempt = int(ctx.get_state(_ATTEMPT_KEY, 0) or 0) + 1
        ctx.set_state(_ATTEMPT_KEY, attempt)
        loop = asyncio.get_running_loop()

        def report(text: str) -> None:  # from the checks' thread: added on the loop, in order, before the check goes on
            asyncio.run_coroutine_threadsafe(ctx.add_event(StewardProgress(text, executor_id=self.id)), loop).result()

        token = _CHECK_PROGRESS.set(report)
        try:
            result = await asyncio.to_thread(self._checks, list(response.full_conversation or response.agent_response.messages))
        finally:
            _CHECK_PROGRESS.reset(token)
        passed, output = result if result is not None else (True, "")
        if output:
            await ctx.add_event(StewardProgress("check passed" if passed else "check failed", executor_id=self.id))
        await ctx.send_message(CheckReport(attempt, passed, output, _last_text(response)))


def needs_repair(report: Any) -> bool:
    """Edge condition: the checks failed and attempts are left."""
    return isinstance(report, CheckReport) and not report.passed and report.attempt < MAX_ATTEMPTS


def ready_to_commit(report: Any) -> bool:
    """Edge condition: the checks ran on changed code and passed, so the work can be committed."""
    return isinstance(report, CheckReport) and report.passed and bool(report.output)


def ready_for_report(report: Any) -> bool:
    """Edge condition: nothing was checked, or the attempts are spent; no commit is offered."""
    if not isinstance(report, CheckReport):
        return False
    return (report.passed and not report.output) or (not report.passed and report.attempt >= MAX_ATTEMPTS)


class AskCommit(Executor):
    """After passing checks, says so, then hands the passing report to COMMIT, which raises the git_commit card."""

    def __init__(self, id: str = "ask_commit") -> None:
        super().__init__(id=id)

    @handler
    async def ask(self, report: CheckReport, ctx: WorkflowContext[CheckReport, Any]) -> None:
        await ctx.yield_output(checks_text(report))
        await ctx.send_message(report)


class CommitMessage(BaseModel):
    """The commit step's structured output: the message alone, so whether to commit is never the model's choice."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # Ollama's structured output enforces the schema's own terms (StewardPlan's note above); the rest is checked here.
    message: str = Field(
        min_length=1,
        max_length=_COMMIT_SUMMARY_MAX,
        description="One imperative line naming what changed, e.g. 'Add item_count to inventory.py'.",
    )

    @field_validator("message")
    @classmethod
    def _names_the_change(cls, message: str) -> str:
        if "\n" in message:
            raise ValueError("one line only")
        if len(message.split()) < 2:
            raise ValueError("name what changed, not one word")
        return message


def commit_message_in(text: str) -> tuple[str | None, str]:
    """The CommitMessage a reply holds, read in code as ROUTE reads its Route: (message, "") or (None, the error)."""
    try:
        return CommitMessage.model_validate_json((text or "").strip()).message, ""
    except ValueError as error:
        return None, str(error).splitlines()[0] if str(error).strip() else type(error).__name__


def fallback_commit_message(request: str, files: Sequence[str]) -> str:
    """A message built from the request and the changed files' names, never empty: the request's first sentence cut at
    a word to fit the summary line, and the files below it."""
    first = next((line.strip() for line in (request or "").splitlines() if line.strip()), "")
    sentence = first.split(". ")[0].rstrip(".").strip()
    names = ", ".join(sorted({Path(f).name for f in files}))
    summary = sentence or (f"Change {names}" if names else "Commit the checked work")
    if len(summary) > _COMMIT_SUMMARY_MAX:
        summary = summary[: _COMMIT_SUMMARY_MAX + 1].rsplit(" ", 1)[0].rstrip(" ,;:") or summary[:_COMMIT_SUMMARY_MAX]
    return f"{summary}\n\nFiles: {names}" if names else summary


class Commit(Executor):
    """Writes the commit message (one structured-output call, CommitMessage), then raises his git_commit's card with it.

    The card is MAF's human input as the plan's is (ctx.request_info with a function_approval_request), named
    git_commit and carrying the message, so every host shows it as his git_commit's card and the evals find it
    (evals._cards_named). Approved, his own git_commit tool runs with the card's arguments; denied, nothing is
    committed and the run says so. The message rides in the card, so it is in the checkpoint while the run waits.

    What it commits (audit 2026-11-04): the files EXECUTE's run wrote (``changes``, by default agent.written_files of
    EXECUTE's session), and git_commit is run as MAF's loop runs an approved call, through the agent's function
    middleware with EXECUTE's session (agent.invoke_through_middleware), not by FunctionTool.invoke alone. The user's
    Approve on the card is what puts that session in execute mode, as the plan's Approve does (approved_plan_turn).
    """

    def __init__(
        self,
        client: Any,
        options: dict[str, Any],
        git_commit: Any,
        changes: Callable[[], list[str]],
        agent: Any = None,
        session: Callable[[], Any] = lambda: None,
        modes: AgentModeProvider | None = None,
        id: str = COMMIT_STEP,
    ) -> None:
        super().__init__(id=id)
        self._client = client
        self._options = options
        self._git_commit = git_commit
        self._changes = changes
        self._agent = agent
        self._session = session
        self._modes = modes

    @handler
    async def write(self, report: CheckReport, ctx: WorkflowContext[Any, Any]) -> None:
        approved = ctx.get_state(_APPROVED_REQUEST_KEY, None) or {}
        request = str(approved.get("request", ""))
        files = await asyncio.to_thread(self._changes)
        message = await self._message(request, files, report.output)
        call_id = f"{GIT_COMMIT}-{uuid.uuid4().hex[:12]}"
        call = Content.from_function_call(call_id=call_id, name=GIT_COMMIT, arguments={"message": message})
        # The card's id is the request's id, as AskApproval's (WorkflowAgent keys answers by the approval's id).
        await ctx.request_info(
            request_data=Content.from_function_approval_request(id=call_id, function_call=call),
            response_type=Content,
            request_id=call_id,
        )

    async def _message(self, request: str, files: Sequence[str], output: str) -> str:
        """The structured call, asked again once on a reply that is no CommitMessage; then the built message."""
        listed = "\n".join(files) or "(none listed)"
        messages = [
            Message(role="system", contents=[Content.from_text(COMMIT_PROMPT)]),
            Message(role="user", contents=[Content.from_text(COMMIT_NOW.format(request=request, files=listed, output=output[-_OUTPUT_TAIL:]))]),
        ]
        for attempt in range(2):
            reply = await self._client.get_response(messages, options={**self._options, "response_format": CommitMessage})
            message, error = commit_message_in(reply.text or "")
            if message is not None:
                return message
            logger.info("Steward commit message, attempt %d, did not parse: %s", attempt + 1, error)
            messages += [
                Message(role="assistant", contents=[Content.from_text(reply.text or "")]),
                Message(role="user", contents=[Content.from_text(COMMIT_AGAIN.format(error=error))]),
            ]
        return fallback_commit_message(request, files)

    @response_handler
    async def on_answer(self, original_request: Content, response: Content, ctx: WorkflowContext[Any, Any]) -> None:
        arguments = original_request.function_call.parse_arguments() or {}
        if not getattr(response, "approved", False):
            await ctx.yield_output(COMMIT_NOT_APPROVED.format(message=arguments.get("message", "")))
            return
        session = self._session()
        if session is not None and self._modes is not None:
            set_agent_mode(session, "execute", source_id=self._modes.source_id, available_modes=self._modes.available_modes)
        # His git_commit itself (agent.py), through his function middleware as MAF's loop runs an approved call.
        result = await invoke_through_middleware(self._agent, self._git_commit, {"message": arguments.get("message", "")}, session)
        await ctx.yield_output(result)


class Repair(Executor):
    """Sends the failing checks back to EXECUTE, in its own session, in execute mode with the fix as its todo.

    When EXECUTE's todos were all done, ReturnToPlanWhenDone put his session back in plan mode, so the repair message
    carries its one step as an approved plan, as the plan's Approve and the commit do (approved_plan_turn: the
    application changes the mode, Learn "Planning and todos")."""

    def __init__(self, id: str = REPAIR_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def repair(self, report: CheckReport, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        text = (
            f"The checks failed after attempt {report.attempt} of {MAX_ATTEMPTS}. Fix the cause, then stop and say "
            f"what you changed.\n\nCheck output:\n{report.output}"
        )
        # REQUEST_KEY "": the check output is no new request, so the work's own hints stay (agent.asked_request).
        message = Message(
            role="user", contents=[Content.from_text(text)], additional_properties={APPROVED_PLAN_KEY: [REPAIR_TODO], REQUEST_KEY: ""}
        )
        await ctx.add_event(StewardProgress(f"repair attempt {report.attempt + 1}/{MAX_ATTEMPTS}", executor_id=self.id))
        await ctx.send_message(AgentExecutorRequest(messages=[message]))


class Report(Executor):
    """The checks' result, when any ran and no commit follows. His answer itself has already streamed (EXECUTE is
    intermediate output), so it is not said again."""

    def __init__(self, id: str = REPORT_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def report(self, report: CheckReport, ctx: WorkflowContext[Any, Any]) -> None:
        if report.output:
            await ctx.yield_output(checks_text(report))


def checks_text(report: CheckReport) -> str:
    """The checks' result as the user reads it."""
    result = "passed" if report.passed else f"still fail after {report.attempt} attempts"
    return f"Checks {result}:\n{report.output[-_OUTPUT_TAIL:]}"


def executor_session(executor: AgentExecutor) -> Any:
    """The session an AgentExecutor runs its agent in: the one MAF checkpoints and restores with it
    (on_checkpoint_save's "agent_session", _agent_executor.py:682 and :721-730). MAF has no public getter for it."""
    return executor._session  # noqa: SLF001


def build_steward_workflow(
    agent: Agent[Any], checks: Checks = python_tests_for_changes, changes: Callable[[], list[str]] | None = None
) -> Workflow:
    """The graph over one build_steward_agent Steward: route, then answer, or plan, read_plan, ask_approval, execute,
    check, repair, then ask_commit and commit when the checks passed on changed code, else report. ``changes`` lists
    the files the commit message is written from: by default the files EXECUTE's run wrote, which are the ones his
    git_commit commits (agent.written_files)."""
    from agent import OLLAMA_OPTIONS  # noqa: PLC0415

    modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
    todos = next(p for p in agent.context_providers if isinstance(p, TodoProvider))
    step_options = step_options_from_env()  # a bad value stops the build here, before any call
    agent.middleware = [
        approved_plan_turn(modes, todos),
        plan_mode_turns(modes, response_format=StewardPlan),
        # Only when a step has overrides: unset, every call's options are what they were before.
        *([step_options_turn(step_options)] if step_options else []),
        *(agent.middleware or []),
    ]
    # His own window and keep-alive on the router's call, so Ollama answers it with the model as loaded.
    base = {k: v for k, v in (agent.default_options or {}).items() if k in OLLAMA_OPTIONS}
    for step, overrides in step_options.items():
        logger.info("Steward step %s: model options %s", step, {**base, **overrides})
    route = Router(agent.client, {**base, **step_options.get(ROUTE_STEP, {})})
    # The answer step's own session says it answers in words: plan_mode_turns asks it for no StewardPlan. The session,
    # with its state, is in the workflow's checkpoint (AgentExecutor.on_checkpoint_save).
    answer_session = step_session(agent, ANSWER_STEP)
    answer_session.state[IN_WORDS_KEY] = True
    answer = AgentExecutor(agent, session=answer_session, id=ANSWER_STEP)
    plan = AgentExecutor(agent, session=step_session(agent, PLAN_STEP), id=PLAN_STEP)
    read_plan = ReadPlan()
    ask_approval = AskApproval()
    execute = AgentExecutor(agent, session=step_session(agent, EXECUTE_STEP), id=EXECUTE_STEP)
    check = Check(checks)
    repair = Repair()
    ask_commit = AskCommit()
    # His own git_commit, the copy this build gave him (agent.py): a build without it has nothing to commit with.
    git_commit = next((t for t in (agent.default_options or {}).get("tools") or [] if getattr(t, "name", None) == GIT_COMMIT), None)
    if git_commit is None:
        raise ValueError(f"Steward has no {GIT_COMMIT} tool, so the workflow's commit step cannot commit.")
    # The message's call on his own client with the router's options (his window and keep-alive).
    def execute_session() -> Any:
        return executor_session(execute)

    commit = Commit(
        agent.client, base, git_commit, changes or (lambda: written_files(execute_session())), agent, execute_session, modes
    )
    report = Report()
    # The run's output is the steps' own (a reply, a clarification, a refusal, the report, the commit's result).
    # EXECUTE's work streams to the caller as intermediate output (MAF's intermediate_output_from; WorkflowAgent and
    # the Responses host both forward it), so every host shows his work as it happens; PLAN's streamed text is the
    # plan's raw JSON, which the card shows, so it stays hidden. ANSWER's words stream as EXECUTE's do.
    return (
        WorkflowBuilder(
            name=WORKFLOW_NAME,
            start_executor=route,
            output_from=[read_plan, ask_approval, ask_commit, commit, report],
            intermediate_output_from=[answer, execute],
        )
        .add_switch_case_edge_group(route, [Case(condition=routed_to_answer, target=answer), Default(target=plan)])
        .add_edge(plan, read_plan)
        .add_edge(read_plan, plan)  # an empty plan reply, asked again once
        .add_edge(read_plan, ask_approval)
        .add_edge(ask_approval, execute)
        .add_edge(execute, check)
        .add_edge(check, repair, condition=needs_repair)
        .add_edge(check, report, condition=ready_for_report)
        .add_edge(check, ask_commit, condition=ready_to_commit)
        .add_edge(ask_commit, commit)
        .add_edge(repair, execute)
        .build()
    )


async def build_steward(stack: AsyncExitStack, **build: Any) -> tuple[Agent[Any], Workflow]:
    """Define once (the guide's Part 4: "The agent is defined once; only the host around it changes"): every host,
    the Agent tab's service, the console and the evals, builds Steward and his workflow here."""
    from agent import build_steward_agent  # noqa: PLC0415
    from agent_framework import InMemoryHistoryProvider  # noqa: PLC0415

    build.setdefault("history_provider", InMemoryHistoryProvider())
    agent = await build_steward_agent(stack, **build)
    return agent, build_steward_workflow(agent)


async def main(request: str) -> None:
    """One request through the graph, streamed as the host runs it; prints the output or the approval card."""
    load_dotenv()
    async with AsyncExitStack() as stack:
        agent, workflow = await build_steward(stack, enable_shell=False)
        async with agent:
            events = [e async for e in workflow.run(request, stream=True)]
    for event in events:
        if event.type == "output":
            print(f"Output: {event.data}")
        elif event.type == "request_info":
            print(f"Approval card: {event.data.function_call.name} {event.data.function_call.arguments}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main(" ".join(sys.argv[1:]) or "Add a docstring to order_total in harness/steward/working/sample-project/inventory.py."))
