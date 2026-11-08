"""Steward's stages as a MAF workflow (Kyle, 2026-11-01: "the harness makes it actually follow the rules").

MAF's builder skill (references/harness-agent-builder.md): "Use a workflow instead when explicit graph topology,
routing, checkpointed stages, or intermediate outputs define correctness." Plan, approve, execute, check and report
are such stages, so their order is the graph's, not the model's choice.

Pieces 1 to 4 of the build order:

    request -> route (one structured-output call: Route) -> (refused by a bound, ADR-0014) refuse | (answer) answer (AgentExecutor, plain words; plan mode,
            so reads run and writes are refused) | (task, or no Route: Default) explore
    explore (AgentExecutor, plan mode, read-only tools, no response_format) -> plan (AgentExecutor, one call: tools off,
            tool_choice "none", structured output StewardPlan) -> read_plan
            -> ask_approval (the workflow pauses: ctx.request_info) -> execute (AgentExecutor, execute mode) -> check
            -> (failed, attempts left) repair -> execute -> check ...
            -> (passed on changed code) ask_commit ("Checks passed") -> commit (one structured-output call writes the
               message: CommitMessage; the workflow raises his git_commit's card with it, and runs it on Approve)
            -> (nothing changed, attempts spent, or he stopped: stop_and_report) report; a docs change with no test
               to run still goes to ask_commit (ADR-0015)

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
    FunctionInvocationContext,
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
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, create_model, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console.observers.planning_models import PlanningQuestion, PlanningResponse, PlanningResponseType  # noqa: E402
from hosted import IN_WORDS_KEY, planning_response_in, plan_mode_turns  # noqa: E402
# write_happened is agent.py's (his write recorder's), named here as the evals and tests have read it.
import agent as _agent  # noqa: E402 - hyperlight_sandbox_on, read at call time (offered_in_step)
import profiles as _profiles  # noqa: E402 - the harness profiles (ADR-0018, spec 002)
from profiles import PROFILE_EVENT, PROFILE_KEY, Profile, ProfileInstructions, card_line, load_profiles, pick_profile  # noqa: E402
from agent import _CHANGES_THINGS, ESTATE_READS, READS_FIRST_KEY, REQUEST_KEY, STOP_AND_REPORT, STOPPED_KEY, UNTRUSTED_READ_KEY, WRITTEN_FILES_KEY, invoke_through_middleware, stopped_reason, write_happened, written_files  # noqa: E402, F401

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
# The bounds at the request (ADR-0014, part 2): a request the bounds refuse is answered here, with no plan and no card.
REFUSE_STEP = "refuse"
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
# Sent to PLAN once when its reply was a clarification whose only choices are a yes and a no (asks_only_to_go_ahead).
# The P36 rerun of 2026-11-08 (transcript bounds-review-p36): asked "Restart the AG-UI host.", he found steward-ag-ui,
# reasoned "we still need confirmation. So type clarification", and the run ended on "Do you want me to restart the
# steward-ag-ui host ...? (Yes / No)", with no plan card. The plan card is that question.
PLAN_CARD_IS_THE_YES = (
    "Your reply was a clarification asking whether to go ahead, yes or no. The plan card is that question: nothing runs "
    "before the user's Approve on it, and his Approve is the yes. Reply with type approval, a summary of the plan as its "
    "one question, and your steps."
)
_GO_AHEAD_CHOICES = frozenset({
    "yes", "no", "y", "n", "ok", "okay", "proceed", "go ahead", "approve", "deny", "cancel", "stop", "abort", "confirm",
    "yes, proceed", "no, cancel", "yes, restart", "no, don't",
})
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
    "the choices. If what you read shows the request is already done (what it asks for is already there), plan no "
    "change: set already_done to what showed it, the file and the line."
)
# ADR-0015 (the 2026-11-06 06:04 run, transcript b06035a6: he read that the README already said how to run the tests,
# reasoned "that's what the instruction says... might be okay", planned the duplicate and wrote it): a request already
# satisfied by what he read is answered so, with its evidence, and no plan card. StewardPlan's already_done carries it,
# read in code by ReadPlan, as the plan itself is.
ALREADY_DONE = "Already done, so nothing was changed: {evidence}"
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
# A turn from one of SecondBrain's automations (Jesster electron/agent/service.cjs, its first line "[from an automation
# (<name>)]"): nobody is watching, and an automation never approves its own card, so a plan card would wait its ten
# minutes and be answered No. Its workflow has already gathered what it needs (Jesster electron/agent/workflows.cjs)
# and asks for words, so it is the answer branch, whatever the model or its opening verb says ("Write the daily ...").
_FROM_AN_AUTOMATION = re.compile(r"\A\s*\[from an automation \(")
# The bounds at the request and the plan (ADR-0014, part 2), held in code before any plan card:
#   * WhatsApp (B3, P30): Jesster's source line "[from the phone (WhatsApp) — chat and research only, no changes | ...]"
#     (electron/agent/service.cjs SOURCES). A turn from it that asks for a change (the router's task, a request whose
#     body opens with a change verb, or a direct ask) is refused here and pointed to the PC or Telegram.
#   * The sitting (L3, RULE 9, P29): a task that names the ground (the words "ground" or "Manjuel", or a path in it,
#     agent.ground_path), or a plan that does, while the operator's sitting is open (agent.sitting_from_ledger, or
#     Jesster's estate_status read here by the workflow itself: open_sitting_now) is refused, naming the sitting.
#   * The Archive (L2, RULE 1, P33): a request or a plan naming a path under Desktop\Archive (agent.archive_named) is
#     refused; nothing reads, lists or reaches it.
#   * A key file (L1, RULE 7, P32; 2026-11-08): a request that names a key file (agent.key_file_named: .env and the rest)
#     and asks for what it holds (_ASKS_FOR_KEYS) is refused before any read. The rerun of 2026-11-08 (transcript
#     bounds-review-p32): routed to ANSWER, his reasoning was "This request is to read a file. It's allowed.", he called
#     file_access_read on worlds/jesster/.env, and only the call's gate refused it. A request that only names one ("Add
#     .env to .gitignore") is not refused here: the call gate still refuses every read of it.
_FROM_WHATSAPP = re.compile(r"\A\s*\[from the phone \(WhatsApp\)", re.IGNORECASE)
_SOURCE_LINE = re.compile(r"\A\s*\[[^\]\n]*\]\s*\n?")
_NAMES_THE_GROUND = re.compile(r"\b(?:ground|manjuel)\b", re.IGNORECASE)
WHATSAPP_REFUSAL = (
    "Not done: this message came from WhatsApp, which is for chat and research only, so I make no plan and no change "
    "from it. Ask for it from the PC (the Agent tab) or from Telegram, where it is planned and goes on your card."
)
SITTING_REFUSAL = (
    "Not done: your {sitting} is open, and nothing in Manjuel's ground changes while a sitting is open (RULE 9). Ask "
    "again once the sitting is closed."
)
ARCHIVE_REFUSAL = (
    "Not done: that names {path}, under Desktop\\Archive, which I never reach, read or list (RULE 1)."
)
KEY_FILE_REFUSAL = (
    "Not done: {path} holds keys, and I never read, print or copy a key or anything in that file (RULE 7). Only you "
    "place and read keys."
)
_ASKS_FOR_KEYS = re.compile(
    r"\b(?:what|which|show|print|read|cat|copy|give|tell|display|value|values|contents?|token|tokens|keys?|"
    r"secrets?|passwords?|credentials?)\b",
    re.IGNORECASE,
)
# GitHub writes withheld (N17; ADR-0016, ExecPlan 0005 M9; 2026-11-08, the operator: "when he has passed reliably, he
# can gain the tools to control github"): his build offers no door write (agent._ATLAS_GIT_WITHHELD), so a task that
# asks for one (a push or force-push, a pull request opened, merged or closed, a branch or line of work opened, closed
# or landed) is answered by the bounds in words, before any plan: the hand does them for now. A question about them
# (the router's answer) is not refused, and his own workspace's commit (git_commit) is not a GitHub write.
_GITHUB_WRITE = re.compile(
    r"\b(?:force[- ]?push(?:es|ed|ing)?|push(?:es|ed|ing)?|save and send)\b"
    r"|\b(?:open|create|merge|close|land)\w*\s+(?:(?:a|an|the|new|this|that|my|his|pr|pull request)\s+)*"
    r"(?:pr\b|pull request|branch|line of work)"
    r"|\bmerge\s+(?:pr|pull request)?\s*#?\d+\b",
    re.IGNORECASE,
)
GITHUB_WRITE_REFUSAL = (
    "Not done: GitHub writes (a branch or line of work, a push, a pull request opened or merged) are withheld from me "
    "for now, until you say I have passed reliably; the hand does them. I can read a repository's state and a pull "
    "request's checks."
)


# The harness profile (ADR-0018, spec 002): the router picks one per request (profiles.pick_profile: a name the request
# gives, a profile's pattern, the model only when two patterns match, `general` otherwise). The pick's card view is kept
# in the workflow's state (so in its checkpoint) for the plan card, and its state on each step's session (PROFILE_KEY),
# where step_tools_turn, profile_options_turn and the ProfileInstructions provider read it. ProfilePicked names the pick
# to every caller (over AG-UI a CUSTOM event named PROFILE_EVENT): its name@version, success check and phone summary.
_PROFILE_STATE_KEY = "steward_profile_picked"
# The picks of the runs made in this context (an eval sets a list here before a case, and reads its pick after).
PROFILE_PICKS: ContextVar[list[str] | None] = ContextVar("steward_profile_picks", default=None)
# The model's choice when two profiles' patterns match the request (pick_profile's "unclear").
PROFILE_PROMPT = "Which harness profile is this request for? Answer with one of the names offered."


class ProfilePicked(WorkflowEvent[dict[str, Any]]):
    """The router's pick, a custom event of type PROFILE_EVENT: {profile: name@version, name, version, picked_by,
    success, summary}. MAF's AG-UI host passes it on as CUSTOM {name: PROFILE_EVENT, value: <that>}; the phone's
    summary reads its summary line when it is there."""

    def __init__(self, data: dict[str, Any], *, executor_id: str) -> None:
        super().__init__(PROFILE_EVENT, data, executor_id=executor_id)  # type: ignore[arg-type]  # a custom type


# The profiles a bounds' refusal runs under (ExecPlan 0005, M0): a GitHub write other than a force-push is the
# github-review family's (N17: the writes withheld, the reads his); every other refusal (a force-push, a key, the Archive,
# the sitting, WhatsApp) is the refuse profile's.
REFUSE_PROFILE = "refuse"
GITHUB_REVIEW_PROFILE = "github-review"
_FORCE_PUSH = re.compile(r"\bforce[- ]?push", re.IGNORECASE)


def refusal_profile(refusal: str, request: str) -> str:
    """The profile a refused request runs under: github-review for a withheld GitHub write, refuse for the rest."""
    if refusal == GITHUB_WRITE_REFUSAL and not _FORCE_PUSH.search(request or ""):
        return GITHUB_REVIEW_PROFILE
    return REFUSE_PROFILE


def asks_for_a_github_write(request: str) -> bool:
    """Whether the request (its body, past a source line) asks for a GitHub write (_GITHUB_WRITE)."""
    return bool(_GITHUB_WRITE.search(request_body(request or "")))


class Route(BaseModel):
    """The router's structured output: the classifier's typed result the switch-case edge group routes on."""

    kind: Literal["answer", "task"]


@dataclass
class RoutedRequest(AgentExecutorRequest):
    """The request with its route, as the AgentExecutorRequest both branches take. kind is None when the router's
    reply was no Route, which falls to the Default branch (the plan)."""

    kind: str | None = None
    # The refusal, when kind is REFUSE_STEP (ADR-0014): the bounds answer the request themselves.
    reason: str | None = None


def asks_only_to_read(request: str) -> bool:
    """Whether the request names one of the Estate's read-only tools (ESTATE_READS) and no change (_CHANGE_WORDS)."""
    return any(name in request for name in ESTATE_READS) and not _CHANGE_WORDS.search(request)


