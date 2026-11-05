"""Steward as an MCP tool (ADR-0001 item 10): Manjuel's mcp_call, or any MCP client, can call him.

MAF's MCP hosting sample session_app.py (samples/04-hosting/mcp), on this PC instead of Foundry:
AgentMCPTool over AgentState, so a reused ``session_id`` continues one conversation, with calls
serialized per ``session_id``. The MCP SDK's stateless streamable HTTP with JSON responses serves it,
under uvicorn on the loop that holds Steward's MCP connections, as devui_app.py runs DevUI.

As in the sample, the endpoint is unauthenticated and listens on loopback only.

Approvals cross it through SecondBrain (2026-11-04): mcp_from_run omits an approval request, so a tool that waits
for one (git_commit, file writes, the shell) used to end the turn unanswered. Now each function_approval_request is
asked on SecondBrain's approval_ask (its MCP server, the same URL and key as agent.py's), which raises Kyle's own card
(the Agent tab, the Approvals shelf, Telegram) tagged "Manjuel / MCP" and waits up to 10 minutes (then No). His answer
goes back to Steward as MAF's function_approval_response on the same session, as the harness tests answer a card
(``to_function_approval_response``), and the turn continues. Without SecondBrain, the cards are left unanswered.

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE, SECONDBRAIN_MCP_* — see agent.py

Run:
    python harness/steward/step04_production_ready/mcp_app.py

Then point an MCP client at http://127.0.0.1:43121/mcp, for example Manjuel's mcp_call with
MANJUEL_MCP_STEWARD=http://127.0.0.1:43121/mcp in its .env.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

import httpx2
import uvicorn
from agent_framework import AgentResponse, Content, FileSessionStore, Message
from agent_framework_hosting import AgentState
from agent_framework_hosting_mcp import AgentMCPTool
from dotenv import load_dotenv
from mcp import Client, MCPError, types
from mcp.client.streamable_http import streamable_http_client
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import (  # noqa: E402
    _WORKING_DIR,
    build_steward_agent,
    steward_history_provider,
    steward_memory_store,
)

MCP_SESSIONS_DIR = _WORKING_DIR / "storage" / "mcp-sessions"
from halo_traces import setup_halo_tracing  # noqa: E402

HOST = "127.0.0.1"
# Beside his service (43120) and SecondBrain's MCP (43110), Kyle's word 2026-11-02; it was MAF's samples' 8000,
# which ComfyUI also takes
PORT = 43121

logger = logging.getLogger("steward.mcp_app")

# SecondBrain answers a card No after 10 minutes (approval_ask); its call is read for that long, and a little more.
CARD_WAIT_SECONDS = 660.0
# Rounds of cards in one turn before the turn ends with any left unanswered (the loop terminates).
MAX_CARD_ROUNDS = 10

# One card to Kyle: (the function_approval_request, the MCP session_id) -> his answer, True for Allow.
AskCard = Callable[[Content, str], Awaitable[bool]]


def secondbrain_cards(client: Any) -> AskCard:
    """Ask each card on SecondBrain's approval_ask over ``client`` (an MCP Client). Anything but an Allow is No."""

    async def ask(card: Content, session_id: str) -> bool:
        call = card.function_call
        arguments = call.parse_arguments() if call is not None else None
        try:
            result = await client.call_tool(
                "approval_ask",
                {"tool": call.name if call is not None else "", "arguments": arguments or {}, "session_id": session_id},
                read_timeout_seconds=CARD_WAIT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 - SecondBrain down or the wait cut: the card is No, the turn goes on
            logger.warning("approval_ask failed (%s): the card is answered No", type(exc).__name__)
            return False
        if result.is_error:
            logger.warning("approval_ask refused: the card is answered No")
            return False
        try:
            answer = json.loads(next(c.text for c in result.content if c.type == "text"))
        except (StopIteration, ValueError):
            return False
        return isinstance(answer, dict) and answer.get("approved") is True

    return ask


def approval_cards(result: AgentResponse[Any]) -> list[Content]:
    """The cards a run ended on: its function_approval_request contents."""
    return [c for m in result.messages for c in m.contents if c.type == "function_approval_request"]


async def run_with_cards(
    agent_tool: AgentMCPTool[Any], name: str, arguments: Mapping[str, Any], ask_card: AskCard
) -> types.CallToolResult:
    """AgentMCPTool.call_tool's session run, with each card asked on ``ask_card`` and answered on the same session.

    The run, the session and the conversion are AgentMCPTool's own (state, mcp_to_run, mcp_from_run); the answers go
    back as function_approval_response contents, so the turn continues until it ends on no card (or MAX_CARD_ROUNDS).
    """
    target = await agent_tool.state.get_target()
    tool_name = (await agent_tool.list_tools()).tools[0].name
    if name != tool_name:
        raise MCPError(types.INVALID_PARAMS, f"Unknown MCP tool: {name}")
    run = agent_tool.mcp_to_run(arguments)
    session_id = str(arguments["session_id"])
    session = await agent_tool.state.get_or_create_session(session_id)
    result = await target.run(run["messages"], options=run["options"], session=session, stream=False)
    messages = list(result.messages)
    for _ in range(MAX_CARD_ROUNDS):
        cards = approval_cards(result)
        if not cards:
            break
        answers = [card.to_function_approval_response(await ask_card(card, session_id)) for card in cards]
        result = await target.run(Message(role="user", contents=answers), options=run["options"], session=session, stream=False)
        messages.extend(result.messages)
    await agent_tool.state.set_session(session_id, session)
    return types.CallToolResult(content=agent_tool.mcp_from_run(AgentResponse(messages=messages)))


def steward_mcp_tool(agent: Any) -> AgentMCPTool[Any]:
    """The sample's AgentMCPTool over AgentState, with Steward as its agent."""
    # Step 5 (5.2): each session_id's conversation is kept on disk, so Manjuel's sessions survive a restart.
    state = AgentState(agent, session_store=FileSessionStore(MCP_SESSIONS_DIR))
    return AgentMCPTool(
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


def build_mcp_app(agent: Any, ask_card: AskCard | None = None) -> Starlette:
    """The sample's session-aware server, with Steward as its agent; ``ask_card`` answers his cards (SecondBrain)."""
    agent_tool = steward_mcp_tool(agent)
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
            if ask_card is None:
                return await agent_tool.call_tool(name, arguments)
            return await run_with_cards(agent_tool, name, arguments, ask_card)

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
        # Each session_id's history is kept on disk by MAF's FileHistoryProvider (storage/history, 2026-11-04).
        agent = await build_steward_agent(
            stack, history_provider=steward_history_provider(), memory_store=steward_memory_store()
        )
        # His cards go to SecondBrain's approval_ask, on a client of their own: a card waits up to 10 minutes, longer
        # than agent.py's client reads (300 s). The same URL and key as agent.py's; the key is never printed.
        ask_card: AskCard | None = None
        url = os.environ.get("SECONDBRAIN_MCP_URL")
        key = os.environ.get("SECONDBRAIN_MCP_KEY")
        if url and key:
            http = await stack.enter_async_context(
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {key}"}, timeout=httpx2.Timeout(30.0, read=CARD_WAIT_SECONDS))
            )
            ask_card = secondbrain_cards(await stack.enter_async_context(Client(streamable_http_client(url, http_client=http))))
        else:
            logger.warning("SECONDBRAIN_MCP_URL or SECONDBRAIN_MCP_KEY is not set: approval cards are left unanswered")
        async with agent:
            app = build_mcp_app(agent, ask_card)
            await uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="info")).serve()


if __name__ == "__main__":
    asyncio.run(main())
