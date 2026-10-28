"""Interactive local host for the production-ready Steward (Step 4).

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE — see agent.py
    ENABLE_INSTRUMENTATION      — Controls Agent Framework instrumentation
    ENABLE_CONSOLE_EXPORTERS    — Enables console OpenTelemetry exporters when true
    OTEL_EXPORTER_OTLP_ENDPOINT — Optional OTLP collector endpoint

Run:
    python harness/steward/step04_production_ready/console_app.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from agent_framework.observability import configure_otel_providers, get_tracer
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace.span import format_trace_id

_HARNESS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_HARNESS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402
from halo_traces import HaloJsonlSpanExporter  # noqa: E402
from console import build_observers_with_planning, run_agent_async  # noqa: E402


async def main() -> None:
    """Run the production-ready Steward in the local interactive console."""
    load_dotenv()
    # The guide logs to the console, but the TUI owns this screen: lines written under it garble the
    # display. Startup diagnostics and request logs go to steward.log instead.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        filename="steward.log",
        encoding="utf-8",
    )
    # Every span also goes to halo_traces/traces.jsonl (cookbook improvement loop, step 2).
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)

    with get_tracer().start_as_current_span("Steward Console Session", kind=trace.SpanKind.CLIENT) as current_span:
        print(f"Trace ID: {format_trace_id(current_span.get_span_context().trace_id)}")
        async with AsyncExitStack() as stack:
            agent = await build_steward_agent(stack)
            async with agent:
                await run_agent_async(
                    agent,
                    session=agent.create_session(),
                    observers=build_observers_with_planning(agent),
                    initial_mode="execute",
                    title="🛠️ Steward",
                    placeholder="Map a codebase, review changes, fix a failing test, or run the build...",
                )


if __name__ == "__main__":
    asyncio.run(main())