def from_whatsapp(request: str) -> bool:
    """Whether the request is a WhatsApp turn (_FROM_WHATSAPP): chat and research only."""
    return bool(_FROM_WHATSAPP.match(request or ""))


def request_body(request: str) -> str:
    """The request without its source line (Jesster's "[from ... | time]" first line), if it has one."""
    return _SOURCE_LINE.sub("", request or "", count=1)


def names_the_ground(text: str) -> bool:
    """Whether a request or a plan names Manjuel's ground: the word, or a path in it (agent.ground_path)."""
    return bool(_NAMES_THE_GROUND.search(text or "")) or any(_agent.ground_path(w) for w in _agent._WORD.findall(text or ""))


def key_file_asked(text: str) -> str | None:
    """The key file a request names (agent.key_file_named), when it also asks for what such a file holds
    (_ASKS_FOR_KEYS), or None."""
    found = _agent.key_file_named(_agent._WORD.findall(text or ""))
    return found.rstrip("?.!,:") if found and _ASKS_FOR_KEYS.search(request_body(text)) else None


def archive_in(text: str) -> str | None:
    """The first path under the Archive a request or a plan names (agent.archive_named), or None."""
    return _agent.archive_named(_agent._WORD.findall(text or ""))


def _named_function(agent: Any, name: str) -> Any:
    """His tool of this name, a FunctionTool or one an MCP tool serves (its functions), or None."""
    for tool in (getattr(agent, "default_options", None) or {}).get("tools") or []:
        if getattr(tool, "name", None) == name and callable(getattr(tool, "invoke", None)):
            return tool
        try:
            functions = getattr(tool, "functions", None) or []
        except Exception:  # noqa: BLE001 - an MCP tool that is not connected serves none
            functions = []
        found = next((f for f in functions if getattr(f, "name", None) == name), None)
        if found is not None:
            return found
    return None


