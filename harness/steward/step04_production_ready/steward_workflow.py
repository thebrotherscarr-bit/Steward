"""Steward's stages as a MAF workflow (Kyle, 2026-11-01: "the harness makes it actually follow the rules").

MAF's builder skill (references/harness-agent-builder.md): "Use a workflow instead when explicit graph topology,
routing, checkpointed stages, or intermediate outputs define correctness." Plan, approve, execute, check and report
are such stages, so their order is the graph's, not the model's choice.

Pieces 1 to 4 of the build order:

    request -> plan (AgentExecutor, plan mode, structured output StewardPlan) -> read_plan
            -> ask_approval (the workflow pauses: ctx.request_info) -> execute (AgentExecutor, execute mode) -> check
            -> (failed, attempts left) repair -> execute -> check ...
            -> (passed, or attempts spent) report

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
* Hosting (MAF native, Kyle's choice 2026-11-01): ResponsesHostServer(workflow=factory) builds a fresh graph and a
  fresh Steward for every request ("Native workflow requests cannot share workflows, executors, agents, clients,
  or providers", _workflow_source.py), so the factory is in hosted.py.

Run one request through it on Ollama (PLAN only reads; it stops at the approval):
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\steward_workflow.py "<request>"
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import uuid
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentContext,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentModeProvider,
    Content,
    Executor,
    FileAccessProvider,
    Message,
    TodoItem,
    TodoProvider,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    agent_middleware,
    handler,
    response_handler,
    set_agent_mode,
)
from dotenv import load_dotenv
from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console.observers.planning_models import PlanningQuestion, PlanningResponse, PlanningResponseType  # noqa: E402
from hosted import planning_response_in, plan_mode_turns  # noqa: E402

# A fixed name: the host checks a reply's rebuilt graph against the stored one by name and signature.
WORKFLOW_NAME = "steward"
PLAN_STEP = "plan"
READ_PLAN_STEP = "read_plan"
ASK_APPROVAL_STEP = "ask_approval"
EXECUTE_STEP = "execute"
CHECK_STEP = "check"
REPAIR_STEP = "repair"
REPORT_STEP = "report"
# EXECUTE's attempts at a plan before REPORT says the checks still fail (the improvement loop's MAX_ATTEMPTS).
MAX_ATTEMPTS = 3
_ATTEMPT_KEY = "steward_check_attempt"
_OUTPUT_TAIL = 1500
# The approval card's name: what the user is approving is the plan, carried in its arguments.
APPROVE_PLAN = "approve_plan"
# The approved plan's steps, on the message that asks EXECUTE to carry it out (read by approved_plan_turn).
APPROVED_PLAN_KEY = "steward_approved_plan"
NOT_APPROVED = "The plan was not approved, so nothing was run. Tell me what to change and I will plan again."
# Sent to PLAN once when its reply was empty; ReadPlan keeps whether it has been sent in the workflow's state.
PLAN_AGAIN = "Your reply was empty. Reply with your plan for the request above."
_PLAN_ASKED_AGAIN_KEY = "steward_plan_asked_again"


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
        f"{numbered}\n\nWork through the todos in order and mark each one complete when it is done."
    )
    return Message(role="user", contents=[Content.from_text(text)], additional_properties={APPROVED_PLAN_KEY: list(steps)})


def approved_plan_turn(mode_provider: AgentModeProvider, todo_provider: TodoProvider) -> Callable[..., Awaitable[None]]:
    """On the message carrying an approved plan: this session goes to execute mode and its todos are the plan's steps.

    Agent middleware, so it runs before the run's mode is read (plan_mode_turns) and acts on the run's own session,
    the one MAF checkpoints and restores (an executor holding a session would hold a stale one after a restore).
    """

    @agent_middleware
    async def approved_plan_turn_(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        steps = next(
            (
                m.additional_properties[APPROVED_PLAN_KEY]
                for m in context.messages or []
                if APPROVED_PLAN_KEY in (getattr(m, "additional_properties", None) or {})
            ),
            None,
        )
        if steps and context.session is not None:
            set_agent_mode(
                context.session, "execute", source_id=mode_provider.source_id, available_modes=mode_provider.available_modes
            )
            items = [TodoItem(id=n, title=str(step)) for n, step in enumerate(steps, start=1)]
            await todo_provider.store.save_state(
                context.session, items, next_id=len(items) + 1, source_id=todo_provider.source_id
            )
        await call_next()

    return approved_plan_turn_


@dataclass
class CheckReport:
    """One attempt's checks: output is empty when nothing was there to check."""

    attempt: int
    passed: bool
    output: str
    answer: str


# A check: given EXECUTE's messages, (passed, output), or None when there is nothing to check.
Checks = Callable[[Sequence[Message]], "tuple[bool, str] | None"]


def written_python_files(messages: Sequence[Message]) -> list[str]:
    """The .py files EXECUTE's calls to MAF's file-writing tools named, in order, once each.

    A write that waited on the user's card is not in the response as a call: after the pause, the AgentExecutor's
    response starts from the user's answer (_agent_executor.py), and the call it approves rides on that answer
    (function_approval_response.function_call). So approved answers count, and denied ones do not.
    """
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
            name = str((call.parse_arguments() or {}).get("file_name") or "")
            if name.endswith(".py") and name not in files:
                files.append(name)
    return files


