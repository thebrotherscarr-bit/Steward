"""Steward as a local service (Step 4): the guide's ``hosted.py``, on this PC instead of Foundry.

Serves the same ``build_steward_agent`` the console uses over the Responses protocol
(``ResponsesHostServer``), on loopback only. SecondBrain is the client: it sends turns here and
answers Steward's approval requests (``mcp_approval_request`` out, ``mcp_approval_response`` in).

Changes from the guide for local Ollama:
    * No Foundry project, credential, Purview or per-request scoping: there is one user, Kyle, so
      one Steward is built at start and kept warm (its SecondBrain connection and shell stay open).
    * File access and the shell stay on: this runs on Kyle's own PC, not a shared container.
    * Background tasks are still released at the end of each request, as in the guide.

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE, SECONDBRAIN_MCP_* — see agent.py
    STEWARD_PORT — port to serve on (defaults to 43120)

Run:
    python harness/steward/step04_production_ready/hosted.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from agent_framework import (
    AgentContext,
    AgentModeProvider,
    AgentResponseUpdate,
    BackgroundAgentsProvider,
    ChatContext,
    InMemoryHistoryProvider,
    ResponseStream,
    agent_middleware,
    chat_middleware,
    get_agent_mode,
    set_agent_mode,
)
from agent_framework_foundry_hosting import CheckpointStoreProvider, HostedResponseRequest, ResponsesHostServer, WorkflowTurn
from azure.ai.agentserver.responses import FileResponseStore
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402
from console.observers.planning_models import PlanningResponse  # noqa: E402
from halo_traces import setup_halo_tracing  # noqa: E402

logger = logging.getLogger(__name__)
# A turn's request metadata key naming the mode to switch to before it runs: the Agent tab's Approve
# sends {"agent_mode": "execute"}, as the console's Approve calls set_agent_mode.
AGENT_MODE_KEY = "agent_mode"
PLAN_MODE = "plan"
# The response chain is kept on disk so a conversation continues after a restart.
_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "responses"
# The host's own state (the workflow's checkpoints, sessions, approvals) defaults to ~/.agentserver
# (azure.ai.agentserver.core._config.resolve_state_subdir), outside the workspace. Its file names run to 191
# characters (function_approvals' base64 store name plus a temp suffix), so the root must stay within 68 to keep
# under Windows' 260 (2026-11-01: storagegentserver came to 262 and every checkpoint save failed). Kyle's ruling:
# a short folder in the repo, .as (gitignored).
_AGENTSERVER_STATE_DIR = Path(__file__).resolve().parents[3] / ".as"
_LOCAL_SESSION_ID = "steward-local"
# A turn that answers the workflow's pending request (the plan's approval card, a tool's card) carries these items.
_REPLY_ITEM_TYPES = ("mcp_approval_response", "function_call_output")


def _release_background_per_request(background_providers: list[BackgroundAgentsProvider]) -> Callable[..., Awaitable[None]]:
    """The guide's middleware: release a request's background tasks when the request ends."""

    @agent_middleware
    async def request_background_lifetime(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        if context.session is None:
            raise RuntimeError("The hosted harness requires a request-owned AgentSession.")
        session = context.session

        @asynccontextmanager
        async def release_background() -> AsyncIterator[None]:
            run_failed = False
            try:
                yield
            except BaseException:
                run_failed = True
                raise
            finally:
                try:
                    for provider in background_providers:
                        await provider.release_session(session)
                except BaseException as cleanup_error:
                    logger.error("Failed to release request-owned background tasks (%s).", type(cleanup_error).__name__)
                    if not run_failed:
                        raise

        if context.stream:
            # Streaming returns before iteration; teardown must wrap consumption, not construction.
            try:
                await call_next()
            except BaseException:
                async with release_background():
                    raise
            inner = context.result
            if not isinstance(inner, ResponseStream):
                async with release_background():
                    raise RuntimeError("The streaming hosted harness must return a ResponseStream.")

            cleaned_up = False

            async def cleanup() -> None:
                nonlocal cleaned_up
                if cleaned_up:
                    return
                cleaned_up = True
                async with release_background():
                    await inner.close()

            async def updates() -> AsyncIterator[AgentResponseUpdate]:
                run_failed = False
                try:
                    async for update in inner:
                        yield update
                    await inner.get_final_response()
                except BaseException:
                    run_failed = True
                    raise
                finally:
                    try:
                        await cleanup()
                    except BaseException as cleanup_error:
                        logger.error("Failed to clean up the request stream (%s).", type(cleanup_error).__name__)
                        if not run_failed:
                            raise

            context.result = ResponseStream(
                updates(), finalizer=lambda _: inner.get_final_response(), cleanup_hooks=[cleanup]
            )
        else:
            async with release_background():
                await call_next()

    return request_background_lifetime


def planning_response_in(text: str, model: type[PlanningResponse] = PlanningResponse) -> PlanningResponse | None:
    """The PlanningResponse in a plan-mode reply, or None.

    With tools offered, gpt-oss writes a short preamble before the constrained JSON in the same reply
    (gate runs 2 and 4, 2026-11-01: 'We added todo. Now present the plan for approval.{"type":...}').
    The cookbook: "Validate JSON ... in code". The plan is the JSON object that ends the reply.
    """
    text = (text or "").strip()
    start = 0
    while (start := text.find("{", start)) != -1:
        try:
            plan = model.model_validate_json(text[start:])
        except ValueError:
            start += 1
            continue
        # Plan run 13: an approval with an empty questions list is valid JSON and holds no plan; the Agent tab's
        # reader (utils/planning.ts) refuses it too, so the harness loop asks again.
        return plan if plan.questions else None
    return None


def plan_mode_turns(
    mode_provider: AgentModeProvider, response_format: type[PlanningResponse] = PlanningResponse
) -> Callable[..., Awaitable[None]]:
    """The guide's planning observer, on the server, where the session's mode lives.

    Part 1, "How plan mode works": in plan mode the console asks for PlanningResponse as
    response_format, so the reply is a clarification or a plan to approve, and its Approve
    switches the session to execute mode (harness/console/observers/planning_output.py,
    configure_run_options and _build_approval_action). The Agent tab cannot reach the session,
    so an approval comes as request metadata {"agent_mode": "execute"}, and both are done here.
    """
    modes = {"source_id": mode_provider.source_id, "available_modes": mode_provider.available_modes}

    @agent_middleware
    async def plan_mode_turn(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
        options = dict(context.options or {})
        metadata = dict(options.pop("metadata", None) or {})
        switch_to = metadata.pop(AGENT_MODE_KEY, None)
        if metadata:
            options["metadata"] = metadata
        if context.session is not None:
            if switch_to:
                set_agent_mode(context.session, str(switch_to), **modes)
            if get_agent_mode(context.session, default_mode=mode_provider.default_mode, **modes) == PLAN_MODE:
                options["response_format"] = response_format
        context.options = options
        await call_next()

    return plan_mode_turn


async def steward_graph(request: HostedResponseRequest, client_factory: Callable[[], Any] | None = None, **build: Any) -> Any:
    """MAF's request-aware workflow factory: a fresh Steward and a fresh graph for every request.

    MAF's native workflow host refuses to share agents, clients or providers between requests (_workflow_source.py,
    WorkflowResolver) and closes each agent when its request ends, so Steward is built here per request; what lasts
    between requests (each step's session, the pending approval) is in the workflow's checkpoint. The connections
    build_steward_agent opens (SecondBrain, the shell) are closed with the agent.
    """
    from steward_workflow import build_steward_workflow  # noqa: PLC0415

    stack = AsyncExitStack()
    if client_factory is not None:  # a fresh chat client per request too (tests pass a scripted one)
        build["client"] = client_factory()
    try:
        agent = await build_steward_agent(stack, history_provider=InMemoryHistoryProvider(), **build)
    except BaseException:
        await stack.aclose()
        raise
    agent._async_exit_stack.push_async_callback(stack.aclose)  # noqa: SLF001 - the agent's close owns the stack
    workflow = build_steward_workflow(agent)
    background_providers = [p for p in agent.context_providers if isinstance(p, BackgroundAgentsProvider)]
    agent.middleware = [
        _release_background_per_request(background_providers),
        _host_identity_stays_with_tools,
        *(agent.middleware or []),
    ]
    return workflow


@chat_middleware
async def _host_identity_stays_with_tools(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """The workflow host hands every agent call additional_function_arguments (the caller's session, user and call ids,
    _workflow_source.py) as a client kwarg. MAF's function layer treats it as "for tool invocation only and not
    recognized by chat service APIs" (_tools.py) and drops it from the options, but the Ollama client passes every
    client kwarg on to ollama's chat(), which refuses it. It is dropped here, before the model call."""
    context.kwargs.pop("additional_function_arguments", None)
    await call_next()


async def steward_turn(request: HostedResponseRequest) -> WorkflowTurn[Any]:
    """MAF's parse_response: an answer to the pending card resumes the run; anything else is a new request."""
    items = await request.get_input_items()
    if any((item.get("type") if hasattr(item, "get") else None) in _REPLY_ITEM_TYPES for item in items):
        return WorkflowTurn(responses=await request.get_workflow_responses())
    return WorkflowTurn(input=(await request.get_input_text()) or "")


def steward_options(request: HostedResponseRequest, options: dict[str, Any]) -> dict[str, Any]:
    """MAF's prepare_options hook: each step sets its own output format (PLAN asks for StewardPlan, EXECUTE for none).

    The Agent tab sends the console's PlanningResponse as response_format, and its agent_mode metadata, on its plan
    turns; MAF's host would apply them to every agent in the graph (2026-11-01: EXECUTE was asked for a plan).
    """
    options = dict(options)
    options.pop("response_format", None)
    metadata = dict(options.pop("metadata", None) or {})
    metadata.pop(AGENT_MODE_KEY, None)
    if metadata:
        options["metadata"] = metadata
    return options


def steward_server(client_factory: Callable[[], Any] | None = None, **build: Any) -> ResponsesHostServer:
    """Steward's workflow on MAF's Responses host (Kyle, 2026-11-01: MAF native hosting)."""
    os.environ.setdefault("AGENTSERVER_STATE_ROOT", str(_AGENTSERVER_STATE_DIR))
    # One user on one PC: one platform session, so a reply (previous_response_id) finds the run it answers. Without
    # it the first request gets a random session and its reply a derived one, two scopes, and the reply is refused
    # ("The previous response has no completed workflow checkpoint in this trusted scope"); the order is
    # azure.ai.agentserver.responses.hosting._request_parsing._resolve_session_id (B39).
    os.environ.setdefault("FOUNDRY_AGENT_SESSION_ID", _LOCAL_SESSION_ID)
    return ResponsesHostServer(
        workflow=lambda request: steward_graph(request, client_factory, **dict(build)),
        parse_response=steward_turn,
        prepare_options=steward_options,
        response_store=FileResponseStore(_STORAGE_DIR),
        # The plan's structured output is in the checkpoint (PLAN's response); MAF's decoder admits named types only.
        checkpoint_store_provider=CheckpointStoreProvider(allowed_checkpoint_types=[
            "steward_workflow:StewardPlan",
            "console.observers.planning_models:PlanningResponseType",
            "console.observers.planning_models:PlanningQuestion",
        ]),
    )


async def main() -> None:
    """Serve Steward on 127.0.0.1:STEWARD_PORT until stopped."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = int(os.environ.get("STEWARD_PORT", "43120"))
    # Every span goes to halo_traces/traces.jsonl (cookbook improvement loop, step 2).
    setup_halo_tracing()
    logger.info("Steward serving on http://127.0.0.1:%d (Responses protocol, MAF workflow).", port)
    await steward_server().run_async(host="127.0.0.1", port=port)


if __name__ == "__main__":
    asyncio.run(main())