async def open_sitting_now(agent: Any) -> dict[str, Any] | None:
    """The operator's open sitting, or None: the ground's ledger (agent.sitting_from_ledger), then Jesster's
    estate_status (his secondbrain_estate_status, or an eval's stand-in of it), read here by the workflow, not by him."""
    ledger = _agent.sitting_from_ledger()
    if ledger.get("open"):
        return ledger
    status = _named_function(agent, "secondbrain_estate_status")
    if status is None:
        return None
    try:
        seen = _agent.sitting_in_status(_agent._result_text(await status.invoke(arguments={})))
    except Exception as error:  # noqa: BLE001 - a status that cannot be read says nothing of the sitting
        logger.warning("estate_status could not be read for the sitting: %s", type(error).__name__)
        return None
    return seen if seen and seen.get("open") else None


def from_an_automation(request: str) -> bool:
    """Whether the request is an automation's turn (_FROM_AN_AUTOMATION): it is answered in words, never planned."""
    return bool(_FROM_AN_AUTOMATION.match(request or ""))


def asks_for_a_change(request: str) -> bool:
    """Whether the request opens with a verb that changes something (_OPENS_WITH_A_CHANGE): a task, never an answer."""
    return bool(_OPENS_WITH_A_CHANGE.match(request or ""))


def routed_to_refusal(request: Any) -> bool:
    """The switch-case's first Case: the bounds refused the request (ADR-0014)."""
    return isinstance(request, RoutedRequest) and request.kind == REFUSE_STEP


def routed_to_answer(request: Any) -> bool:
    """The switch-case's one Case: the router said this is a question to answer in words."""
    return isinstance(request, RoutedRequest) and request.kind == "answer"


class Router(Executor):
    """The classifier before the plan (Learn, Workflows > Edges, switch-case; _workflow_builder.py
    add_switch_case_edge_group): one call on Steward's own client with Route as response_format. Its input handlers
    are AgentExecutor's own (str, Message, list[Message]), so every host starts the graph as it started PLAN."""

    def __init__(
        self, client: Any, options: dict[str, Any], id: str = ROUTE_STEP,
        sitting: Callable[[], Awaitable[dict[str, Any] | None]] | None = None,
        profiles: Mapping[str, Profile] | None = None,
        on_pick: Callable[[Profile], None] | None = None,
    ) -> None:
        super().__init__(id=id)
        self._client = client
        self._options = options
        self._sitting = sitting  # the open sitting, read when a task names the ground (open_sitting_now)
        self._profiles = profiles or {}  # the harness profiles (ADR-0018); none: no profile is picked
        self._on_pick = on_pick  # puts the pick on each step's session (build_steward_workflow)

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
        # A direct ask (one of his Estate actions named by its tool name) is a task whatever its first word: in chat an
        # Estate action is planned and carded (ADR-0009). An automation's turn is still answered in words.
        direct = _agent.directly_named_action(request) is not None
        if (asks_only_to_read(request) and not direct) or from_an_automation(request):
            kind = "answer"
        elif asks_for_a_change(request) or direct:
            kind = "task"
        refusal = await self._refusal(request, kind, direct)
        # ADR-0018: the harness profile, picked once the bounds have spoken (a refused request runs under the profile
        # its refusal belongs to: refusal_profile), and a profile's own extra refusal (profiles.PROFILE_REFUSALS).
        profile = await self._pick(request, ctx, refusal)
        if refusal is None and profile is not None:
            refusal = _profiles.profile_refusal(profile.name, request_body(request))
        if refusal is not None:
            await ctx.send_message(RoutedRequest(messages=messages, kind=REFUSE_STEP, reason=refusal))
            return
        if kind == "answer":
            messages = [Message(role="system", contents=[Content.from_text(ANSWER_IN_WORDS)]), *messages]
        await ctx.send_message(RoutedRequest(messages=messages, kind=kind))

    async def _pick(self, request: str, ctx: WorkflowContext[Any], refusal: str | None = None) -> Profile | None:
        """The request's harness profile (ADR-0018 item 2): a request the bounds refused runs under its refusal's profile
        (refusal_profile, when profiles/ holds it); otherwise pick_profile's deterministic pick on the request (its
        source line included, so an automation's turn can be told apart); when two profiles' patterns match, one
        structured call on his own client chooses between them (an unparsed reply falls back to `general`). The pick is
        kept in the workflow's state, put on each step's session (on_pick), and named to the caller (ProfilePicked)."""
        if not self._profiles:
            return None
        if refusal is not None:
            name = refusal_profile(refusal, request)
            profile, how, candidates = self._profiles.get(name) or self._profiles[_profiles.GENERAL], "refusal", [name]
        else:
            profile, how, candidates = pick_profile(request, self._profiles)
        if profile is None:
            choice = create_model("ProfilePick", profile=(Literal[tuple(candidates)], ...))  # type: ignore[valid-type]
            reply = await self._client.get_response(
                [Message(role="system", contents=[Content.from_text(PROFILE_PROMPT)]), Message(role="user", contents=[Content.from_text(request)])],
                options={**self._options, "response_format": choice},
            )
            try:
                profile, how = self._profiles[choice.model_validate_json((reply.text or "").strip()).profile], "model"
            except ValueError:
                profile, how = self._profiles[_profiles.GENERAL], "default"
        ctx.set_state(_PROFILE_STATE_KEY, profile.card_view())
        if self._on_pick is not None:
            self._on_pick(profile)
        if (picks := PROFILE_PICKS.get()) is not None:
            picks.append(profile.ref)
        logger.info("Steward profile: %s (%s)", profile.ref, how)
        await ctx.add_event(ProfilePicked(profile.event(how), executor_id=self.id))
        return profile

    async def _refusal(self, request: str, kind: str | None, direct: bool) -> str | None:
        """The bounds' refusal of the request (ADR-0014, part 2), or None: the Archive named, a key file's content asked
        for, a change from WhatsApp, a change to the ground while the sitting is open, or a GitHub write (withheld, N17)."""
        if path := archive_in(request):
            return ARCHIVE_REFUSAL.format(path=path)
        if path := key_file_asked(request):
            return KEY_FILE_REFUSAL.format(path=path)
        if from_whatsapp(request) and (kind != "answer" or asks_for_a_change(request_body(request)) or direct):
            return WHATSAPP_REFUSAL
        if kind != "answer" and self._sitting is not None and names_the_ground(request) and (sitting := await self._sitting()):
            return SITTING_REFUSAL.format(sitting=_agent.sitting_named(sitting))
        if asks_for_a_github_write(request) and (kind != "answer" or asks_for_a_change(request_body(request))):
            return GITHUB_WRITE_REFUSAL
        return None


