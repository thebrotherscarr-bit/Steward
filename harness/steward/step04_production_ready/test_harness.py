"""Model-free checks of Steward's harness (ADR-0001).

They follow Microsoft's builder skill on validating a harness (references/harness-agent-builder.md):
"Exercise enabled modes, memory, skills, and file roots rather than testing factory construction
alone. Verify approval behavior for side effects. Prove loop termination."

No model and no network. A scripted chat client, composed like MAF's own MockBaseChatClient
(python/packages/core/tests/core/conftest.py), stands in for Ollama, so each check takes seconds,
on this PC or on GitHub's runners (the gate). Small checks instead of model-run evals, as MAF's
LocalEvaluator guidance has it: "ideal for ... CI smoke tests".

Run:
    python -m pytest harness/steward/step04_production_ready/test_harness.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterable, Awaitable, Mapping, Sequence
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)
from agent_framework.observability import ChatTelemetryLayer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent as steward  # noqa: E402

# Hermetic: no SecondBrain connection (and so no Atlas door), whatever agent.py's load_dotenv() found.
for _name in ("SECONDBRAIN_MCP_URL", "SECONDBRAIN_MCP_KEY"):
    os.environ.pop(_name, None)

SKILLS = ("agent-framework-builder-python", "code-review", "codebase-map")


class ScriptedChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer, BaseChatClient):
    """MAF's MockBaseChatClient composition, replying from a script: text, or one function call."""

    def __init__(self, replies: list[Any] | None = None) -> None:
        super().__init__(middleware=[])
        self.replies = list(replies or [])
        self.calls: list[dict[str, Any]] = []

    def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool = False, options: Mapping[str, Any], **kwargs: Any
    ) -> Awaitable[ChatResponse] | ResponseStream[ChatResponseUpdate, ChatResponse]:
        self.calls.append({"messages": list(messages), "options": dict(options)})
        reply = self.replies.pop(0) if self.replies else "done"
        content = reply if isinstance(reply, Content) else Content.from_text(reply)
        if stream:
            # As MockBaseChatClient._get_streaming_response: the reply as one update, finalized from updates.
            async def _stream() -> AsyncIterable[ChatResponseUpdate]:
                yield ChatResponseUpdate(contents=[content], role="assistant", finish_reason="stop")

            return ResponseStream(_stream(), finalizer=lambda updates: ChatResponse.from_updates(updates))

        async def _get() -> ChatResponse:
            return ChatResponse(messages=Message(role="assistant", contents=[content]))

        return _get()


def run_steward(replies: list[Any], query: str, *, unattended: bool = False) -> tuple[ScriptedChatClient, Any, Any]:
    """One turn of Steward (Part 4, shell off) on the scripted client, in its own session.

    ``unattended`` is the evals' switch (auto_approve_skill_scripts): reads and skill scripts run without
    approval, as in MAF's claw evals.
    """

    async def _go() -> tuple[ScriptedChatClient, Any, Any]:
        client = ScriptedChatClient(replies)
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(
                stack, client=client, enable_shell=False, auto_approve_skill_scripts=unattended
            )
            async with agent:
                response = await agent.run(query, session=agent.create_session())
        return client, agent, response

    return asyncio.run(_go())


def offered_tools(call: dict[str, Any]) -> set[str]:
    return {getattr(tool, "name", "") for tool in call["options"].get("tools") or []}


def approval_requests(response: Any) -> list[Any]:
    return [c for m in response.messages for c in m.contents if c.type == "function_approval_request"]


def test_modes_memory_skills_and_file_roots_are_offered() -> None:
    client, agent, _ = run_steward(["Hello."], "Hello")
    call = client.calls[0]
    assert {"mode_get", "mode_set", "todos_add", "todos_complete"} <= offered_tools(call)  # modes, todos
    assert {"file_memory_read", "file_memory_write"} <= offered_tools(call)  # memory
    assert {"load_skill", "read_skill_resource"} <= offered_tools(call)  # skills
    assert {"file_access_read", "file_access_write"} <= offered_tools(call)  # file access
    instructions = str(call["options"].get("instructions") or "")
    assert all(skill in instructions for skill in SKILLS), "every file skill is advertised"
    assert not {t for t in offered_tools(call) if t.startswith("atlas")}, "no door without SecondBrain (ADR-0001 item 5)"
    file_access = next(p for p in agent.context_providers if type(p).__name__ == "FileAccessProvider")
    assert Path(file_access.store.root_path).resolve() == steward._WORKING_DIR  # the file root


def test_git_commit_waits_for_approval() -> None:
    commit = Content.from_function_call(call_id="c1", name="git_commit", arguments={"message": "Test commit"})
    client, _, response = run_steward([commit], "Commit the work.")
    requests = approval_requests(response)
    assert [r.function_call.name for r in requests] == ["git_commit"]
    assert len(client.calls) == 1, "nothing ran before the approval"


def test_file_write_waits_for_approval() -> None:
    write = Content.from_function_call(
        call_id="w1", name="file_access_write", arguments={"file_name": "test_harness_probe.txt", "content": "x"}
    )
    client, _, response = run_steward([write], "Write a file.")
    assert [r.function_call.name for r in approval_requests(response)] == ["file_access_write"]
    assert not (steward._WORKING_DIR / "test_harness_probe.txt").exists()
    assert len(client.calls) == 1


INVENTORY = "harness/steward/working/sample-project/inventory.py"


