"""Steward's stages as a MAF workflow (Kyle, 2026-11-01: "the harness makes it actually follow the rules").

MAF's builder skill (references/harness-agent-builder.md): "Use a workflow instead when explicit graph topology,
routing, checkpointed stages, or intermediate outputs define correctness." Plan, approve, execute, check and report
are such stages, so their order is the graph's, not the model's choice.

Pieces 1 to 4 of the build order:

    request -> route (one structured-output call: Route) -> (answer) answer (AgentExecutor, plain words; plan mode,
            so reads run and writes are refused) | (task, or no Route: Default) explore
    explore (AgentExecutor, plan mode, read-only tools, no response_format) -> plan (AgentExecutor, one call: tools off,
            tool_choice "none", structured output StewardPlan) -> read_plan
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
from typing import Annotated, Any, Literal

from agent_framework import (
    Agent,
    AgentContext,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentModeProvider,
    ChatContext,
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
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console.observers.planning_models import PlanningQuestion, PlanningResponse, PlanningResponseType  # noqa: E402
from hosted import IN_WORDS_KEY, planning_response_in, plan_mode_turns  # noqa: E402
# write_happened is agent.py's (his write recorder's), named here as the evals and tests have read it.
import agent as _agent  # noqa: E402 - hyperlight_sandbox_on, read at call time (offered_in_step)
from agent import _CHANGES_THINGS, ESTATE_READS, REQUEST_KEY, WRITTEN_FILES_KEY, invoke_through_middleware, write_happened, written_files  # noqa: E402, F401

logger = logging.getLogger(__name__)

# A fixed name: the host checks a reply's rebuilt graph against the stored one by name and signature.
WORKFLOW_NAME = "steward"
ROUTE_STEP = "route"
ANSWER_STEP = "answer"
# PLAN in two phases (the bar at aba870f, 2026-11-04: the discount ask's PLAN ended on a tool call's arguments written
# as text both runs, '{"todos": [...]}' and '{"file_name": ..., "new_lines": ...}', after '{"query": ...}',
# '{"edits": ...}' and others on earlier bars; reading each new shape was not converging). EXPLORE reads, with only the
# read-only tools (PLAN_TOOLS) and no response_format; PLAN is then one call with tool_choice "none" and StewardPlan as
# response_format, so the model's only possible answer is the plan. MAF's own way to get a final answer with the tools
# off is that same option (agent_framework/_tools.py:4726, _disable_tools_at_function_call_limit), which
# OllamaChatClient honours by sending no tools (agent_framework_ollama/_chat_client.py:483-497, "none omits the
# tools"); response_format is Ollama's `format`, the schema it enforces (_chat_client.py:241 and 457).
EXPLORE_STEP = "explore"
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
# Its example names no eval ask's work (the bar at aba870f: given no request, the model copied the example, which was
# the item_count ask's own message, so a copy could not be told from an answer; see _REQUEST_STATE_KEY).
COMMIT_PROMPT = (
    "Write the git commit message for the change below: one line of at most 72 characters, imperative, naming what "
    "changed (the function, file or behaviour), e.g. 'Add parse_date to dates.py'. Never a bare word such as "
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
# Names the structured plan, as PLAN_NOT_A_CALL does (the steps set at 6d8b127: PLAN's first reply was '').
PLAN_AGAIN = (
    "Your reply was empty. Reply now with your plan for the request above as the JSON object asked for: type "
    "approval, a summary of the plan as its one question, and your steps."
)
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
# Sent to EXPLORE once when the plan call answered only with read calls (tools off there, so none ran). The bar at
# 416ba41 (2026-11-05 05:28Z, the discount ask's second run): EXPLORE listed the folder and stopped; the plan call
# answered with file_access_read twice, nothing ran, the run ended with an empty reply and no card. EXPLORE is where
# reads run, so it reads them, and its conversation goes on to the plan call as the first did.
PLAN_READ_FIRST = (
    "Your plan call asked to read {calls}, but tools are off in the plan call, so nothing ran. Make those reads now "
    "with your tools, then stop; your plan comes after."
)
# The plan call's own turn, after EXPLORE's conversation (plan_call_input): its tools are off, so it says so, and says
# what the steps become (approved_plan_turn writes them as his todos; no todo tool is offered while planning).
# A step that changes a file names it (the steps set at 416ba41: "Change order_total to multiply subtotal by ..." named
# the function, not inventory.py, and EXECUTE then worked from a todo that did not say where).
PLAN_NOW = (
    "Your reading is done, and your tools are off for this reply. Reply now with your plan for the request above as "
    "the JSON object asked for: type approval, a summary of the plan as its one question, and your steps, one short "
    "imperative line each, a step that changes a file naming that file by its path; they become your todo list when "
    "the user approves. If you need the user's answer first, reply with type clarification and a question that lists "
    "the choices."
)
# The user's request, kept in the workflow's state by ROUTE (so in its checkpoint): the plan card and the commit message
# name it. The bar at aba870f (steps set, 2026-11-04): PLAN was asked again (PLAN_AGAIN), its second run's conversation
# started at that message, and the commit message was asked for "Request: Your reply was empty. Reply now with your
# plan ..."; with no request to name, the model copied COMMIT_PROMPT's example (traces: "Given example provided by
# developer ... We'll produce that"), "Add item_count to inventory.py", on the discount fix.
_REQUEST_STATE_KEY = "steward_request"
_TRAILING_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```\s*\Z", re.S | re.I)
# The router's one instruction, and the line the answer step is given with a question: short, since the graph routes.
ROUTE_PROMPT = (
    'Classify the user\'s request. "answer": a question to answer in words, reading files or read-only tools at '
    "most: what is, show, list, how many, status, logs, history (e.g. 'What is the estate status? Read it with "
    "estate_status.'). \"task\": it asks to change, create, run, fix, commit or send something."
)
# A request that names one of the Estate's read-only tools and asks for no change is a question, whatever the model
# says (live 2026-11-04: "Read it with estate_status and list each service" was routed to the plan).
_CHANGE_VERBS = "write|fix|add|commit|restart|update|delete|change|create|edit|remove|send|push|install|stop|start|run|unload|apply"
_CHANGE_WORDS = re.compile(rf"\b({_CHANGE_VERBS})\b", re.IGNORECASE)
# A request that opens with one of those verbs (an imperative, "please" allowed) asks for a change: a task, whatever the
# model says. The bar at a0fb3ca (2026-11-05 04:35Z and 04:41Z, traces): "Fix the bug that makes test_percent_discount
# fail in ..." was routed {"kind":"answer"} both small runs, the router's reasoning solving the bug instead of
# classifying it ("Let's imagine the test fails"), so ANSWER replied with the fixed file in prose and no plan card.
_OPENS_WITH_A_CHANGE = re.compile(rf"\A\W*(?:please\W+)?({_CHANGE_VERBS})\b", re.IGNORECASE)
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


def asks_for_a_change(request: str) -> bool:
    """Whether the request opens with a verb that changes something (_OPENS_WITH_A_CHANGE): a task, never an answer."""
    return bool(_OPENS_WITH_A_CHANGE.match(request or ""))


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
        # The request, for the plan card and the commit message, whatever later turns of PLAN start from.
        ctx.set_state(_REQUEST_STATE_KEY, request)
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
        elif asks_for_a_change(request):
            kind = "task"
        if kind == "answer":
            messages = [Message(role="system", contents=[Content.from_text(ANSWER_IN_WORDS)]), *messages]
        await ctx.send_message(RoutedRequest(messages=messages, kind=kind))


class StewardPlan(PlanningResponse):
    """The guide's PlanningResponse with the plan's steps, which become his todo list."""

    # Required and at least one ("required", "minItems": 1 in the schema): Ollama's structured output (format = this
    # schema) enforces only what the schema says, and a model left free sent no steps, or "[ ]" (live, 2026-11-01);
    # a plan without steps has nothing to approve or run.
    # Each step non-blank ("minLength": 1 per item in the schema Ollama is sent): the bar at 98d54d5 (2026-11-05
    # 01:47Z) approved a plan whose steps held "" lines, MAF's todo store refuses a blank title on its next load
    # (TodoItem.from_dict, agent_framework/_harness/_todo.py:92-93), and the run crashed. A reply with one is no plan,
    # so READ_PLAN asks for it again (PLAN_NOT_A_CALL), as it asks for any reply that is not the plan.
    steps: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]] = Field(
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
    """The StewardPlan ending a reply, or None: an approval needs its steps, a clarification its questions.

    A plan written in its own shape (plan_in_its_own_shape) is read as the approval it is."""
    plan = planning_response_in(text, model=StewardPlan)
    if plan is None:
        return plan_in_its_own_shape(text)
    if plan.type == PlanningResponseType.APPROVAL and not plan.steps:
        return None
    return plan


# A plan step written as an object (the bar at 6d8b127, the README ask's run 2: {"title": ..., "action": ...}): its
# line is the title, then the action (or description) after a colon.
_STEP_LINE_KEYS = ("action", "description")


def _step_line(step: Any) -> str | None:
    """One plan step as one line, or None when it holds no line."""
    if isinstance(step, dict):
        title = step.get("title")
        detail = next((step[key] for key in _STEP_LINE_KEYS if isinstance(step.get(key), str) and step[key].strip()), None)
        parts = [p for p in (title if isinstance(title, str) else None, detail) if p and p.strip()]
        step = ": ".join(parts) if parts else None
    if not isinstance(step, str):
        return None
    return " ".join(step.split()) or None


def plan_in_its_own_shape(text: str) -> StewardPlan | None:
    """The approval a reply's trailing JSON object holds when the model wrote its plan in its own shape, or None.

    The bar at 6d8b127 (2026-11-05, the README ask's run 2): '{"summary": "Add a line to the sample-project README ...",
    "steps": [{"title": "Locate README.md", "action": "read file ..."}, ...]}' ended the run with no card. The cookbook's
    "Validate JSON ... in code": a plan-shaped object (no "type"; a summary or question; a steps list of strings, or of
    objects with a title, action or description) is read as the approval, its steps one line each (_step_line), its
    summary the card's question. A step with no line, a blank one, or no summary: no plan, as StewardPlan's own schema
    has it, so READ_PLAN asks again (PLAN_NOT_A_CALL). A "type" of "approval" is read the same (the steps set at
    416ba41: '{"type":"approval","summary":"Modify order_total ...","steps":[...]}' was asked again); any other type
    is not an approval in its own shape."""
    found = trailing_json_object(text)
    if found is None or found.get("type", PlanningResponseType.APPROVAL.value) != PlanningResponseType.APPROVAL.value:
        return None
    question = next((found[key] for key in ("summary", "question") if isinstance(found.get(key), str)), "")
    steps = found.get("steps")
    if not question.strip() or not isinstance(steps, list) or not steps:
        return None
    lines = [_step_line(step) for step in steps]
    if not all(lines):
        return None
    try:
        return StewardPlan(
            type=PlanningResponseType.APPROVAL, questions=[PlanningQuestion(message=" ".join(question.split()))], steps=lines
        )
    except ValueError:
        return None


def trailing_json_object(text: str) -> dict[str, Any] | None:
    """The one non-empty JSON object text is, or ends with (fenced or not), or None."""
    body = (text or "").strip()
    if fenced := _TRAILING_FENCE.search(body):
        body = fenced.group(1)
    if not body.endswith("}"):
        return None
    decoder = json.JSONDecoder()
    for start in (i for i, char in enumerate(body) if char == "{"):
        try:
            value, end = decoder.raw_decode(body, start)
        except ValueError:
            continue
        if end == len(body):
            return value if isinstance(value, dict) and value else None
    return None


def ends_with_a_json_object(text: str) -> bool:
    """Whether text is, or ends with, one non-empty JSON object (fenced or not)."""
    return trailing_json_object(text) is not None


def offers_no_choices(plan: StewardPlan) -> bool:
    """A clarification none of whose questions offers a choice: by the guide's definition it presents options."""
    return plan.type == PlanningResponseType.CLARIFICATION and not any(q.choices for q in plan.questions)


def _last_text(response: AgentExecutorResponse) -> str:
    messages = response.agent_response.messages
    return next((m.text for m in reversed(messages) if m.role == "assistant" and (m.text or "").strip()), "")


def plan_call_reads(response: AgentExecutorResponse) -> list[str]:
    """The read calls (PLAN_TOOLS) a plan call answered with, as 'name(arguments)', in order; none ran (tools off)."""
    return [
        f"{c.name}({json.dumps(c.parse_arguments() or {}, ensure_ascii=False)})"
        for m in response.agent_response.messages
        for c in m.contents
        if c.type == "function_call" and c.name in PLAN_TOOLS
    ]


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
            # Only titles MAF's store loads again (TodoItem.from_dict: a non-blank string), so a blank step that got
            # past the plan's schema never reaches the store, where it would end the run on the next load.
            titles = [title for title in (str(step).strip() for step in steps) if title]
            items = [TodoItem(id=n, title=title) for n, title in enumerate(titles, start=1)]
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
        if step == EXPLORE_STEP:
            step = PLAN_STEP  # PLAN's reading phase: STEWARD_PLAN_* are the plan step's, both its phases
        if overrides := step_options.get(str(step)):
            context.options = {**(context.options or {}), **overrides}
        await call_next()

    return step_options_turn_


@agent_middleware
async def plan_phases_turn(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Agent middleware, after plan_mode_turns: the run options of PLAN's two phases, read from the session's STEP_KEY.

    EXPLORE reads: no response_format, so its replies are its own words and calls (plan_mode_turns sets StewardPlan
    on every plan-mode run). PLAN is the plan call: tool_choice "none" and StewardPlan as response_format, so the
    model can only answer with the plan (OllamaChatClient sends no tools, _chat_client.py:483-497; MAF's function loop
    runs no call with it set, _tools.py:5428). Its asked-again runs (ReadPlan) are the same call.
    """
    session = context.session
    step = session.state.get(STEP_KEY) if session is not None else None
    if step == EXPLORE_STEP:
        options = dict(context.options or {})
        options.pop("response_format", None)
        context.options = options
    elif step == PLAN_STEP:
        context.options = {**(context.options or {}), "tool_choice": "none", "response_format": StewardPlan}
    await call_next()


def plan_call_input(conversation: list[Message]) -> list[Message]:
    """PLAN's input from EXPLORE (AgentExecutor's context_filter, context_mode "custom"): EXPLORE's whole conversation,
    then PLAN_NOW. REQUEST_KEY "": PLAN_NOW is no new request (agent.asked_request)."""
    now = Message(role="user", contents=[Content.from_text(PLAN_NOW)], additional_properties={REQUEST_KEY: ""})
    return [*conversation, now]


# Per-step tools (2026-11-05, the bar at 98d54d5): every model call of every step was offered the whole set, 43 tools
# in an eval's build and 56 live, and the plan step's failures were in its tool use (traces 01:15-02:05Z: of 56 PLAN
# calls, 4 wrote a call's arguments as text, one called "functions?", one listed '.'). The cookbook's guidance is fewer,
# clearer tools per step; Ollama has no tool_choice allowed_tools, and MAF's own answer is "Pass only the tools you want
# to allow" (agent_framework_ollama/_chat_client.py:491-494). So each call's own tool list (ChatContext.options, the
# list MAF sends: _chat_client.py:495-497) is cut to its step's, by chat middleware that reads the step from the call's
# session (ChatContext.session, STEP_KEY). This supersedes, for the workflow's steps, agent.py's "Tools stay offered in
# every mode": the plan-mode gate and the cards still stand behind it. A session with no step (a host that runs him
# without the graph) is offered everything, as before.
#   EXPLORE, PLAN's reading phase, offers what reads (PLAN_TOOLS): MAF's read-only file and skill tools, his repo status
#     and code search, his file memory's reads, his notes' and the Estate's reads. No todo tool (the bar at aba870f:
#     '{"todos": [...]}' written as text was PLAN's last reply): approved_plan_turn writes the approved plan's steps as
#     his todos. PLAN's own call is offered no tool and is sent with tool_choice "none" (plan_phases_turn).
#   ANSWER offers everything that changes nothing (all but agent._CHANGES_THINGS, the mode tools, the todos and file
#     memory's writes): a question may need CodeAct, a background agent or a skill's script (REQUEST_HINTS).
#   EXECUTE (and its repair) offers everything but git_commit (COMMIT's own), the mode tools, CodeAct (CODEACT_TOOL) and
#     todos_add (its todos are the approved plan's).
#   ROUTE and COMMIT call the client with no tools; REPORT makes no call.
PLAN_TOOLS = frozenset({
    *FileAccessProvider._READ_ONLY_TOOL_NAMES,  # MAF's own set: file_access_read, _read_lines, _ls, _grep
    "load_skill", "read_skill_resource",  # SkillsProvider's read-only tools (READ_ONLY_RULES)
    "get_repo_status", "search_code",
    "file_memory_ls", "file_memory_read", "file_memory_grep",
    # His automatic memory (MAF's MemoryContextProvider, step 5): its reads, and write_memory for a fact the request
    # tells him (no card; his own memory, not the workspace). Named here because the provider adds them to the live list
    # on a run's first call after this cut, so the run's later calls would otherwise lose them.
    "list_memory_topics", "read_memory_topic", "search_memory_transcripts", "write_memory",
    *(f"secondbrain_{name}" for name in ("search_notes", "read_note", "list_notes", *ESTATE_READS)),
})
_MODE_TOOLS = frozenset({"mode_set", "mode_get"})
_FILE_MEMORY_WRITES = frozenset({"file_memory_write", "file_memory_replace", "file_memory_replace_lines", "file_memory_delete"})
_TODO_TOOLS = frozenset({"todos_add", "todos_complete", "todos_get_all", "todos_get_remaining", "todos_remove"})
ANSWER_LEAVES_OUT = frozenset({*_CHANGES_THINGS, *_MODE_TOOLS, *_FILE_MEMORY_WRITES, *_TODO_TOOLS})
# CodeAct's tool (agent_framework_monty/_execute_code_tool.py:41, EXECUTE_CODE_TOOL_NAME; Hyperlight's is the same name,
# agent_framework_hyperlight/_execute_code_tool.py:1566). CodeAct is for counting and calculation (the Charter): an
# answer's tool. The steps set at 6d8b127 (2026-11-05 03:08Z): EXECUTE called execute_code seven times and file_access_ls
# four, and never wrote inventory.py. So EXECUTE is not offered it, unless the Hyperlight sandbox is on, where it is the
# shell's stand-in after untrusted content (agent.SANDBOX_SHELL_REFUSAL sends that step to execute_code).
CODEACT_TOOL = "execute_code"
# todos_add (the steps set at a0fb3ca, 2026-11-05 04:49Z): EXECUTE's one call was todos_add, then it ended with no write
# to inventory.py. EXECUTE's todos are the approved plan's steps (approved_plan_turn writes them), so it is offered
# only the todo tools that work through them (todos_complete, todos_get_remaining, todos_get_all), never one to add.
EXECUTE_LEAVES_OUT = frozenset({GIT_COMMIT, CODEACT_TOOL, "todos_add", *_MODE_TOOLS})


def offered_in_step(name: str, step: str | None) -> bool:
    """Whether a step's model calls are offered the tool named name (a step of None is offered every tool)."""
    if step == EXPLORE_STEP:
        return name in PLAN_TOOLS
    if step == PLAN_STEP:
        return False  # the plan call: tools off (plan_phases_turn), so it can only answer with the plan
    if step == ANSWER_STEP:
        return name not in ANSWER_LEAVES_OUT
    if step == EXECUTE_STEP:
        if name == CODEACT_TOOL:
            return _agent.hyperlight_sandbox_on()
        return name not in EXECUTE_LEAVES_OUT
    return True


async def step_tools_turn(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Chat middleware: this call's tools are its step's (offered_in_step), the step read from the call's session.

    The run's live tool list is cut in place, as MAF's own progressive tool exposure cuts it
    (FunctionInvocationContext.remove_tools, agent_framework/_middleware.py:580-625, "self.tools[:] = ..."): MAF's
    function loop runs calls from that same list, and a provider's chat middleware later in the chain adds its tools to
    it (MemoryContextProvider's write_memory), so a copy would lose those. A tool the step leaves out cannot run either.
    """
    session = context.session
    step = session.state.get(STEP_KEY) if session is not None else None
    tools = (context.options or {}).get("tools")
    if step is not None and isinstance(tools, list):
        tools[:] = [t for t in tools if offered_in_step(getattr(t, "name", "") or "", step)]
    await call_next()


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
        reads = plan_call_reads(response)
        if not last.strip() and reads and not ctx.get_state(_PLAN_ASKED_AGAIN_KEY, False):
            ctx.set_state(_PLAN_ASKED_AGAIN_KEY, True)
            # REQUEST_KEY "": the reads are no new request (agent.asked_request).
            read_first = Message(
                role="user", contents=[Content.from_text(PLAN_READ_FIRST.format(calls=", ".join(reads)))], additional_properties={REQUEST_KEY: ""}
            )
            await ctx.send_message(AgentExecutorRequest(messages=[read_first]), target_id=EXPLORE_STEP)
            return
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
            request = ctx.get_state(_REQUEST_STATE_KEY, None) or _first_user_text(response)
            plan_data = {"request": request, "plan": plan.questions[0].message, "steps": plan.steps}
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
        description="One imperative line naming what changed, e.g. 'Add parse_date to dates.py'.",
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
    async def repair(self, report: CheckReport, ctx: WorkflowContext[AgentExecutorRequest, Any]) -> None:
        text = (
            f"The checks failed after attempt {report.attempt} of {MAX_ATTEMPTS}. Fix the cause, then stop and say "
            f"what you changed.\n\nCheck output:\n{report.output}"
        )
        # REQUEST_KEY "": the check output is no new request, so the work's own hints stay (agent.asked_request).
        message = Message(
            role="user", contents=[Content.from_text(text)], additional_properties={APPROVED_PLAN_KEY: [REPAIR_TODO], REQUEST_KEY: ""}
        )
        await ctx.add_event(StewardProgress(f"repair attempt {report.attempt + 1}/{MAX_ATTEMPTS}", executor_id=self.id))
        # The failing checks are said before the repair (the bar at a0fb3ca, the item_count ask's run 1, 04:34Z): CHECK
        # ran pytest over inventory.py and failed, REPAIR said nothing (only the progress event, which no host forwards),
        # and the run then ended on a later card, so his reply never showed that a check had run at all.
        await ctx.yield_output(repair_text(report))
        await ctx.send_message(AgentExecutorRequest(messages=[message]))


def repair_text(report: CheckReport) -> str:
    """The failing checks as the user reads them before a repair: which attempt failed, and the check's output."""
    return (
        f"Checks failed on attempt {report.attempt} of {MAX_ATTEMPTS}; repairing:\n{report.output[-_OUTPUT_TAIL:]}"
    )


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
        plan_phases_turn,  # after plan_mode_turns: EXPLORE drops its response_format, PLAN turns its tools off
        # Only when a step has overrides: unset, every call's options are what they were before.
        *([step_options_turn(step_options)] if step_options else []),
        # Chat middleware, first of his chat middleware, so the name repair and the text-call recovery read the step's
        # tools (repair_tool_names, recover_text_tool_calls): each step's calls are offered only its tools.
        step_tools_turn,
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
    explore = AgentExecutor(agent, session=step_session(agent, EXPLORE_STEP), id=EXPLORE_STEP)
    # PLAN takes EXPLORE's conversation and PLAN_NOW (MAF's chaining, AgentExecutor.from_response, context_mode custom).
    plan = AgentExecutor(
        agent, session=step_session(agent, PLAN_STEP), id=PLAN_STEP, context_mode="custom", context_filter=plan_call_input
    )
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
    # plan's raw JSON, which the card shows, so it stays hidden, as EXPLORE's reading does. ANSWER's words stream as EXECUTE's do.
    return (
        WorkflowBuilder(
            name=WORKFLOW_NAME,
            start_executor=route,
            output_from=[read_plan, ask_approval, repair, ask_commit, commit, report],
            intermediate_output_from=[answer, execute],
        )
        .add_switch_case_edge_group(route, [Case(condition=routed_to_answer, target=answer), Default(target=explore)])
        .add_edge(explore, plan)
        .add_edge(plan, read_plan)
        .add_edge(read_plan, plan)  # an empty plan reply, asked again once
        .add_edge(read_plan, explore)  # a plan call that answered with reads: EXPLORE makes them, once (PLAN_READ_FIRST)
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
