"""Steward as a local service (Step 4): the guide's ``hosted.py``, on this PC instead of Foundry.

Serves the same ``build_steward_agent`` the console uses over the Responses protocol
(``ResponsesHostServer``), on loopback only. SecondBrain is the client: it sends turns here and
answers Steward's approval requests (``mcp_approval_request`` out, ``mcp_approval_response`` in).

Changes from the guide for local Ollama:
    * No Foundry project, credential, Purview or per-request scoping: there is one user, Kyle, so
      one Steward is built at start and kept warm (its SecondBrain connection and shell stay open).
    * File access and the shell stay on: this runs on Kyle's own PC, not a shared container.
    * Background tasks are still released at the end of each request, as in the guide.

Its own telemetry stays local (steward_observability): spans to halo_traces/traces.jsonl as before, metrics and
OpenTelemetry log records to halo_traces/metrics.jsonl and halo_traces/logs.jsonl (one compact JSON line each, rotated
at 10 MB, five kept), and nothing of it on stdout, which SecondBrain writes to steward.log.

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE, SECONDBRAIN_MCP_* — see agent.py
    STEWARD_PORT — port to serve on (defaults to 43120)

Run:
    python harness/steward/step04_production_ready/hosted.py
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any
from contextlib import AsyncExitStack, asynccontextmanager
from logging.handlers import RotatingFileHandler
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
from agent_framework.observability import OBSERVABILITY_SETTINGS
from agent_framework_foundry_hosting import CheckpointStoreProvider, HostedResponseRequest, ResponsesHostServer, WorkflowTurn
from azure.ai.agentserver.responses import FileResponseStore
from dotenv import load_dotenv
from opentelemetry.sdk._logs.export import ConsoleLogRecordExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # harness/, for the console's planning models
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent, steward_memory_store  # noqa: E402
from console.observers.planning_models import PlanningResponse  # noqa: E402
from halo_traces import HALO_TRACE_PATH, setup_halo_tracing  # noqa: E402

logger = logging.getLogger(__name__)
# A turn's request metadata key naming the mode to switch to before it runs: the Agent tab's Approve
# sends {"agent_mode": "execute"}, as the console's Approve calls set_agent_mode.
AGENT_MODE_KEY = "agent_mode"
# Step 6, 6.3: a turn whose request metadata carries {"steward_workflow": "improve"} runs the improvement loop
# (improvement_loop_workflow.py: the coder fixer, the gate, the review) instead of his request workflow. The Agent
# tab sends it on every turn of an improve conversation, so a card's answer resumes the same workflow.
IMPROVE_KEY = "steward_workflow"
IMPROVE = "improve"
PLAN_MODE = "plan"
# A session whose state holds this answers in words: plan_mode_turns asks it for no plan (the workflow's answer step).
IN_WORDS_KEY = "steward_answers_in_words"
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
            in_words = context.session.state.get(IN_WORDS_KEY, False)
            if not in_words and get_agent_mode(context.session, default_mode=mode_provider.default_mode, **modes) == PLAN_MODE:
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
    from steward_workflow import build_steward  # noqa: PLC0415

    stack = AsyncExitStack()
    if client_factory is not None:  # a fresh chat client per request too (tests pass a scripted one)
        build["client"] = client_factory()
    try:
        if wants_improvement(request):
            agent, workflow = await _improvement_loop(stack, **build)
        else:
            agent, workflow = await build_steward(
                stack, history_provider=InMemoryHistoryProvider(), memory_store=steward_memory_store(), **build
            )
    except BaseException:
        await stack.aclose()
        raise
    agent._async_exit_stack.push_async_callback(stack.aclose)  # noqa: SLF001 - the agent's close owns the stack
    background_providers = [p for p in agent.context_providers if isinstance(p, BackgroundAgentsProvider)]
    agent.middleware = [
        _release_background_per_request(background_providers),
        _only_his_own_words,
        _host_identity_stays_with_tools,
        *(agent.middleware or []),
    ]
    return workflow


def wants_improvement(request: Any) -> bool:
    """Whether this turn belongs to an improve conversation (its request metadata names the loop)."""
    metadata = getattr(request, "request", {}).get("metadata")
    return isinstance(metadata, Mapping) and metadata.get(IMPROVE_KEY) == IMPROVE


async def _improvement_loop(stack: AsyncExitStack, **build: Any) -> tuple[Any, Any]:
    """The improvement loop on MAF's host: Steward diagnosing (build_diagnoser) and the small coder (build_coder) in
    the loop's graph, the host's own checkpoints, and the gate's checks read at call time."""
    import improvement_loop_workflow as loop  # noqa: PLC0415

    agent = await loop.build_diagnoser(
        stack, history_provider=InMemoryHistoryProvider(), memory_store=steward_memory_store(), **build
    )
    coder = loop.build_coder(build.get("client"))
    coder.middleware = [_host_identity_stays_with_tools, *(coder.middleware or [])]  # the coder calls Ollama too
    return agent, loop.create_workflow(agent, coder, None, checks=loop.GATE_CHECKS)