class Refuse(Executor):
    """The bounds' answer to a request they refuse (ADR-0014): the refusal, in words; no plan, no card, no model call."""

    def __init__(self, id: str = REFUSE_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def refuse(self, request: RoutedRequest, ctx: WorkflowContext[Any, Any]) -> None:
        await ctx.yield_output(request.reason or "Not done.")


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
    # ADR-0015: the request is already satisfied by what he read; ReadPlan answers with it (ALREADY_DONE), no card.
    already_done: str | None = Field(
        default=None,
        description=(
            "Only when what you read shows the request is already done (what it asks for is already there): what "
            "showed it, the file and the line, e.g. 'README.md line 7 already says python -m unittest -v'. Nothing is "
            "then changed. Leave it out otherwise."
        ),
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


def asks_only_to_go_ahead(plan: StewardPlan) -> bool:
    """A clarification every question of which offers only a yes and a no (_GO_AHEAD_CHOICES): it asks to go ahead,
    which is the plan card's own question."""
    def plain(choice: str) -> str:
        return " ".join(re.sub(r"[^\w,' ]", " ", str(choice).lower()).split()).strip(" ,")

    return (
        plan.type == PlanningResponseType.CLARIFICATION
        and bool(plan.questions)
        and all(q.choices and all(plain(c) in _GO_AHEAD_CHOICES for c in q.choices) for q in plan.questions)
    )


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


# The confirmation bar at 5039e0e (2026-11-05 09:05Z, the discount ask): his plan's step "Run the sample project tests"
# sent EXECUTE to run_shell("pytest -q") twice, both cards denied, and his last reply asked the user to allow test runs,
# not what he fixed. CHECK runs the tests of the files he changed by itself (python_tests_for_changes), so a step that
# only runs the tests is CHECK's: EXECUTE is told so, and marks it complete.
CHECKS_RUN_THE_TESTS = (
    "The checks run the tests of the files you change by themselves when you finish, so a step that only runs the "
    "tests is theirs: mark it complete without running them."
)
# The confirmation bars at 2b4b509 and e532fea (2026-11-05, the discount and README asks): the work was right, and his
# last reply was only "All remaining todos are completed and the tests now pass." or "Todos marked complete.", so the
# user's last line said nothing of what changed. EXECUTE is asked to end on what it changed, by file.
SAY_WHAT_CHANGED = "When the work is done, end with a line or two saying what you changed, naming each file."
# ADR-0015, part 2 (the 06:04 run: the line was already in the README; he wrote it again and reported "the rest of the
# file remains unchanged"): a step that would spoil the result against the request stops the plan (stop_and_report),
# and his report says what he noticed against the request, with what showed it.
STOP_IF_IT_SPOILS = (
    "Before each step, check it against the request: if carrying it out would make the result wrong or redundant (what "
    "the request asks for is already there, or the step goes against it), do not carry on: call stop_and_report with "
    "what you found and what showed it."
)
SAY_WHAT_GOES_AGAINST = (
    "Say also anything you noticed that goes against the request (something already there, a step that did not fit), "
    "with what showed it."
)
# The run's answer when he stopped (stop_and_report): his reason, and that nothing more ran or was committed.
STOPPED_REPORT = "Stopped before finishing, so nothing more was done and nothing is committed: {reason}"
# A change with no .py file has no test to run (ADR-0015: docs need no test run), and still ends at the commit card.
NO_TESTS_NEEDED = "No tests to run: no code changed (a docs change needs no test run)."


def untrusted_read_in(messages: Sequence[Message] | None) -> bool:
    """Whether a call to one of the untrusted sources (agent._SANDBOX_UNTRUSTED_SOURCES: notes, the Estate's reads, the
    web, a background agent's results) is in these messages: what EXPLORE read before the plan (ADR-0014)."""
    sources = _agent._SANDBOX_UNTRUSTED_SOURCES
    return any(c.type == "function_call" and c.name in sources for m in messages or [] for c in m.contents or [])


def execute_message(request: str, plan: str, steps: list[str], untrusted: bool = False) -> Message:
    """The message that asks EXECUTE to carry out the approved plan, with the plan's steps on it, and whether untrusted
    content was read before the plan (UNTRUSTED_READ_KEY, ADR-0014: EXECUTE's session is marked, so his shell stays shut)."""
    numbered = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1))
    text = (
        f"The user approved your plan. Carry it out now.\n\nRequest: {request}\n\nPlan: {plan}\n\nSteps (your todos):\n"
        f"{numbered}\n\nWork through the todos in order and mark each one complete when it is done. {STOP_IF_IT_SPOILS} "
        f"{CHECKS_RUN_THE_TESTS} {SAY_WHAT_CHANGED} {SAY_WHAT_GOES_AGAINST} "
        "Do not commit: the checks run when you finish, and once they pass you will be asked to commit."
    )
    # REQUEST_KEY: his request hints match the request alone, never the plan's wording (agent.asked_request).
    return Message(
        role="user", contents=[Content.from_text(text)],
        additional_properties={APPROVED_PLAN_KEY: list(steps), REQUEST_KEY: request, **({UNTRUSTED_READ_KEY: True} if untrusted else {})},
    )


