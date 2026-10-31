"""Steward as an MCP tool (ADR-0001 item 10): Manjuel's mcp_call, or any MCP client, can call him.

MAF's MCP hosting sample session_app.py (samples/04-hosting/mcp), on this PC instead of Foundry:
AgentMCPTool over AgentState, so a reused ``session_id`` continues one conversation, with calls
serialized per ``session_id``. The MCP SDK's stateless streamable HTTP with JSON responses serves it,
under uvicorn on the loop that holds Steward's MCP connections, as devui_app.py runs DevUI.

As in the sample, the endpoint is unauthenticated and listens on loopback only.

Approvals do not cross this boundary: mcp_from_run returns text, links and data, and omits an
approval request. A tool that waits for approval (git_commit, file writes, the shell) does not run
through this door; the Agent tab, where Kyle answers approvals, stays the way to work with him.

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE, SECONDBRAIN_MCP_* — see agent.py

Run:
    python harness/steward/step04_production_ready/mcp_app.py

Then point an MCP client at http://127.0.0.1:8000/mcp, for example Manjuel's mcp_call with
MANJUEL_MCP_STEWARD=http://127.0.0.1:8000/mcp in its .env.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from agent_framework import InMemoryHistoryProvider
from agent_framework_hosting import AgentState
from agent_framework_hosting_mcp import AgentMCPTool
from dotenv import load_dotenv
from mcp import MCPError, types
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402
from halo_traces import setup_halo_tracing  # noqa: E402

HOST = "127.0.0.1"
PORT = 8000  # MAF's MCP hosting samples' port


def build_mcp_app(agent: Any) -> Starlette:
    """The sample's session-aware server, with Steward as its agent."""
    state = AgentState(agent)
    agent_tool = AgentMCPTool(
        state,
        argument_description="The request for the hosted agent.",
        parameters={
            "session_id": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Opaque, app-defined conversation key. Reuse the same value to continue and update one conversation."
                ),
            }
        },
        required_parameters={"session_id"},
        session_id_parameter="session_id",
    )
    session_locks: dict[str, asyncio.Lock] = {}

    async def list_tools(
        _ctx: ServerRequestContext[dict[str, Any]], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        """Return the agent-derived MCP tool definition."""
        return await agent_tool.list_tools()

    async def call_tool(
        _ctx: ServerRequestContext[dict[str, Any]], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        """Serialize calls per app-owned session before using ``AgentState``."""
        name = params.name
        arguments = params.arguments or {}
        session_id = arguments.get("session_id") if arguments else None
        if not isinstance(session_id, str) or not session_id:
            raise MCPError(types.INVALID_PARAMS, "MCP tool argument 'session_id' must be a non-empty string.")
        lock = session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await agent_tool.call_tool(name, arguments)

    server = Server("steward", on_list_tools=list_tools, on_call_tool=call_tool)
    session_manager = StreamableHTTPSessionManager(app=server, event_store=None, json_response=True, stateless=True)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncGenerator[None]:
        """Start and stop the native MCP session manager."""
        async with session_manager.run():
            yield

    return Starlette(routes=[Mount("/", app=session_manager.handle_request)], lifespan=lifespan)


async def main() -> None:
    """Serve Steward as an MCP tool on HOST:PORT until stopped."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Every span goes to halo_traces/traces.jsonl, as hosted.py does.
    setup_halo_tracing()

    async with AsyncExitStack() as stack:
        # Each conversation's history lives in its session, as in the sample (and hosted.py).
        agent = await build_steward_agent(stack, history_provider=InMemoryHistoryProvider())
        async with agent:
            app = build_mcp_app(agent)
            await uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="info")).serve()


if __name__ == "__main__":
    asyncio.run(main())