@chat_middleware
async def _host_identity_stays_with_tools(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """The workflow host hands every agent call additional_function_arguments (the caller's session, user and call ids,
    _workflow_source.py) as a client kwarg. MAF's function layer treats it as "for tool invocation only and not
    recognized by chat service APIs" (_tools.py) and drops it from the options, but the Ollama client passes every
    client kwarg on to ollama's chat(), which refuses it. It is dropped here, before the model call."""
    context.kwargs.pop("additional_function_arguments", None)
    await call_next()


@agent_middleware
async def _only_his_own_words(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    """The Agent tab shows his own words, not the harness loop's prompts to him (live 2026-11-03).

    MAF's AgentLoopMiddleware streams each injected next_message ("Progress so far", the open-todo reminder) as a
    user update between passes (_harness/_loop.py, _process_streaming: "yield self._message_to_update(message)"; its
    return_final_only has "no effect on streaming runs"). EXECUTE's AgentExecutor yields every update as output, and
    the Responses host's tracker does not read the role, so the nudges were glued into his message. MAF's own
    WorkflowAgent forwards assistant updates only (_workflows/_agent.py, "Filter out non-assistant updates"); here the
    user updates are dropped with ResponseStream.flat_map (zero or more updates per update), and his next pass gets a
    new message_id, since a changed message_id "marks a new logical message" for the host (_responses.py,
    _OutputItemTracker.handle). The run's final response is the loop's own, unchanged.
    """
    await call_next()
    inner = context.result
    if not context.stream or not isinstance(inner, ResponseStream):
        return
    message = {"id": uuid.uuid4().hex}

    def his_own(update: AgentResponseUpdate) -> list[AgentResponseUpdate]:
        if update.role == "user":
            message["id"] = uuid.uuid4().hex  # a nudge ends his pass: the next one is a new message
            return []
        if update.message_id is None:
            update = copy.copy(update)  # as AgentExecutor copies an update before changing it (_agent_executor.py)
            update.message_id = message["id"]
        return [update]

    context.result = inner.flat_map(his_own, finalizer=lambda _: inner.get_final_response())


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
    metadata.pop(IMPROVE_KEY, None)
    if metadata:
        options["metadata"] = metadata
    return options


# <observability>
# The host's default observability (azure.ai.agentserver core/_base.py:271, configure_observability) is the
# microsoft-opentelemetry distro, which turns on its console exporters when no Azure Monitor, A365 or OTLP exporter is
# set (microsoft/opentelemetry/_distro.py:344, _console/handler.py:46-52): every metric, span and OTel log record
# pretty-printed as JSON on stdout, which SecondBrain writes to steward.log (192 MB on 2026-11-03). The host takes "a
# custom callable to override the setup" (_base.py:252-258), so Steward's is MAF's configure_otel_providers, through
# setup_halo_tracing: spans to HALO as before, and metrics and OTel logs through OpenTelemetry's own console exporters
# writing to a file instead of stdout (their out= and formatter=, opentelemetry/sdk/metrics/_internal/export/
# __init__.py:143-146 and sdk/_logs/_internal/export/__init__.py:147-150), one compact line each (to_json(indent=None)).
TELEMETRY_DIR = HALO_TRACE_PATH.parent  # halo_traces/, gitignored
TELEMETRY_MAX_BYTES = 10 * 1024 * 1024
TELEMETRY_BACKUPS = 5


class RotatingLines:
    """A text stream for the console exporters' ``out``: each line goes through stdlib logging's RotatingFileHandler,
    so the file is rolled over at max_bytes with ``backups`` old files kept."""

    def __init__(self, path: Path, max_bytes: int = TELEMETRY_MAX_BYTES, backups: int = TELEMETRY_BACKUPS) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8", delay=True)

    def write(self, text: str) -> None:
        for line in text.splitlines():
            if line.strip():
                self.handler.handle(logging.makeLogRecord({"msg": line}))

    def flush(self) -> None:
        self.handler.flush()

    def close(self) -> None:
        self.handler.close()


def telemetry_file_exporters(directory: Path = TELEMETRY_DIR) -> list[Any]:
    """Metrics (gen_ai.client.operation.duration, gen_ai.client.token.usage, agent_framework.function.invocation.duration)
    and OTel log records, each as one JSON line in a rotating file under ``directory``, never on stdout."""
    return [
        ConsoleMetricExporter(
            out=RotatingLines(directory / "metrics.jsonl"), formatter=lambda data: data.to_json(indent=None) + "\n"
        ),
        ConsoleLogRecordExporter(
            out=RotatingLines(directory / "logs.jsonl"), formatter=lambda record: record.to_json(indent=None) + "\n"
        ),
    ]


# MAF's workflow host logs a failed turn by its exception's type alone, inside the except block
# (agent_framework_foundry_hosting/_workflow_responses.py:583, and :416 for a failed abort), so the TypeError of
# 2026-11-03 left no trace and cost a day. The same package's _log_response_failure (_responses.py:182-196) attaches
# exc_info when sensitive data is on; this filter does the same for the workflow host's records: the exception being
# handled when it logs is the one it names.
WORKFLOW_HOST_LOGGER = "agent_framework_foundry_hosting._workflow_responses"


def _with_traceback(record: logging.LogRecord) -> bool:
    if record.levelno >= logging.ERROR and not record.exc_info and OBSERVABILITY_SETTINGS.SENSITIVE_DATA_ENABLED:
        handled = sys.exc_info()
        if handled[1] is not None:
            record.exc_info = handled
    return True


def show_workflow_failure_tracebacks() -> None:
    """Put the traceback on the workflow host's error records (a logging filter on its logger; idempotent)."""
    host = logging.getLogger(WORKFLOW_HOST_LOGGER)
    if _with_traceback not in host.filters:
        host.addFilter(_with_traceback)


def steward_observability(**_: Any) -> None:
    """The host's configure_observability hook. The host passes connection_string, log_level and enable_sensitive_data
    (_base.py:306-311); nothing leaves this PC, the log level is main's, and sensitive data is on, as for HALO."""
    show_workflow_failure_tracebacks()
    setup_halo_tracing(exporters=telemetry_file_exporters())


# </observability>


def steward_server(
    client_factory: Callable[[], Any] | None = None,
    observability: Callable[..., None] | None = None,
    **build: Any,
) -> ResponsesHostServer:
    """Steward's workflow on MAF's Responses host (Kyle, 2026-11-01: MAF native hosting).

    ``observability`` is the host's configure_observability: main passes steward_observability; None (tests) sets
    nothing up, where the host's default would print every metric to stdout.
    """
    os.environ.setdefault("AGENTSERVER_STATE_ROOT", str(_AGENTSERVER_STATE_DIR))
    # One user on one PC: one platform session, so a reply (previous_response_id) finds the run it answers. Without
    # it the first request gets a random session and its reply a derived one, two scopes, and the reply is refused
    # ("The previous response has no completed workflow checkpoint in this trusted scope"); the order is
    # azure.ai.agentserver.responses.hosting._request_parsing._resolve_session_id (B39).
    os.environ.setdefault("FOUNDRY_AGENT_SESSION_ID", _LOCAL_SESSION_ID)
    return ResponsesHostServer(
        workflow=lambda request: steward_graph(request, client_factory, **dict(build)),
        configure_observability=observability,
        parse_response=steward_turn,
        prepare_options=steward_options,
        response_store=FileResponseStore(_STORAGE_DIR),
        # The routed request (ROUTE -> ANSWER | PLAN), the plan's structured output (PLAN's response) and a check's
        # report (CHECK -> REPAIR | REPORT) are in the checkpoint; MAF's decoder admits named types only.
        checkpoint_store_provider=CheckpointStoreProvider(allowed_checkpoint_types=[
            "steward_workflow:RoutedRequest",
            "steward_workflow:StewardPlan",
            "steward_workflow:CheckReport",
            # An approved run_shell's result (agent._shell_text_copies: the text is rebuilt from its ShellResult).
            "agent_framework_tools.shell._types:_ShellResultText",
            "agent_framework_tools.shell._types:ShellResult",
            "console.observers.planning_models:PlanningResponseType",
            "console.observers.planning_models:PlanningQuestion",
            # The improvement loop's own records (step 6, 6.3).
            "improvement_loop_workflow:CheckReport",
            "improvement_loop_workflow:ReviewRequest",
            "improvement_loop_workflow:LoopResult",
        ]),
    )


async def main() -> None:
    """Serve Steward on 127.0.0.1:STEWARD_PORT until stopped."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = int(os.environ.get("STEWARD_PORT", "43120"))
    # Every span goes to halo_traces/traces.jsonl (cookbook improvement loop, step 2), metrics and OTel logs to their
    # rotating files beside it: the host runs steward_observability as it is built.
    server = steward_server(observability=steward_observability)
    logger.info("Steward serving on http://127.0.0.1:%d (Responses protocol, MAF workflow).", port)
    await server.run_async(host="127.0.0.1", port=port)


if __name__ == "__main__":
    asyncio.run(main())
