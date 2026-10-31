"""DevUI host for the production-ready Steward (ADR-0001 item 7): each run and its trace in a browser.

MAF's DevUI with tracing (ui/devui/tracing), run as MAF's github_mcp_example.py
(samples/02-agents/security) runs it for an agent that holds live MCP connections: DevUI's serve()
starts its own event loop, which would orphan Steward's MCP sessions, so DevServer runs under uvicorn
on this loop. Tracing is on as configure_otel_providers sets it, with every span also written to
halo_traces/traces.jsonl, as console_app.py does.

DevUI is a development tool ("not intended for production use"). It listens on loopback only and
asks for DevUI's bearer token.

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE — see agent.py
    DEVUI_AUTH_TOKEN            — DevUI's bearer token; a fresh one is made and printed when unset
    OTEL_EXPORTER_OTLP_ENDPOINT — Optional OTLP collector endpoint

Run:
    python harness/steward/step04_production_ready/devui_app.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import sys
from contextlib import AsyncExitStack, suppress
from pathlib import Path
from typing import Any

import uvicorn
from agent_framework.observability import configure_otel_providers
from agent_framework_devui._server import DevServer
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402
from halo_traces import HaloJsonlSpanExporter  # noqa: E402

HOST = "127.0.0.1"
PORT = 8080  # DevUI's default


def build_dev_server(agent: Any, auth_token: str) -> DevServer:
    """DevUI's server with Steward registered in memory, as the sample registers its agent."""
    server = DevServer(port=PORT, host=HOST, auth_enabled=True, auth_token=auth_token)
    server.set_pending_entities([agent])
    return server


async def main() -> None:
    """Serve Steward in DevUI, on the loop that holds his MCP connections."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    configure_otel_providers(exporters=[HaloJsonlSpanExporter()], enable_sensitive_data=True)

    async with AsyncExitStack() as stack:
        agent = await stack.enter_async_context(await build_steward_agent(stack))
        auth_token = os.getenv("DEVUI_AUTH_TOKEN") or secrets.token_urlsafe(32)
        server = build_dev_server(agent, auth_token)

        print(f"\nDevUI:        http://{HOST}:{PORT}  (entity: agent_{agent.name})")
        print(f"Bearer token: {auth_token}")
        print("Press Ctrl+C to stop.\n")

        await uvicorn.Server(uvicorn.Config(server.get_app(), host=HOST, port=PORT, log_level="info")).serve()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
