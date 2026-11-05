"""Steward's workflow over AG-UI (step 1 of moving the Agent tab to AG-UI): MAF's AG-UI package as it ships.

The same workflow hosted.py serves over the Responses protocol (steward_workflow.build_steward, through
hosted.steward_graph, with the same middleware), here served as an AG-UI endpoint by MAF's ``agent_framework_ag_ui``:
``AgentFrameworkWorkflow`` turns the workflow's events into AG-UI events and ``add_agent_framework_fastapi_endpoint``
streams them as Server-Sent Events (Learn, "Workflows with AG-UI": "Wrapping a Workflow with AgentFrameworkWorkflow",
"Registering the Endpoint"). Nothing here writes SSE by hand.

What a client sees, as the Learn page's table has it: RUN_STARTED, STEP_STARTED/STEP_FINISHED per executor,
TEXT_MESSAGE_* for the workflow's output, REASONING_* for the steps whose words stream as intermediate output (ANSWER,
EXECUTE: WorkflowBuilder's intermediate_output_from), TOOL_CALL_* for his tool calls, and RUN_FINISHED. A card is
MAF's human-in-the-loop: the workflow's pending request (the plan's approve_plan, a write's function_approval_request)
comes as a TOOL_CALL named ``request_info`` and a CUSTOM ``request_info`` event, and the run ends with RUN_FINISHED
whose ``outcome`` is ``{"type": "interrupt", "interrupts": [{"id", "reason": "tool_call", "message", "toolCallId",
"metadata": {"agent_framework": {"function_call", "checkpoint_id"}}}]}``. The answer is a new run on the same
``threadId`` with ``resume: [{"interruptId", "status": "resolved", "payload": {"approved": true|false}}]`` and
``forwardedProps: {"checkpointId": <the interrupt's metadata.agent_framework.checkpoint_id>}`` (Learn, "Interrupt and
resume", "Persist and resume workflow checkpoints").

One Steward per request, as hosted.py builds him (MAF's native host refuses to share agents between requests, and his
SecondBrain connection and shell are opened and closed with each build): the package's own workflow_factory is
synchronous and caches a workflow per thread, so ``StewardAGUIWorkflow.run`` builds the graph for the request, enters
each of its agents as MAF's workflow host does (agent_framework_foundry_hosting workflow_agents), runs it through
``AgentFrameworkWorkflow``, and closes them when the stream ends. What lasts between requests (the pending card, each
step's session) is in the workflow's checkpoint, in this process's ``InMemoryCheckpointStorage``, so a card is
answered on the same running host (a restart drops it; hosted.py keeps its checkpoints on disk).

A turn whose forwardedProps carry ``{"steward_workflow": "improve"}`` runs the improvement loop, as hosted.py's
request metadata does.

Loopback only, unauthenticated, one user (``single_user=True``), off unless started. Jesster does not use it yet.

Environment variables:
    OLLAMA_HOST, OLLAMA_MODEL, STEWARD_WORKSPACE, SECONDBRAIN_MCP_* - see agent.py
    STEWARD_AG_UI_PORT - port to serve on (defaults to 43122)

Run:
    python harness/steward/step04_production_ready/ag_ui_app.py

Then point an AG-UI client (an HttpAgent) at http://127.0.0.1:43122/.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import AsyncExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import uvicorn
from ag_ui.core import BaseEvent
from agent_framework import CheckpointStorage, InMemoryCheckpointStorage
from agent_framework_ag_ui import AgentFrameworkWorkflow, add_agent_framework_fastapi_endpoint
from agent_framework_foundry_hosting._workflow_source import workflow_agents
from dotenv import load_dotenv
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hosted  # noqa: E402
from agent import warn_model_drift  # noqa: E402

logger = logging.getLogger(__name__)
HOST = "127.0.0.1"  # loopback only
PORT = 43122
PATH = "/"
NAME = "steward"


def _request_metadata(input_data: Mapping[str, Any]) -> dict[str, Any]:
    """The run's forwardedProps, read as hosted.py reads a Responses request's metadata (wants_improvement)."""
    props = input_data.get("forwarded_props") or input_data.get("forwardedProps")
    return dict(props) if isinstance(props, Mapping) else {}


class StewardAGUIWorkflow(AgentFrameworkWorkflow):
    """MAF's AG-UI workflow wrapper over a Steward built for each request (see the module docstring)."""

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        checkpoint_storage: CheckpointStorage | None = None,
        **build: Any,
    ) -> None:
        super().__init__(
            name=NAME,
            description="Steward's request workflow: route, answer or plan, approve, execute, check, report.",
            checkpoint_storage=checkpoint_storage or InMemoryCheckpointStorage(),
        )
        self._client_factory = client_factory
        self._build = build

    async def run(self, input_data: dict[str, Any]) -> AsyncGenerator[BaseEvent]:
        request = SimpleNamespace(request={"metadata": _request_metadata(input_data)})
        workflow = await hosted.steward_graph(request, self._client_factory, **dict(self._build))
        async with AsyncExitStack() as agents:
            for agent in workflow_agents(workflow):  # as MAF's workflow host enters them (_workflow_responses.py)
                await agents.enter_async_context(agent)
            runner = AgentFrameworkWorkflow(
                workflow=workflow, name=self.name, description=self.description, checkpoint_storage=self.checkpoint_storage
            )
            async for event in runner.run(input_data):
                yield event


def build_ag_ui_app(client_factory: Callable[[], Any] | None = None, **build: Any) -> FastAPI:
    """The AG-UI endpoint at PATH, on a FastAPI app (Learn's "Registering the Endpoint", single_user=True). The code
    each request builds is imported now (hosted.load_host_code), so a pull while the host runs is not mixed into it."""
    hosted.load_host_code()
    app = FastAPI(title="Steward (AG-UI)")
    add_agent_framework_fastapi_endpoint(
        app=app, agent=StewardAGUIWorkflow(client_factory, **build), path=PATH, single_user=True
    )
    return app


async def main() -> None:
    """Serve Steward over AG-UI on HOST:STEWARD_AG_UI_PORT until stopped."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = int(os.environ.get("STEWARD_AG_UI_PORT", str(PORT)))
    hosted.steward_observability()  # the same local telemetry as hosted.py: nothing of it on stdout
    await warn_model_drift()
    logger.info("Steward serving on http://%s:%d%s (AG-UI, MAF workflow).", HOST, port, PATH)
    await uvicorn.Server(uvicorn.Config(build_ag_ui_app(), host=HOST, port=port, log_level="info")).serve()


if __name__ == "__main__":
    asyncio.run(main())