def python_tests_for_writes(messages: Sequence[Message]) -> tuple[bool, str] | None:
    """The tests in each written file's folder (pytest; "no tests collected" passes). None when no code was written."""
    from agent import _WORKING_DIR  # noqa: PLC0415 - the folder his file tools write in

    files = written_python_files(messages)
    if not files:
        return None
    targets = sorted({str(Path(f).parent) if str(Path(f).parent) != "." else f for f in files})
    outputs: list[str] = []
    passed = True
    for target in targets:
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target]
        done = subprocess.run(
            command, cwd=_WORKING_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300
        )
        outputs.append(f"$ pytest -q {target}\n(exit {done.returncode})\n{(done.stdout + done.stderr)[-_OUTPUT_TAIL:]}")
        passed = passed and done.returncode in (0, 5)  # 5: no tests collected
    return passed, "\n\n".join(outputs)


class ReadPlan(Executor):
    """Reads PLAN's reply in code: an approval goes on for the user's approval; anything else ends the run as it is.

    An empty reply (live 2026-11-01: the model's whole answer stayed in its reasoning) is sent back to PLAN once for
    the plan, as the cookbook's "Validate JSON ... in code" has a bad reply asked again; a reply in words is not.
    """

    def __init__(self, id: str = READ_PLAN_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def read(
        self, response: AgentExecutorResponse, ctx: WorkflowContext[dict[str, Any] | AgentExecutorRequest, Any]
    ) -> None:
        last = _last_text(response)
        if not last.strip() and not ctx.get_state(_PLAN_ASKED_AGAIN_KEY, False):
            ctx.set_state(_PLAN_ASKED_AGAIN_KEY, True)
            await ctx.send_message(AgentExecutorRequest(messages=[Message(role="user", contents=[Content.from_text(PLAN_AGAIN)])]), target_id=PLAN_STEP)
            return
        ctx.set_state(_PLAN_ASKED_AGAIN_KEY, False)
        plan = steward_plan_in(last)
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
        await ctx.request_info(
            request_data=Content.from_function_approval_request(id=call_id, function_call=call), response_type=Content
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
        result = await asyncio.to_thread(self._checks, list(response.full_conversation or response.agent_response.messages))
        passed, output = result if result is not None else (True, "")
        await ctx.send_message(CheckReport(attempt, passed, output, _last_text(response)))


def needs_repair(report: Any) -> bool:
    """Edge condition: the checks failed and attempts are left."""
    return isinstance(report, CheckReport) and not report.passed and report.attempt < MAX_ATTEMPTS


def ready_for_report(report: Any) -> bool:
    """Edge condition: the checks passed, or the attempts are spent."""
    return isinstance(report, CheckReport) and (report.passed or report.attempt >= MAX_ATTEMPTS)


class Repair(Executor):
    """Sends the failing checks back to EXECUTE, in its own session (still execute mode)."""

    def __init__(self, id: str = REPAIR_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def repair(self, report: CheckReport, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        text = (
            f"The checks failed after attempt {report.attempt} of {MAX_ATTEMPTS}. Fix the cause, then stop and say "
            f"what you changed.\n\nCheck output:\n{report.output}"
        )
        await ctx.send_message(AgentExecutorRequest(messages=[Message(role="user", contents=[Content.from_text(text)])]))


class Report(Executor):
    """EXECUTE's answer is the run's output, with the checks' result when any ran."""

    def __init__(self, id: str = REPORT_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def report(self, report: CheckReport, ctx: WorkflowContext[Any, Any]) -> None:
        if not report.output:
            await ctx.yield_output(report.answer)
            return
        result = "passed" if report.passed else f"still fail after {report.attempt} attempts"
        await ctx.yield_output(f"{report.answer}\n\nChecks {result}:\n{report.output[-_OUTPUT_TAIL:]}")


def build_steward_workflow(agent: Agent[Any], checks: Checks = python_tests_for_writes) -> Workflow:
    """The graph over one build_steward_agent Steward: plan, read_plan, ask_approval, execute, check, repair, report."""
    modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
    todos = next(p for p in agent.context_providers if isinstance(p, TodoProvider))
    agent.middleware = [
        approved_plan_turn(modes, todos),
        plan_mode_turns(modes, response_format=StewardPlan),
        *(agent.middleware or []),
    ]
    plan = AgentExecutor(agent, id=PLAN_STEP)
    read_plan = ReadPlan()
    ask_approval = AskApproval()
    execute = AgentExecutor(agent, id=EXECUTE_STEP)
    check = Check(checks)
    repair = Repair()
    report = Report()
    # The run's output is the steps' own (a reply, a clarification, a refusal, the report); the agents' raw
    # responses stay intermediate.
    return (
        WorkflowBuilder(name=WORKFLOW_NAME, start_executor=plan, output_from=[read_plan, ask_approval, report])
        .add_edge(plan, read_plan)
        .add_edge(read_plan, plan)  # an empty plan reply, asked again once
        .add_edge(read_plan, ask_approval)
        .add_edge(ask_approval, execute)
        .add_edge(execute, check)
        .add_edge(check, repair, condition=needs_repair)
        .add_edge(check, report, condition=ready_for_report)
        .add_edge(repair, execute)
        .build()
    )


async def main(request: str) -> None:
    """One request through the graph, streamed as the host runs it; prints the output or the approval card."""
    load_dotenv()
    from agent import build_steward_agent  # noqa: PLC0415

    async with AsyncExitStack() as stack:
        agent = await build_steward_agent(stack, enable_shell=False)
        async with agent:
            events = [e async for e in build_steward_workflow(agent).run(request, stream=True)]
    for event in events:
        if event.type == "output":
            print(f"Output: {event.data}")
        elif event.type == "request_info":
            print(f"Approval card: {event.data.function_call.name} {event.data.function_call.arguments}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main(" ".join(sys.argv[1:]) or "Add a docstring to order_total in harness/steward/working/sample-project/inventory.py."))
