"""Steward's stages as a MAF workflow (Kyle, 2026-11-01: "the harness makes it actually follow the rules").

MAF's builder skill (references/harness-agent-builder.md): "Use a workflow instead when explicit graph topology,
routing, checkpointed stages, or intermediate outputs define correctness." Plan, approve, execute, check and report
are such stages, so their order is the graph's, not the model's choice.

Pieces 1 to 3 of the build order:

    request -> plan (AgentExecutor, plan mode, structured output StewardPlan) -> read_plan
            -> ask_approval (the workflow pauses: ctx.request_info) -> execute (AgentExecutor, execute mode) -> report

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
* Hosting (MAF native, Kyle's choice 2026-11-01): ResponsesHostServer(workflow=factory) builds a fresh graph and a
  fresh Steward for every request ("Native workflow requests cannot share workflows, executors, agents, clients,
  or providers", _workflow_source.py), so the factory is in hosted.py.

Run one request through it on Ollama (PLAN only reads; it stops at the approval):
    .venv\\Scripts\\python harness\\steward\\step04_production_ready\\steward_workflow.py "<request>"
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
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
from console.observers.planning_models import PlanningResponse, PlanningResponseType  # noqa: E402
from hosted import planning_response_in, plan_mode_turns  # noqa: E402

# A fixed name: the host checks a reply's rebuilt graph against the stored one by name and signature.
WORKFLOW_NAME = "steward"
PLAN_STEP = "plan"
READ_PLAN_STEP = "read_plan"
ASK_APPROVAL_STEP = "ask_approval"
EXECUTE_STEP = "execute"
REPORT_STEP = "report"
# The approval card's name: what the user is approving is the plan, carried in its arguments.
APPROVE_PLAN = "approve_plan"
# The approved plan's steps, on the message that asks EXECUTE to carry it out (read by approved_plan_turn).
APPROVED_PLAN_KEY = "steward_approved_plan"
NOT_APPROVED = "The plan was not approved, so nothing was run. Tell me what to change and I will plan again."


class StewardPlan(PlanningResponse):
    """The guide's PlanningResponse with the plan's steps, which become his todo list."""

    # Required, so it is in the schema's "required" list: Ollama's structured output (format = this schema) lets the
    # model leave out a field that is not, and a plan without steps has nothing to approve or run.
    steps: list[str] = Field(
        description=(
            "For approvals: the plan's steps in order, one short imperative line each (e.g. 'Read inventory.py', "
            "'Fix the discount line'). They become your todo list. Empty for clarifications."
        ),
    )


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


class ReadPlan(Executor):
    """Reads PLAN's reply in code: an approval goes on for the user's approval; anything else ends the run as it is."""

    def __init__(self, id: str = READ_PLAN_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def read(self, response: AgentExecutorResponse, ctx: WorkflowContext[dict[str, Any], Any]) -> None:
        last = _last_text(response)
        plan = steward_plan_in(last)
        if plan is None:
            await ctx.yield_output(last)
        elif plan.type != PlanningResponseType.APPROVAL:
            await ctx.yield_output(plan.model_dump_json())
        else:
            await ctx.send_message({"request": _first_user_text(response), "plan": plan.questions[0].message, "steps": plan.steps})


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
        message = execute_message(str(plan.get("request", "")), str(plan.get("plan", "")), list(plan.get("steps") or []))
        await ctx.send_message(AgentExecutorRequest(messages=[message]))


class Report(Executor):
    """EXECUTE's answer is the run's output."""

    def __init__(self, id: str = REPORT_STEP) -> None:
        super().__init__(id=id)

    @handler
    async def report(self, response: AgentExecutorResponse, ctx: WorkflowContext[Any, Any]) -> None:
        await ctx.yield_output(_last_text(response))


def build_steward_workflow(agent: Agent[Any]) -> Workflow:
    """The graph over one build_steward_agent Steward: plan, read_plan, ask_approval, execute, report."""
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
    report = Report()
    # The run's output is the steps' own (a reply, a clarification, a refusal, the report); the agents' raw
    # responses stay intermediate.
    return (
        WorkflowBuilder(name=WORKFLOW_NAME, start_executor=plan, output_from=[read_plan, ask_approval, report])
        .add_edge(plan, read_plan)
        .add_edge(read_plan, ask_approval)
        .add_edge(ask_approval, execute)
        .add_edge(execute, report)
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