def test_file_read_waits_for_approval_when_attended() -> None:
    # ADR-0001 item 11: the file root is the repo, whose root holds .env, so reads park for approval.
    read = Content.from_function_call(call_id="r1", name="file_access_read", arguments={"file_name": INVENTORY})
    client, _, response = run_steward([read], "Read inventory.py.")
    assert [r.function_call.name for r in approval_requests(response)] == ["file_access_read"]
    assert len(client.calls) == 1


def test_file_read_runs_without_approval_when_unattended() -> None:
    read = Content.from_function_call(call_id="r1", name="file_access_read", arguments={"file_name": INVENTORY})
    client, _, response = run_steward([read, "It defines order_total."], "Read inventory.py.", unattended=True)
    assert not approval_requests(response)
    assert len(client.calls) == 2, "the read ran and the model was called again"
    results = [str(c.result) for m in client.calls[1]["messages"] for c in m.contents if c.type == "function_result"]
    assert any("def order_total" in r for r in results)


def test_loop_stops_at_its_bound() -> None:
    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Never finished"}]})
    client, _, response = run_steward([todo], "Work through the plan.")
    # One open todo in execute mode keeps the harness loop going (todos_remaining) until its bound of
    # ten runs: the first run makes two model calls (the todos_add call, then the reply), the rest one each.
    assert len(client.calls) == 2 + 9
    assert any("Never finished" in m.text for m in client.calls[2]["messages"]), "the loop reminds him of the open todo"


def test_door_calls_stay_on_stewards_world() -> None:
    """steward_world_only, MAF's middleware gating: a door call on another world, or none, never reaches the door."""
    from types import SimpleNamespace

    def gate(name: str, arguments: dict[str, Any]) -> tuple[Any, bool]:
        reached: list[bool] = []

        async def call_next() -> None:
            reached.append(True)

        context = SimpleNamespace(function=SimpleNamespace(name=name), arguments=arguments, result=None)
        asyncio.run(steward.steward_world_only(context, call_next))
        return context.result, bool(reached)

    result, reached = gate("atlas_git_commit", {"project": "research", "message": "x"})
    assert not reached and 'project="steward"' in result
    result, reached = gate("atlas_git_commit", {"message": "x"})
    assert not reached, "no project means the door's default world, which is refused"
    assert gate("atlas_git", {"project": "steward"}) == (None, True)
    assert gate("git_commit", {"message": "x"}) == (None, True), "Steward's own tools are untouched"


def test_devui_shows_stewards_runs_and_traces() -> None:
    """ADR-0001 item 7: DevUI, run as devui_app.py runs it, serves Steward and streams his run's trace."""
    from agent_framework.observability import configure_otel_providers
    from fastapi.testclient import TestClient

    import devui_app

    configure_otel_providers(enable_sensitive_data=True)
    stack = AsyncExitStack()
    client = ScriptedChatClient(["Hello from Steward."])
    agent = asyncio.run(steward.build_steward_agent(stack, client=client, enable_shell=False))
    server = devui_app.build_dev_server(agent, "test-token")
    # DevUI answers only requests addressed to its loopback host.
    with TestClient(server.get_app(), base_url=f"http://{devui_app.HOST}:{devui_app.PORT}") as http:
        auth = {"Authorization": "Bearer test-token"}
        assert http.get("/v1/entities").status_code == 401, "DevUI asks for its token"
        entities = http.get("/v1/entities", headers=auth).json()["entities"]
        assert [e["name"] for e in entities] == ["Steward"]
        entity = entities[0]["id"]
        # The UI runs each chat in a conversation, which carries the session the harness needs.
        conversation = http.post("/v1/conversations", json={"metadata": {"entity_id": entity}}, headers=auth).json()
        body = {"metadata": {"entity_id": entity}, "input": "Hello", "stream": True, "conversation": conversation["id"]}
        events = http.post("/v1/responses", json=body, headers=auth).text
    asyncio.run(stack.aclose())
    assert "Hello from Steward." in events, "the run's reply reaches DevUI"
    assert "response.trace.completed" in events and "invoke_agent Steward" in events, "and so does its trace"


def test_mcp_hosting_serves_steward_as_one_tool() -> None:
    """ADR-0001 item 10: mcp_app.py serves Steward as one MCP tool; a reused session_id continues his conversation."""
    from agent_framework import InMemoryHistoryProvider
    from starlette.testclient import TestClient

    import mcp_app

    stack = AsyncExitStack()
    client = ScriptedChatClient(["First answer.", "Second answer."])
    agent = asyncio.run(
        steward.build_steward_agent(stack, client=client, enable_shell=False, history_provider=InMemoryHistoryProvider())
    )
    headers = {"Accept": "application/json, text/event-stream"}

    def rpc(http: TestClient, method: str, params: dict[str, Any]) -> dict[str, Any]:
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return http.post("/mcp", json=body, headers=headers).json()["result"]

    with TestClient(mcp_app.build_mcp_app(agent), base_url=f"http://{mcp_app.HOST}:{mcp_app.PORT}") as http:
        tools = rpc(http, "tools/list", {})["tools"]
        assert [(t["name"], t["inputSchema"]["required"]) for t in tools] == [("Steward", ["task", "session_id"])]
        call = {"name": "Steward", "arguments": {"task": "Hello", "session_id": "s1"}}
        first = rpc(http, "tools/call", call)
        call["arguments"]["task"] = "And again"
        second = rpc(http, "tools/call", call)
    asyncio.run(stack.aclose())
    assert [b["text"] for b in first["content"]] == ["First answer."]
    assert [b["text"] for b in second["content"]] == ["Second answer."]
    assert any("Hello" in m.text for m in client.calls[1]["messages"]), "the second call continues the first's session"