def approved_plan_turn(mode_provider: AgentModeProvider, todo_provider: TodoProvider) -> Callable[..., Awaitable[None]]:
    """On the message carrying an approved plan: this session goes to execute mode and its todos are the plan's steps.

    Agent middleware, so it runs before the run's mode is read (plan_mode_turns) and acts on the run's own session,
    the one MAF checkpoints and restores (an executor holding a session would hold a stale one after a restore).
    """

    @agent_middleware
    async def approved_plan_turn_(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        steps = approved_steps(context.messages)
        # ADR-0014: untrusted content read before the plan marks this session too, so the bounds keep his shell shut.
        if context.session is not None and any(
            (getattr(m, "additional_properties", None) or {}).get(UNTRUSTED_READ_KEY) for m in context.messages or []
        ):
            context.session.state[UNTRUSTED_READ_KEY] = True
        if steps and context.session is not None:
            if list(steps) != [REPAIR_TODO]:
                # A new approved plan is a new run of work: the files it writes are the ones its commit takes.
                context.session.state[WRITTEN_FILES_KEY] = []
                context.session.state.pop(STOPPED_KEY, None)  # and an earlier stop (stop_and_report) is behind it
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
# shell's stand-in after untrusted content (agent.SANDBOX_SHELL_REFUSAL sends that step to execute_code). Only then:
# T1 heldout v1 run 2 (e94cb90, 2026-11-05 14:57Z, sandbox on, nothing untrusted read) EXECUTE wrote units.py with
# execute_code, into the sandbox's copy of harness/ (read-only to the workspace, <sandbox>), the tool answered "", and
# no .py file changed. So EXECUTE is offered it only once the session's shell is closed (agent.sandbox_shell_closed).
CODEACT_TOOL = "execute_code"
# todos_add (the steps set at a0fb3ca, 2026-11-05 04:49Z): EXECUTE's one call was todos_add, then it ended with no write
# to inventory.py. EXECUTE's todos are the approved plan's steps (approved_plan_turn writes them), so it is offered
# only the todo tools that work through them (todos_complete, todos_get_remaining, todos_get_all), never one to add.
EXECUTE_LEAVES_OUT = frozenset({GIT_COMMIT, CODEACT_TOOL, "todos_add", *_MODE_TOOLS})
# stop_and_report (ADR-0015) is EXECUTE's alone: reading for the plan, or answering in words, has nothing to stop.
# The direct ask (agent.DIRECT_ACTION_KEY: the request names one of his Estate actions by its tool name): EXPLORE is
# offered only the Estate's reads, so his reading is at most a status check and no code search or file read stands
# between the request and his plan (session-20261105-1110-535a: 18 EXPLORE calls, 15 minutes, before the card).
DIRECT_ASK_TOOLS = frozenset(f"secondbrain_{name}" for name in ESTATE_READS)
# ADR-0015, the reading budget: EXPLORE's reads before a plan are at most EXPLORE_READ_BUDGET tool calls (the 06:04 run
# of 2026-11-06 made 17 reads and searches in two minutes before planning a one-line README change). Past it, EXPLORE's
# calls are offered no tool, as MAF's own progressive tool exposure cuts a run's list (step_tools_turn), so its reply
# is its words and the plan call follows; EXECUTE reads what else it needs after the plan is approved.
EXPLORE_READ_BUDGET = 8


def offered_in_step(name: str, step: str | None, shell_closed: bool = False, direct: bool = False) -> bool:
    """Whether a step's model calls are offered the tool named name (a step of None is offered every tool); shell_closed
    is whether the sandbox has closed the session's run_shell (agent.sandbox_shell_closed); direct is whether the
    request is a direct ask (agent.DIRECT_ACTION_KEY), which narrows EXPLORE to DIRECT_ASK_TOOLS."""
    if name == STOP_AND_REPORT and step != EXECUTE_STEP:
        return False
    if step == EXPLORE_STEP:
        return name in (DIRECT_ASK_TOOLS if direct else PLAN_TOOLS)
    if step == PLAN_STEP:
        return False  # the plan call: tools off (plan_phases_turn), so it can only answer with the plan
    if step == ANSWER_STEP:
        return name not in ANSWER_LEAVES_OUT
    if step == EXECUTE_STEP:
        if name == CODEACT_TOOL:
            return shell_closed and _agent.hyperlight_sandbox_on()
        return name not in EXECUTE_LEAVES_OUT
    return True


async def step_tools_turn(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Chat middleware: this call's tools are its step's (offered_in_step), the step read from the call's session.

    The run's live tool list is cut in place, as MAF's own progressive tool exposure cuts it
    (FunctionInvocationContext.remove_tools, agent_framework/_middleware.py:580-625, "self.tools[:] = ..."): MAF's
    function loop runs calls from that same list, and a provider's chat middleware later in the chain adds its tools to
    it (MemoryContextProvider's write_memory), so a copy would lose those. A tool the step leaves out cannot run either.

    The tools cut are his tools, not misspellings: they are kept in the session (agent.LEFT_OUT_KEY, added to on each
    call, as the run's list stays cut for its later calls), so his name repair (agent.repair_tool_names, later in the
    chain) never turns a call to one of them into another tool's call; MAF answers it as not found.
    """
    session = context.session
    step = session.state.get(STEP_KEY) if session is not None else None
    tools = (context.options or {}).get("tools")
    if step is not None and isinstance(tools, list):
        closed = _agent.sandbox_shell_closed(session)
        direct = bool(session.state.get(_agent.DIRECT_ACTION_KEY))
        names = [getattr(t, "name", "") or "" for t in tools]
        # ADR-0018: the picked profile's allow-list, intersected with the step's own (nothing it does not name is offered).
        allowed = profile_tools(session)
        governed = harness_tool_names() if allowed is not None else frozenset()
        spent = step == EXPLORE_STEP and calls_made(session) >= read_budget(session)
        cut = {n for n in names if spent or not offered_in_step(n, step, closed, direct) or (allowed is not None and n in governed and n not in allowed)}
        tools[:] = [t for t, n in zip(tools, names) if n not in cut]
        kept = {*(session.state.get(_agent.LEFT_OUT_KEY) or []), *cut} - {n for n in names if n not in cut} - {""}
        session.state[_agent.LEFT_OUT_KEY] = sorted(kept)
    if step is not None and isinstance(instructions := (context.options or {}).get("instructions"), str):
        # The call's whole instructions (his own, the Charter, MAF's todo and mode texts, the profile's) name only the
        # tools the step offers (step_offers): t3-away's first run (2026-11-08, storage/evals/runs/away-first) called
        # todos_add two or three times a case in plan mode, where no todo tool is offered ("Requested function ... not
        # found", tripping MAF's three consecutive function-call errors: "the plan mode expects me to create todos via
        # todos_add but the tool is not listed"), and the check after (profile-check-away, 68f970c) mode_get in the plan
        # call. Each line naming one he is not offered here is dropped from this call's instructions.
        left_out = sorted(harness_tool_names() - step_offers(session, step))
        context.options["instructions"] = lines_naming_only_offered(instructions, left_out)
    await call_next()


def steward_tool_names() -> set[str]:
    """The tools of Steward's own, by the names his code gives them (agent.py's lists and tools; the MAF harness's own
    are profiles.MAF_HARNESS_TOOLS). evals.steward_tool_names is this list, which validate maps (capabilities.yaml)."""
    return {
        *(f"secondbrain_{name}" for name in (*_agent.ESTATE_READS, *_agent.ESTATE_ASKS, *_agent.ESTATE_ACTIONS)),
        *(f"secondbrain_{name}" for name in _agent._SECONDBRAIN_NOTES_TOOLS),  # noqa: SLF001
        *(f"atlas_{name}" for name in _agent._ATLAS_GIT_TOOLS),  # noqa: SLF001
        _agent.PR_CHECKS_TOOL, GIT_COMMIT, "run_shell", "get_repo_status", "search_code", CODEACT_TOOL,
        "hand_to_coder",  # the improvement round's (improvement_loop_workflow.py), his in an improve: round
        _agent.STOP_AND_REPORT,  # EXECUTE's stop (ADR-0015)
    }


def harness_tool_names() -> frozenset[str]:
    """Every tool name a profile's allow-list governs: Steward's own and the MAF harness's own. A tool outside both is
    no tool of his build (a test's scripted tool), and a profile does not cut it; his live build offering one is red in
    the gate (test_his_live_build_offers_no_tool_of_his_own_that_the_capability_map_does_not_know)."""
    return frozenset({*steward_tool_names(), *_profiles.MAF_HARNESS_TOOLS})


def session_profile(session: Any) -> dict[str, Any] | None:
    """The profile picked for this session's run (PROFILE_KEY, set by the router's pick), or None."""
    profile = (getattr(session, "state", None) or {}).get(PROFILE_KEY) if session is not None else None
    return profile if isinstance(profile, dict) else None


def profile_tools(session: Any) -> frozenset[str] | None:
    """The picked profile's tool allow-list, or None when the session has no profile (offered as before)."""
    profile = session_profile(session)
    return frozenset(profile.get("tools") or []) if profile is not None else None


def read_budget(session: Any) -> int:
    """EXPLORE's reading budget: the picked profile's read_budget, else EXPLORE_READ_BUDGET (ADR-0015)."""
    profile = session_profile(session)
    budget = profile.get("read_budget") if profile is not None else None
    return budget if isinstance(budget, int) and not isinstance(budget, bool) else EXPLORE_READ_BUDGET


# The steps a profile's reasoning effort is sent on: the AgentExecutors' model calls (ROUTE and COMMIT keep theirs).
_REASONING_STEPS = frozenset({ANSWER_STEP, EXPLORE_STEP, PLAN_STEP, EXECUTE_STEP})
# gpt-oss's own effort when none is sent (Ollama's gpt-oss template reasons at medium unless `think` names another), so a
# profile at it sends no `think`, and a run under it sends exactly the options it sent before profiles (general).
MODEL_REASONING = "medium"


@agent_middleware
async def profile_options_turn(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Agent middleware: the picked profile's reasoning effort as Ollama's `think` on this run's options (ADR-0018:
    gpt-oss's reasoning effort, the one model setting a profile may change). MAF's OllamaChatClient passes `think` to
    ollama's AsyncClient.chat as a top-level argument (agent_framework_ollama/_chat_client.py _prepare_options: a key
    not in OLLAMA_MODEL_OPTIONS goes top-level; OllamaChatOptions documents `think`), and ollama's chat takes "low",
    "medium" or "high" (ollama/_client.py). A profile at MODEL_REASONING sends none. Before step_options_turn, so an
    eval's STEWARD_<STEP>_THINK still wins."""
    session = context.session
    profile = session_profile(session)
    step = session.state.get(STEP_KEY) if session is not None else None
    effort = profile.get("reasoning") if profile is not None else None
    if step in _REASONING_STEPS and effort in _profiles.REASONING and effort != MODEL_REASONING:
        context.options = {**(context.options or {}), "think": effort}
    await call_next()


# The todo tools (MAF's TodoProvider) a step's instructions may name only when the step offers them.
TODO_TOOLS = ("todos_add", "todos_complete", "todos_remove", "todos_get_remaining", "todos_get_all")
_TOOL_WORD = r"(?<![\w]){}(?![\w])"


def lines_naming_only_offered(text: str, left_out: Sequence[str]) -> str:
    """The instruction text without its lines that name a tool in ``left_out`` (a tool the step does not offer)."""
    if not left_out:
        return text
    named = re.compile("|".join(_TOOL_WORD.format(re.escape(name)) for name in left_out))
    return "\n".join(line for line in text.split("\n") if not named.search(line))


# The harness's own mechanics: the plan's steps become his todos and the user's Approve switches his mode, so in the
# plan phase no line may send him to them (t3-away's away-first: todos_add; profile-check-away: mode_get).
_MECHANICS_TOOLS = frozenset({*_TODO_TOOLS, *_MODE_TOOLS})


def step_offers(session: Any, step: str) -> frozenset[str]:
    """The tools of his harness a step's instructions may name: those it offers (offered_in_step, within the picked
    profile's allow-list), whatever its read budget has spent. EXPLORE and PLAN (the tools-off plan call) also keep the
    tools the plan may put in its steps, EXECUTE's (a direct ask's hint names the Estate action the plan is for), but
    never the harness's mechanics (_MECHANICS_TOOLS), which no call of the plan phase can make."""
    closed = _agent.sandbox_shell_closed(session)
    direct = bool((getattr(session, "state", None) or {}).get(_agent.DIRECT_ACTION_KEY))
    allowed = profile_tools(session)

    def offered(at: str) -> set[str]:
        return {n for n in harness_tool_names() if offered_in_step(n, at, closed, direct) and (allowed is None or n in allowed)}

    if step in (EXPLORE_STEP, PLAN_STEP):
        return frozenset(offered(EXPLORE_STEP) | (offered(EXECUTE_STEP) - _MECHANICS_TOOLS))
    return frozenset(offered(step))


_CALLS_MADE_KEY = "steward_calls_made"


def calls_made(session: Any) -> int:
    """The tool calls this session has run (count_calls): EXPLORE's reads, for EXPLORE_READ_BUDGET."""
    return int(session.state.get(_CALLS_MADE_KEY, 0) or 0) if session is not None else 0


async def count_calls(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """Function middleware: each call a session runs is counted in its state (a chat call's messages hold only the
    run's input, not the function loop's calls, so the count is kept here, where MAF runs each call)."""
    session = context.session or _agent._RUN_SESSION.get()
    if session is not None:
        session.state[_CALLS_MADE_KEY] = calls_made(session) + 1
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
    # ADR-0015: whether EXECUTE's run wrote a file (a change that ends at the commit card even with no test to run),
    # and his reason when he stopped (stop_and_report: REPORT says it, no repair, no commit).
    changed: bool = False
    stopped: str | None = None


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
# The files EXECUTE's session says his write tools wrote (agent.written_files), set by CHECK for its checks' thread. The
# steps set at a3a3519 (2026-11-05 06:05Z): his fix put inventory.py back to its committed text (the evals plant the
# bug in the working copy only), git listed no change, the check ran nothing and the run ended with an empty report.
# A file he wrote is checked whether or not it differs from the commit.
_CHECK_WRITTEN: ContextVar[tuple[str, ...]] = ContextVar("steward_check_written", default=())


def check_written() -> list[str]:
    """The files his run wrote, as CHECK set them for this check (none outside a check)."""
    return list(_CHECK_WRITTEN.get())


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
    files += [f for f in check_written() if f.endswith(".py") and f not in files and (Path(workspace) / f).is_file()]
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

    def __init__(
        self, id: str = READ_PLAN_STEP, sitting: Callable[[], Awaitable[dict[str, Any] | None]] | None = None
    ) -> None:
        super().__init__(id=id)
        self._sitting = sitting  # the open sitting, read when a plan names the ground (open_sitting_now)

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
            again = (
                PLAN_IS_APPROVAL if offers_no_choices(plan) else PLAN_CARD_IS_THE_YES if asks_only_to_go_ahead(plan) else None
            )
        else:
            again = PLAN_NOT_A_CALL if ends_with_a_json_object(last) else None
        if again and not ctx.get_state(_PLAN_ASKED_AGAIN_KEY, False):
            ctx.set_state(_PLAN_ASKED_AGAIN_KEY, True)
            await ctx.send_message(AgentExecutorRequest(messages=[Message(role="user", contents=[Content.from_text(again)])]), target_id=PLAN_STEP)
            return
        ctx.set_state(_PLAN_ASKED_AGAIN_KEY, False)
        if plan is not None and (evidence := " ".join((plan.already_done or "").split())):
            await ctx.yield_output(ALREADY_DONE.format(evidence=evidence))  # ADR-0015: no plan, no card, no change
            return
        if plan is None:
            await ctx.yield_output(last)
        elif plan.type != PlanningResponseType.APPROVAL:
            await ctx.yield_output(clarification_text(plan))
        else:
            request = ctx.get_state(_REQUEST_STATE_KEY, None) or _first_user_text(response)
            # ADR-0014, part 2: a plan that names the Archive, or the ground while the sitting is open, gets no card.
            planned = "\n".join([plan.questions[0].message, *plan.steps])
            if path := archive_in(planned):
                await ctx.yield_output(ARCHIVE_REFUSAL.format(path=path))
                return
            if self._sitting is not None and names_the_ground(planned) and (sitting := await self._sitting()):
                await ctx.yield_output(SITTING_REFUSAL.format(sitting=_agent.sitting_named(sitting)))
                return
            # ADR-0014: whether EXPLORE read untrusted content, kept for EXECUTE (in the checkpoint, beside the request).
            ctx.set_state(UNTRUSTED_READ_KEY, untrusted_read_in(response.full_conversation or response.agent_response.messages))
            plan_data = {"request": request, "plan": plan.questions[0].message, "steps": plan.steps}
            # ADR-0018 item 2: one card for the plan and the harness (Approve approves both).
            if (profile := ctx.get_state(_PROFILE_STATE_KEY, None)) is not None:
                plan_data["profile"] = profile
            await ctx.send_message(plan_data, target_id=ASK_APPROVAL_STEP)


# The plan card as an A2UI surface (ADR-0013, the A2UI pilot; ExecPlan 0004): A2UI v0.9 messages for the basic
# catalog, built from the plan the card carries, sent beside the card as a custom workflow event of type A2UI. MAF's
# AG-UI host passes a custom workflow event to the client as a CUSTOM event named by its type (agent_framework_ag_ui
# _workflow_run.py); the Responses host does not pass it, so a client there draws its own card.
A2UI = "a2ui"
A2UI_VERSION = "v0.9"
A2UI_BASIC_CATALOG = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
A2UI_APPROVE, A2UI_DENY = "approve", "deny"


def plan_card_surface(plan: dict[str, Any], request_id: str) -> list[dict[str, Any]]:
    """The plan card's A2UI v0.9 messages: createSurface on the basic catalog, then updateComponents: a Column of a
    heading, the plan's words, one numbered Text per step, and a Row of the Approve and Deny Buttons, whose actions
    carry the card's id (the interrupt's id) so the client answers that card."""
    surface = f"plan-{request_id}"
    steps = [str(step) for step in plan.get("steps") or []]
    context = {"requestId": request_id}
    # ADR-0018 item 2: the harness the plan runs under, on the same card (card_line), when a profile was picked.
    harness = [{"id": "harness", "component": "Text", "text": card_line(plan["profile"])}] if isinstance(plan.get("profile"), dict) else []
    components: list[dict[str, Any]] = [
        {"id": "root", "component": "Column", "children": [
            "heading", "plan", *(f"step-{i}" for i in range(len(steps))), *(c["id"] for c in harness), "answers",
        ]},
        {"id": "heading", "component": "Text", "text": "Steward's plan", "variant": "h4"},
        {"id": "plan", "component": "Text", "text": str(plan.get("plan") or "")},
        *({"id": f"step-{i}", "component": "Text", "text": f"{i + 1}. {step}"} for i, step in enumerate(steps)),
        *harness,
        {"id": "answers", "component": "Row", "children": [A2UI_APPROVE, A2UI_DENY]},
        {"id": f"{A2UI_APPROVE}-label", "component": "Text", "text": "Approve"},
        {"id": f"{A2UI_DENY}-label", "component": "Text", "text": "Deny"},
        {"id": A2UI_APPROVE, "component": "Button", "child": f"{A2UI_APPROVE}-label", "variant": "primary",
         "action": {"event": {"name": A2UI_APPROVE, "context": context}}},
        {"id": A2UI_DENY, "component": "Button", "child": f"{A2UI_DENY}-label",
         "action": {"event": {"name": A2UI_DENY, "context": context}}},
    ]
    return [
        {"version": A2UI_VERSION, "createSurface": {"surfaceId": surface, "catalogId": A2UI_BASIC_CATALOG}},
        {"version": A2UI_VERSION, "updateComponents": {"surfaceId": surface, "components": components}},
    ]


class PlanCardSurface(WorkflowEvent[dict[str, Any]]):
    """The plan card's A2UI surface, a custom event of type A2UI: {"request_id": <the card's id>, "messages": [...]}.
    Over AG-UI it is CUSTOM {name: "a2ui", value: <that>}, sent before the card's interrupt."""

    def __init__(self, request_id: str, messages: list[dict[str, Any]], *, executor_id: str) -> None:
        super().__init__(A2UI, {"request_id": request_id, "messages": messages}, executor_id=executor_id)  # type: ignore[arg-type]  # a custom type


class AskApproval(Executor):
    """The user's approval of the plan (MAF's human input: ctx.request_info). The plan rides in the request, so it is
    in the checkpoint while the run waits. Approved: EXECUTE is asked to carry it out. Denied: nothing runs. The card
    is also described as an A2UI surface (PlanCardSurface, ADR-0013), sent just before it."""

    def __init__(self, id: str = ASK_APPROVAL_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def ask(self, plan: dict[str, Any], ctx: WorkflowContext[Any, Any]) -> None:
        call_id = f"{APPROVE_PLAN}-{uuid.uuid4().hex[:12]}"
        call = Content.from_function_call(call_id=call_id, name=APPROVE_PLAN, arguments=plan)
        await ctx.add_event(PlanCardSurface(call_id, plan_card_surface(plan, call_id), executor_id=self.id))
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
        message = execute_message(
            str(plan.get("request", "")), str(plan.get("plan", "")), list(plan.get("steps") or []),
            untrusted=bool(ctx.get_state(UNTRUSTED_READ_KEY, False)),
        )
        await ctx.send_message(AgentExecutorRequest(messages=[message]))


class Check(Executor):
    """Runs the checks on what EXECUTE did (model-free) and reports the attempt."""

    def __init__(
        self, checks: Checks, id: str = CHECK_STEP, written: Callable[[], list[str]] | None = None,
        stopped: Callable[[], str | None] | None = None,
    ) -> None:
        super().__init__(id=id)
        self._checks = checks
        self._written = written  # the files EXECUTE's session says he wrote (check_written)
        self._stopped = stopped  # his reason, when EXECUTE stopped (stop_and_report)

    @handler
    async def check(self, response: AgentExecutorResponse, ctx: WorkflowContext[CheckReport]) -> None:
        attempt = int(ctx.get_state(_ATTEMPT_KEY, 0) or 0) + 1
        ctx.set_state(_ATTEMPT_KEY, attempt)
        loop = asyncio.get_running_loop()

        def report(text: str) -> None:  # from the checks' thread: added on the loop, in order, before the check goes on
            asyncio.run_coroutine_threadsafe(ctx.add_event(StewardProgress(text, executor_id=self.id)), loop).result()

        token = _CHECK_PROGRESS.set(report)
        wrote = _CHECK_WRITTEN.set(tuple(self._written() if self._written is not None else ()))
        try:
            result = await asyncio.to_thread(self._checks, list(response.full_conversation or response.agent_response.messages))
        finally:
            _CHECK_WRITTEN.reset(wrote)
            _CHECK_PROGRESS.reset(token)
        passed, output = result if result is not None else (True, "")
        if output:
            await ctx.add_event(StewardProgress("check passed" if passed else "check failed", executor_id=self.id))
        changed = bool(self._written()) if self._written is not None else False
        stopped = self._stopped() if self._stopped is not None else None
        await ctx.send_message(CheckReport(attempt, passed, output, _last_text(response), changed=changed, stopped=stopped))


def needs_repair(report: Any) -> bool:
    """Edge condition: the checks failed and attempts are left."""
    return isinstance(report, CheckReport) and not report.stopped and not report.passed and report.attempt < MAX_ATTEMPTS


def ready_to_commit(report: Any) -> bool:
    """Edge condition: the work changed something and its checks passed (or it had none to run: a docs change,
    ADR-0015), and he did not stop, so the work can be committed."""
    return isinstance(report, CheckReport) and not report.stopped and report.passed and (bool(report.output) or report.changed)


def ready_for_report(report: Any) -> bool:
    """Edge condition: nothing was checked, or the attempts are spent; no commit is offered."""
    if not isinstance(report, CheckReport):
        return False
    if report.stopped:
        return True
    return (report.passed and not report.output and not report.changed) or (not report.passed and report.attempt >= MAX_ATTEMPTS)


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
        message = await self._message(request, files, report.output or NO_TESTS_NEEDED)
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
        if report.stopped:
            await ctx.yield_output(STOPPED_REPORT.format(reason=report.stopped))
        if report.output:
            await ctx.yield_output(checks_text(report))


def checks_text(report: CheckReport) -> str:
    """The checks' result as the user reads it (a change with no test to run says so: NO_TESTS_NEEDED)."""
    if report.passed and not report.output:
        return NO_TESTS_NEEDED
    result = "passed" if report.passed else f"still fail after {report.attempt} attempts"
    return f"Checks {result}:\n{report.output[-_OUTPUT_TAIL:]}"


def executor_session(executor: AgentExecutor) -> Any:
    """The session an AgentExecutor runs its agent in: the one MAF checkpoints and restores with it
    (on_checkpoint_save's "agent_session", _agent_executor.py:682 and :721-730). MAF has no public getter for it."""
    return executor._session  # noqa: SLF001


def build_steward_workflow(
    agent: Agent[Any], checks: Checks = python_tests_for_changes, changes: Callable[[], list[str]] | None = None,
    profiles: Mapping[str, Profile] | None = None,
) -> Workflow:
    """The graph over one build_steward_agent Steward: route, then answer, or plan, read_plan, ask_approval, execute,
    check, repair, then ask_commit and commit when the checks passed on changed code, else report. ``changes`` lists
    the files the commit message is written from: by default the files EXECUTE's run wrote, which are the ones his
    git_commit commits (agent.written_files). ``profiles`` are the harness profiles the router picks from (ADR-0018),
    by default harness/steward/profiles/ (profiles.load_profiles: a profile that cannot be used stops the build here)."""
    from agent import OLLAMA_OPTIONS  # noqa: PLC0415

    modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
    todos = next(p for p in agent.context_providers if isinstance(p, TodoProvider))
    step_options = step_options_from_env()  # a bad value stops the build here, before any call
    profiles = load_profiles() if profiles is None else profiles
    # The picked profile's instructions, added for the task by MAF's own context-provider seam (ProfileInstructions).
    if not any(isinstance(p, ProfileInstructions) for p in agent.context_providers):
        agent.context_providers.append(ProfileInstructions())
    agent.middleware = [
        approved_plan_turn(modes, todos),
        plan_mode_turns(modes, response_format=StewardPlan),
        plan_phases_turn,  # after plan_mode_turns: EXPLORE drops its response_format, PLAN turns its tools off
        profile_options_turn,  # ADR-0018: the profile's reasoning effort; before step_options_turn, which wins
        # Only when a step has overrides: unset, every call's options are what they were before.
        *([step_options_turn(step_options)] if step_options else []),
        # Chat middleware, first of his chat middleware, so the name repair and the text-call recovery read the step's
        # tools (repair_tool_names, recover_text_tool_calls): each step's calls are offered only its tools.
        step_tools_turn,
        count_calls,  # ADR-0015: EXPLORE's calls, for its reading budget
        *(agent.middleware or []),
    ]
    # His own window and keep-alive on the router's call, so Ollama answers it with the model as loaded.
    base = {k: v for k, v in (agent.default_options or {}).items() if k in OLLAMA_OPTIONS}
    for step, overrides in step_options.items():
        logger.info("Steward step %s: model options %s", step, {**base, **overrides})
    async def sitting() -> dict[str, Any] | None:
        return await open_sitting_now(agent)

    step_executors: list[AgentExecutor] = []

    def picked(profile: Profile) -> None:  # the pick on each step's session, where its middleware reads it
        for executor in step_executors:
            executor_session(executor).state[PROFILE_KEY] = profile.state()

    route = Router(agent.client, {**base, **step_options.get(ROUTE_STEP, {})}, sitting=sitting, profiles=profiles, on_pick=picked)
    refuse = Refuse()
    # The answer step's own session says it answers in words: plan_mode_turns asks it for no StewardPlan. The session,
    # with its state, is in the workflow's checkpoint (AgentExecutor.on_checkpoint_save).
    answer_session = step_session(agent, ANSWER_STEP)
    answer_session.state[IN_WORDS_KEY] = True
    answer = AgentExecutor(agent, session=answer_session, id=ANSWER_STEP)
    # EXPLORE's session reads for the plan: an empty reply there is asked once to go on reading (agent.READS_FIRST_KEY).
    explore_session = step_session(agent, EXPLORE_STEP)
    explore_session.state[READS_FIRST_KEY] = True
    explore = AgentExecutor(agent, session=explore_session, id=EXPLORE_STEP)
    # PLAN takes EXPLORE's conversation and PLAN_NOW (MAF's chaining, AgentExecutor.from_response, context_mode custom).
    plan = AgentExecutor(
        agent, session=step_session(agent, PLAN_STEP), id=PLAN_STEP, context_mode="custom", context_filter=plan_call_input
    )
    read_plan = ReadPlan(sitting=sitting)
    ask_approval = AskApproval()
    execute = AgentExecutor(agent, session=step_session(agent, EXECUTE_STEP), id=EXECUTE_STEP)
    step_executors.extend([answer, explore, plan, execute])
    check = Check(
        checks, written=lambda: written_files(executor_session(execute)), stopped=lambda: stopped_reason(executor_session(execute))
    )
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
            output_from=[refuse, read_plan, ask_approval, repair, ask_commit, commit, report],
            intermediate_output_from=[answer, execute],
        )
        .add_switch_case_edge_group(
            route,
            [Case(condition=routed_to_refusal, target=refuse), Case(condition=routed_to_answer, target=answer), Default(target=explore)],
        )
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
