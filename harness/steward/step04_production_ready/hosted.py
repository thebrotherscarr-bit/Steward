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
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from agent_framework import (
    AgentContext,
    AgentResponseUpdate,
    BackgroundAgentsProvider,
    InMemoryHistoryProvider,
    ResponseStream,
    agent_middleware,
)
from agent_framework_foundry_hosting import ResponsesHostServer
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import build_steward_agent  # noqa: E402
from halo_traces import setup_halo_tracing  # noqa: E402

logger = logging.getLogger(__name__)


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


async def main() -> None:
    """Serve Steward on 127.0.0.1:STEWARD_PORT until stopped."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = int(os.environ.get("STEWARD_PORT", "43120"))
    # Every span goes to halo_traces/traces.jsonl (cookbook improvement loop, step 2).
    setup_halo_tracing()

    async with AsyncExitStack() as stack:
        # Steward keeps each conversation's history in its session (history_source="agent"), so an
        # approval answer comes back through the harness's approval layer instead of being replayed
        # to Ollama as history, which the Ollama client cannot read.
        agent = await build_steward_agent(stack, history_provider=InMemoryHistoryProvider())
        background_providers = [
            provider for provider in agent.context_providers if isinstance(provider, BackgroundAgentsProvider)
        ]
        agent.middleware = [_release_background_per_request(background_providers), *(agent.middleware or [])]
        async with agent:
            logger.info("Steward serving on http://127.0.0.1:%d (Responses protocol).", port)
            server = ResponsesHostServer(agent=agent, history_source="agent")
            await server.run_async(host="127.0.0.1", port=port)


if __name__ == "__main__":
    asyncio.run(main())
