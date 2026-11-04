"""Interactive local host for the production-ready Steward (Step 4).

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE — see agent.py
    ENABLE_INSTRUMENTATION      — Controls Agent Framework instrumentation
    ENABLE_CONSOLE_EXPORTERS    — Enables console OpenTelemetry exporters when true
    OTEL_EXPORTER_OTLP_ENDPOINT — Optional OTLP collector endpoint, spoken to over http/protobuf
                                  (setup_halo_tracing passes otlp_protocol="http/protobuf"; MAF's default
                                  is gRPC, whose exporter is not installed)

Run:
    python harness/steward/step04_production_ready/console_app.py [--session ID]

His history is kept on disk per session (agent.steward_history_provider, storage/history): the console prints its
session ID at start, and --session ID continues that conversation after a restart.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from agent_framework.observability import get_tracer
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace.span import format_trace_id

_HARNESS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_HARNESS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent, steward_history_provider, steward_memory_store  # noqa: E402
from halo_traces import setup_halo_tracing  # noqa: E402
from console import build_observers_with_planning, run_agent_async  # noqa: E402


async def main(session_id: str | None = None) -> None:
    """Run the production-ready Steward in the local interactive console; ``session_id`` continues a session."""
    load_dotenv()
    # The guide logs to the console, but the TUI owns this screen: lines written under it garble the
    # display. Startup diagnostics and request logs go to steward.log instead.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        filename="steward.log",
        encoding="utf-8",
    )
    # Every span also goes to halo_traces/traces.jsonl (cookbook improvement loop, step 2): MAF's
    # configure_otel_providers, as hosted.py and mcp_app.py set it up.
    setup_halo_tracing()

    with get_tracer().start_as_current_span("Steward Console Session", kind=trace.SpanKind.CLIENT) as current_span:
        print(f"Trace ID: {format_trace_id(current_span.get_span_context().trace_id)}")
        async with AsyncExitStack() as stack:
            agent = await build_steward_agent(
                stack, history_provider=steward_history_provider(), memory_store=steward_memory_store()
            )
            async with agent:
                session = agent.create_session(session_id=session_id)
                print(f"Session: {session.session_id} (continue it with --session {session.session_id})")
                await run_agent_async(
                    agent,
                    session=session,
                    observers=build_observers_with_planning(agent),
                    initial_mode="execute",
                    title="🛠️ Steward",
                    placeholder="Map a codebase, review changes, fix a failing test, or run the build...",
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Steward's console.")
    parser.add_argument("--session", help="a session ID to continue; its history is read from storage/history")
    asyncio.run(main(parser.parse_args().session))
