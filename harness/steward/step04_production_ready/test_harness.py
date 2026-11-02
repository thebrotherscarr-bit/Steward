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
        self.calls.append({"messages": list(messages), "options": dict(options), "kwargs": dict(kwargs)})
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


def run_steward(
    replies: list[Any], query: str, *, unattended: bool = False, mode: str | None = None
) -> tuple[ScriptedChatClient, Any, Any]:
    """One turn of Steward (Part 4, shell off) on the scripted client, in its own session.

    ``unattended`` is the evals' switch (auto_approve_skill_scripts): reads and skill scripts run without
    approval, as in MAF's claw evals. ``mode`` puts the session in that mode first, as the user's Approve does.
    """
    from agent_framework import AgentModeProvider, set_agent_mode

    async def _go() -> tuple[ScriptedChatClient, Any, Any]:
        client = ScriptedChatClient(replies)
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(
                stack, client=client, enable_shell=False, auto_approve_skill_scripts=unattended
            )
            async with agent:
                session = agent.create_session()
                if mode:
                    provider = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                    set_agent_mode(session, mode, source_id=provider.source_id, available_modes=provider.available_modes)
                response = await agent.run(query, session=session)
        return client, agent, response

    return asyncio.run(_go())


def offered_tools(call: dict[str, Any]) -> set[str]:
    return {getattr(tool, "name", "") for tool in call["options"].get("tools") or []}


def approval_requests(response: Any) -> list[Any]:
    return [c for m in response.messages for c in m.contents if c.type == "function_approval_request"]


def test_modes_memory_skills_and_file_roots_are_offered() -> None:
    # In execute mode, where every tool is offered (plan mode offers only what changes nothing: the gate's check).
    client, agent, _ = run_steward(["Hello."], "Hello", mode="execute")
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
    # In execute mode (after the user's Approve); in plan mode the gate refuses it before any card.
    client, _, response = run_steward([commit], "Commit the work.", mode="execute")
    requests = approval_requests(response)
    assert [r.function_call.name for r in requests] == ["git_commit"]
    assert len(client.calls) == 1, "nothing ran before the approval"


def test_file_write_waits_for_approval() -> None:
    write = Content.from_function_call(
        call_id="w1", name="file_access_write", arguments={"file_name": "test_harness_probe.txt", "content": "x"}
    )
    client, _, response = run_steward([write], "Write a file.", mode="execute")
    assert [r.function_call.name for r in approval_requests(response)] == ["file_access_write"]
    assert not (steward._WORKING_DIR / "test_harness_probe.txt").exists()
    assert len(client.calls) == 1


INVENTORY = "harness/steward/working/sample-project/inventory.py"


def function_results(call: dict[str, Any]) -> list[str]:
    return [str(c.result) for m in call["messages"] for c in m.contents if c.type == "function_result"]


def test_file_read_runs_without_approval_when_attended() -> None:
    # plan-steward-context-memory-reads, piece 1 (supersedes ADR-0001 item 11's card per read): reads run.
    read = Content.from_function_call(call_id="r1", name="file_access_read", arguments={"file_name": INVENTORY})
    client, _, response = run_steward([read, "It defines order_total."], "Read inventory.py.")
    assert not approval_requests(response)
    assert any("def order_total" in r for r in function_results(client.calls[1]))


def test_env_is_never_read_searched_or_listed(tmp_path: Path) -> None:
    """Piece 1: the store keeps .env out, so a read that runs without a card never reaches a key."""
    (tmp_path / ".env").write_text("SECONDBRAIN_MCP_KEY=planted-secret\n")
    (tmp_path / "a.txt").write_text("hello\n")
    store = steward.LineEndingFileStore(str(tmp_path))

    async def _go() -> tuple[bool, list[Any], list[str]]:
        try:
            await store.read(".env")
            refused = False
        except ValueError:
            refused = True
        hits = await store.search("", "planted-secret", recursive=True)
        return refused, hits, [e.name for e in await store.list_children("")]

    refused, hits, names = asyncio.run(_go())
    assert refused and not hits and names == ["a.txt"]
    # Through Steward's own tool, in an attended run: no card, and no key.
    read = Content.from_function_call(call_id="r1", name="file_access_read", arguments={"file_name": ".env"})
    client, _, response = run_steward([read, "Refused."], "Read .env.")
    assert not approval_requests(response)
    assert any("never read" in r for r in function_results(client.calls[1]))


def test_charter_and_notes_reach_him_every_turn(monkeypatch: Any) -> None:
    """Piece 2: with SecondBrain up, his notes are offered and the Charter is in his instructions."""
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("secondbrain")

    @server.tool()
    def read_note(id: str) -> str:
        return "CHARTER: what we are building, what binds you." if id == "steward-charter" else f"no note {id}"

    @server.tool()
    def search_notes(query: str) -> str:
        return "[]"

    @server.tool()
    def list_notes() -> str:
        return "[]"

    # SecondBrain in process: the MCP SDK's Client connects to a server object without a network.
    monkeypatch.setenv("SECONDBRAIN_MCP_URL", "http://127.0.0.1:43110/mcp")
    monkeypatch.setenv("SECONDBRAIN_MCP_KEY", "test-key")
    monkeypatch.setattr(steward, "streamable_http_client", lambda url, http_client=None: server)
    client, _, _ = run_steward(["Hello."], "Hello")
    call = client.calls[0]
    assert {"secondbrain_search_notes", "secondbrain_read_note", "secondbrain_list_notes"} <= offered_tools(call)
    assert "CHARTER: what we are building" in str(call["options"].get("instructions") or "")


def test_memory_lasts_between_sessions(tmp_path: Path) -> None:
    """Piece 3: a memory saved in one session is in front of him in the next."""
    from agent_framework import FileSystemAgentFileStore

    write = Content.from_function_call(
        call_id="m1",
        name="file_memory_write",
        arguments={"file_name": "lesson.md", "content": "Run test_harness.py after every change.", "description": "the check to run"},
    )

    async def _go() -> ScriptedChatClient:
        client = ScriptedChatClient([write, "Saved.", "Hello again."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(
                stack, client=client, enable_shell=False, file_memory_store=FileSystemAgentFileStore(tmp_path)
            )
            async with agent:
                await agent.run("Remember this.", session=agent.create_session())
                await agent.run("Hello", session=agent.create_session())
        return client

    client = asyncio.run(_go())
    later = client.calls[2]
    seen = str(later["options"].get("instructions") or "") + " ".join(m.text for m in later["messages"])
    assert "lesson.md" in seen, "the new session is shown the memory saved in the first"


def test_file_read_runs_without_approval_when_unattended() -> None:
    read = Content.from_function_call(call_id="r1", name="file_access_read", arguments={"file_name": INVENTORY})
    client, _, response = run_steward([read, "It defines order_total."], "Read inventory.py.", unattended=True)
    assert not approval_requests(response)
    assert len(client.calls) == 2, "the read ran and the model was called again"
    results = [str(c.result) for m in client.calls[1]["messages"] for c in m.contents if c.type == "function_result"]
    assert any("def order_total" in r for r in results)


def test_a_new_session_starts_in_plan_mode() -> None:
    """Every session starts in MAF's plan mode: he works out what he has and asks before he acts."""
    client, _, _ = run_steward(["Hello."], "Hello")
    instructions = str(client.calls[0]["options"].get("instructions") or "")
    assert "You are currently operating in the plan mode." in instructions


def test_every_task_gets_todos_and_no_simple_task_skips_the_plan() -> None:
    """The todo list at all times: MAF's "if simple, just complete the task directly" is replaced, the rest of its text kept."""
    client, _, _ = run_steward(["Hello."], "Hello")
    instructions = str(client.calls[0]["options"].get("instructions") or "")
    assert "There is no simple task" in instructions and "load_skill and add the skill's steps" in instructions
    assert "just complete the task directly" not in instructions
    assert "Use todos_complete to mark items as done" in instructions, "MAF's own todo guidance stays"


def test_the_agent_tab_plans_then_executes_on_approve() -> None:
    """Part 1's plan mode on the hosted path (hosted.py): a plan-mode turn asks for PlanningResponse; Approve switches to execute."""
    from agent_framework import AgentModeProvider

    import hosted
    from console.observers.planning_models import PlanningResponse

    plan = '{"type": "approval", "questions": [{"message": "1. Read the note. 2. Report."}]}'

    async def _go() -> ScriptedChatClient:
        client = ScriptedChatClient([plan, "Done."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            mode_provider = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
            agent.middleware = [hosted.plan_mode_turns(mode_provider), *(agent.middleware or [])]
            async with agent:
                session = agent.create_session()
                await agent.run("Read the ADR note and report.", session=session)
                approve = {"metadata": {hosted.AGENT_MODE_KEY: "execute"}}
                await agent.run("Approve and switch to execute mode", session=session, options=approve)
        return client

    client = asyncio.run(_go())
    planned, approved = client.calls[0]["options"], client.calls[1]["options"]
    assert planned.get("response_format") is PlanningResponse, "plan mode asks for the console's PlanningResponse"
    assert "operating in the plan mode" in str(planned.get("instructions") or "")
    assert "operating in the execute mode" in str(approved.get("instructions") or ""), "Approve switched the session"
    assert approved.get("response_format") is None and "metadata" not in approved, "and the switch never reaches the model"


def test_finished_todos_return_him_to_plan_mode() -> None:
    """After an execute run leaves no todo open, the next request is planned again (ReturnToPlanWhenDone)."""
    from agent_framework import AgentModeProvider, set_agent_mode

    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Write the file"}]})
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "Written."}]})

    async def _go() -> ScriptedChatClient:
        client = ScriptedChatClient([todo, done, "Done.", "Hello."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            async with agent:
                session = agent.create_session()
                provider = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                set_agent_mode(session, "execute", source_id=provider.source_id, available_modes=provider.available_modes)
                await agent.run("Work through the plan.", session=session)
                await agent.run("Hello", session=session)
        return client

    client = asyncio.run(_go())
    assert "operating in the execute mode" in str(client.calls[0]["options"].get("instructions") or "")
    assert "operating in the plan mode" in str(client.calls[3]["options"].get("instructions") or ""), "todos done: plan"


def test_loop_stops_at_its_bound() -> None:
    # Sessions start in plan mode, which stays interactive; the loop runs in execute mode, which the user's
    # Approve puts the session in (set_agent_mode, from the console or hosted.py).
    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Never finished"}]})
    client, _, response = run_steward([todo], "Work through the plan.", mode="execute")
    # One open todo in execute mode keeps the harness loop going (todos_remaining) until its bound of
    # ten runs: the first run makes two model calls (todos_add, then the reply), the rest one each.
    assert len(client.calls) == 2 + 9
    assert any("Never finished" in m.text for m in client.calls[2]["messages"]), "the loop reminds him of the open todo"


def test_plan_mode_states_the_tool_policy_and_every_tool_stays_offered() -> None:
    """The cookbook's way: the tools stay offered (their approvals are the gate) and plan mode states the policy."""
    client, _, _ = run_steward(["Here is the plan."], "Do it.")
    offered, instructions = offered_tools(client.calls[0]), str(client.calls[0]["options"].get("instructions") or "")
    assert steward._CHANGES_THINGS - {"run_shell", "atlas_git_branch", "atlas_git_commit", "atlas_git_push", "atlas_git_pr"} <= offered
    assert {"todos_add", "mode_set"} <= offered
    assert steward.PLAN_MODE_TOOL_POLICY in instructions and "file_access_write" in steward.PLAN_MODE_TOOL_POLICY
    # The plan-mode gate: a write called in plan mode is refused with corrective feedback, with no card.
    write = Content.from_function_call(
        call_id="w1", name="file_access_write", arguments={"file_name": "test_harness_gate_probe.txt", "content": "x"}
    )
    client, _, response = run_steward([write, "Here is the plan."], "Do it.")
    assert not approval_requests(response), "no card in plan mode: the gate refuses instead"
    assert any("Refused: you are in plan mode" in r for r in function_results(client.calls[1]))
    assert not (steward._WORKING_DIR / "test_harness_gate_probe.txt").exists()
    # After Approve (execute mode), the same write goes to its own approval card, as before.
    client, _, response = run_steward([write], "Do it.", mode="execute")
    assert [r.function_call.name for r in approval_requests(response)] == ["file_access_write"]
    assert not (steward._WORKING_DIR / "test_harness_gate_probe.txt").exists()
    # MAF lists every mode's text each turn, the policy under plan; in execute mode he is told he is executing.
    client, _, _ = run_steward(["Done."], "Do it.", mode="execute")
    assert "operating in the execute mode" in str(client.calls[0]["options"].get("instructions") or "")


def test_plan_mode_marks_no_todo_done_and_the_plan_is_read_in_code() -> None:
    """Gate run 5: in plan mode a todo cannot be marked done (nothing has run); the plan JSON is read in code."""
    import hosted

    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Write it"}]})
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "x"}]})
    client, _, _ = run_steward([todo, done, "Plan."], "Do it.")
    assert any(r.startswith("Refused: you are in plan mode and nothing has been done") for r in function_results(client.calls[2]))
    prefixed = 'We added the todo. Now present the plan.{"type": "approval", "questions": [{"message": "1. Write it."}]}'
    assert hosted.planning_response_in(prefixed).questions[0].message == "1. Write it."
    assert hosted.planning_response_in("plain words") is None
    assert hosted.planning_response_in('{"type": "approval", "questions": []}') is None, "an empty plan is no plan"


def test_a_plan_mode_reply_without_todos_or_plan_is_asked_again() -> None:
    """For a host that asks for PlanningResponse: no todos, then a prose reply, each get one more ask (the harness loop)."""
    import hosted

    plan = '{"type": "approval", "questions": [{"message": "1. Write it."}]}'
    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Write it"}]})

    async def _go(replies: list[Any], check: Any) -> ScriptedChatClient:
        client = ScriptedChatClient(replies)
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False, plan_reply_check=check)
            async with agent:
                await agent.run("Write it.", session=agent.create_session())
        return client

    # A plan with no todos: asked to add the todos first.
    client = asyncio.run(_go([plan, todo, plan], hosted.planning_response_in))
    assert len(client.calls) == 3 and any(steward.PLAN_TODOS_NUDGE in m.text for m in client.calls[1]["messages"])
    # Todos, then prose: asked for the plan.
    client = asyncio.run(_go([todo, "Here is my plan in prose.", plan], hosted.planning_response_in))
    assert len(client.calls) == 3 and any(steward.PLAN_REPLY_NUDGE in m.text for m in client.calls[2]["messages"])
    assert len(asyncio.run(_go(["Prose."], None)).calls) == 1, "a host that does not ask for the plan is not looped"


def test_finished_work_is_not_asked_for_a_plan() -> None:
    """Live test 2026-11-01: an execute run that finishes its todos returns to plan mode, and is not then asked for a plan."""
    from agent_framework import AgentModeProvider, set_agent_mode

    import hosted

    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Write it"}]})
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "Written."}]})

    async def _go() -> ScriptedChatClient:
        client = ScriptedChatClient([todo, done, "Done: the file is written."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(
                stack, client=client, enable_shell=False, plan_reply_check=hosted.planning_response_in
            )
            async with agent:
                session = agent.create_session()
                modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
                await agent.run("Work through the plan.", session=session)
        return client

    client = asyncio.run(_go())
    assert len(client.calls) == 3, "no plan was asked of the finished run"
    assert not any(steward.PLAN_REPLY_NUDGE in m.text for c in client.calls for m in c["messages"])


def test_a_request_that_matches_a_skill_or_helper_gets_one_line_naming_it() -> None:
    """RequestHints: the fast path adds task-specific guidance only when the request asks for it."""

    def hints_for(query: str) -> str:
        client, _, _ = run_steward(["ok"], query, mode="execute")
        text = str(client.calls[0]["options"].get("instructions") or "")
        return text.split("## For this request", 1)[1] if "## For this request" in text else ""

    assert 'load_skill("codebase-map")' in hints_for("Map harness/steward/working/sample-project.")
    assert "WebResearchAgent" in hints_for("Research Ollama and mem0 and summarize the latest news.")
    assert "execute_code" in hints_for("What percentage of the lines are tests?")
    assert "CodeExplorer" in hints_for("Explore it with the CodeExplorer agent.")
    assert hints_for("Hello, how are you?") == "", "nothing is added when nothing matches"
    assert hints_for("Fix the import in C:/Users/novad/Desktop/Research/worlds/x.py.") == "", "a word inside a path never counts"


def test_a_clearly_misspelled_tool_name_is_repaired_and_an_unclear_one_is_not() -> None:
    """repair_tool_names: "totos_add" (his most common slip) runs todos_add, streamed or not; an unknown name stays unknown."""
    slip = Content.from_function_call(call_id="t1", name="totos_add", arguments={"todos": [{"title": "Write it"}]})
    client, _, _ = run_steward([slip, "Planned."], "Plan it.")
    assert any('"title": "Write it"' in r for r in function_results(client.calls[1])), "the todo was made"

    async def _streamed() -> ScriptedChatClient:
        c = ScriptedChatClient([slip, "Planned."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=c, enable_shell=False)
            async with agent:
                await agent.run("Plan it.", session=agent.create_session(), stream=True).get_final_response()
        return c

    assert any('"title": "Write it"' in r for r in function_results(asyncio.run(_streamed()).calls[1])), "streamed too"
    unknown = Content.from_function_call(call_id="u1", name="unknown_tool", arguments={})
    client, _, _ = run_steward([unknown, "Ok."], "Do it.")
    assert any("not found" in r for r in function_results(client.calls[1]))
    assert steward.repaired_tool_name("file_acess_read", {"file_access_read", "file_access_write"}) == "file_access_read"
    assert steward.repaired_tool_name("mod_x", {"mode_set", "mode_get"}) is None


def test_work_that_skips_the_tool_its_request_needs_is_asked_once_and_hints_outlive_the_approve() -> None:
    """The evidence check: a count finished without CodeAct is asked once; a hint is kept through the Approve turn."""
    from agent_framework import AgentModeProvider, set_agent_mode

    count = Content.from_function_call(call_id="x1", name="execute_code", arguments={"code": "print(round(100 * 24 / 44, 1))"})
    question = "What percentage of the lines are tests?"
    client, _, _ = run_steward(["About half.", count, "54.5%"], question, mode="execute")
    assert len(client.calls) == 3, "one nudge, then the count, then the answer"
    assert any(steward.REQUIRED_TOOLS_NUDGE in m.text and "execute_code" in m.text for m in client.calls[1]["messages"])
    client, _, _ = run_steward([count, "54.5%"], question, mode="execute")
    assert len(client.calls) == 2, "no nudge when the tool was used"

    async def _approve() -> ScriptedChatClient:
        c = ScriptedChatClient(["Plan: research it.", "Done."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=c, enable_shell=False)
            async with agent:
                session = agent.create_session()
                await agent.run("Research Ollama and summarize the latest news.", session=session)
                modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
                await agent.run("Approve and switch to execute mode", session=session)
        return c

    c = asyncio.run(_approve())
    assert "WebResearchAgent" in str(c.calls[1]["options"].get("instructions") or ""), "the hint reaches the Approve turn"


def test_only_the_users_approve_leaves_plan_mode() -> None:
    """Regression run 10: in plan mode his own mode_set("execute") is refused; only the user's Approve switches him."""
    switch = Content.from_function_call(call_id="s1", name="mode_set", arguments={"mode": "execute"})
    client, _, _ = run_steward([switch, "Here is the plan."], "Do it.")
    assert any(r == steward.PLAN_MODE_SWITCH_REFUSAL for r in function_results(client.calls[1]))
    assert "operating in the plan mode" in str(client.calls[1]["options"].get("instructions") or ""), "still in plan mode"
    assert "do not call mode_set for it" in str(client.calls[0]["options"].get("instructions") or ""), "step 7 says so"
    back = Content.from_function_call(call_id="s2", name="mode_set", arguments={"mode": "plan"})
    client, _, _ = run_steward([back, "Back to planning."], "Plan it again.", mode="execute")
    assert not any("Refused" in r for r in function_results(client.calls[1])), "switching to plan is always allowed"


def test_codeact_reads_harness_read_only_and_a_pass_count_is_not_a_count_question() -> None:
    """Regression run 11: CodeAct counts files through a read-only mount; "report the pass count" asks for no count."""
    count = Content.from_function_call(call_id="x1", name="execute_code", arguments={"code": (
        "print(len(open('harness/steward/working/sample-project/inventory.py').read().splitlines()))")})
    write = Content.from_function_call(call_id="x2", name="execute_code", arguments={"code": (
        "open('harness/test_harness_codeact_probe.txt', 'w').write('x')")})
    client, _, _ = run_steward([count, write, "ok"], "Count the lines.", mode="execute")
    lines = len((steward._WORKING_DIR / "harness/steward/working/sample-project/inventory.py").read_text(encoding="utf-8").splitlines())
    assert function_results(client.calls[1])[0].strip() == str(lines), "an exact count, read from the file"
    assert not (steward._WORKING_DIR / "harness" / "test_harness_codeact_probe.txt").exists(), "and nothing written"
    asked = [hint for pattern, hint, _ in steward.REQUEST_HINTS if pattern.search("Report the pass count and every failing line.")]
    assert asked == []


def test_a_run_that_added_todos_is_never_told_its_list_is_empty(monkeypatch: Any) -> None:
    """Live run 14: even if the store reads empty, a run that called todos_add is not nudged to add todos."""
    from agent_framework._harness._todo import TodoSessionStore

    import hosted

    async def empty(self: Any, session: Any, *, source_id: str) -> list[Any]:
        return []

    monkeypatch.setattr(TodoSessionStore, "load_items", empty)
    todo = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": "Write it"}]})
    plan = '{"type": "approval", "questions": [{"message": "1. Write it."}]}'

    async def _go() -> ScriptedChatClient:
        client = ScriptedChatClient([todo, plan, plan])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False, plan_reply_check=hosted.planning_response_in)
            async with agent:
                await agent.run("Write it.", session=agent.create_session())
        return client

    client = asyncio.run(_go())
    assert len(client.calls) == 2, "the plan stood; no false 'empty' nudge"


def scored(check: Any, query: str, conversation: list[Any]) -> Any:
    """One evals.py check on one conversation, as MAF's LocalEvaluator runs it (EvalItem, the full split)."""
    from agent_framework import ConversationSplit, EvalItem

    item = EvalItem([Message(role="user", contents=[Content.from_text(query)]), *conversation], split_strategy=ConversationSplit.FULL)
    return asyncio.run(check(item))


def test_a_plan_that_does_not_name_the_work_fails_the_plan_eval() -> None:
    """Run 15: a bug-fix plan that planned a new inventory.py passed; the plan must name the discount line's file and fix."""
    import evals

    query = evals.PLAN_BEFORE_ACT_QUERIES[1]

    def run(todo: str, plan: str) -> bool:
        add = Content.from_function_call(call_id="t1", name="todos_add", arguments={"todos": [{"title": todo}]})
        reply = '{"type": "approval", "questions": [{"message": "%s"}]}' % plan
        conversation = [Message(role="assistant", contents=[add]), Message(role="assistant", contents=[Content.from_text(reply)])]
        return scored(evals.plan_before_act, query, conversation).passed

    assert run("Add inventory.py re-exporting the functions", "Add a new file.") is False
    assert run("Fix the discount in inventory.py", "Divide discount_percent by 100.") is True


def test_the_walkthrough_denies_a_commit_card_and_nothing_is_committed() -> None:
    """The walkthrough's commit step: the card is answered Deny, so git_commit never runs and HEAD stays."""
    import evals

    commit = Content.from_function_call(call_id="c1", name="git_commit", arguments={"message": "checkpoint"})
    client = ScriptedChatClient([commit, "The commit was not approved."])

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            async with agent:
                from agent_framework import AgentModeProvider, set_agent_mode

                modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                session = agent.create_session()
                set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
                return await evals._run_answering_cards(agent, session, evals.WALKTHROUGH_COMMIT, set())

    head = evals._head()
    evals.WALKTHROUGH_HEAD[0] = head
    response = asyncio.run(_go())
    conversation = list(response.messages)
    assert evals._cards(conversation) == ["git_commit"], "the commit asked for approval"
    assert evals._head() == head, "the denied commit did not run"
    assert len(client.calls) == 2, "the run continued after the Deny"
    result = scored(evals.walkthrough, evals.WALKTHROUGH_COMMIT, conversation)
    assert result.passed, result.reason


def test_the_workflow_plans_waits_for_approval_and_only_then_executes_the_plans_steps_as_todos() -> None:
    """Pieces 1 and 2 of the workflow: PLAN asks for StewardPlan and the run pauses on an approve_plan card before
    anything runs. Approved, EXECUTE's own session goes to execute mode with the plan's steps as its todos (no
    todos_add from him) and runs until they are done; denied, nothing runs. A reply that is no plan ends the run."""
    import steward_workflow as wf
    from agent_framework import AgentModeProvider, TodoProvider, get_agent_mode

    plan = '{"type": "approval", "questions": [{"message": "Fix the discount."}], "steps": ["Read inventory.py", "Fix the discount line"]}'

    def run(replies: list[Any], approve: bool | None) -> dict[str, Any]:
        client = ScriptedChatClient(replies)

        async def _go() -> dict[str, Any]:
            async with AsyncExitStack() as stack:
                agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
                async with agent:
                    workflow = wf.build_steward_workflow(agent)
                    todos = next(p for p in agent.context_providers if isinstance(p, TodoProvider))
                    modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                    # Streamed, as the host runs it: MAF's loop parses a non-streamed structured reply strictly
                    # (_harness/_loop.py, _aggregate_response -> value), so a reply that is not pure JSON raises.
                    events = [e async for e in workflow.run("Fix the discount bug.", stream=True)]
                    cards = [e for e in events if e.type == "request_info"]
                    seen: dict[str, Any] = {
                        "cards": [e.data.function_call.name for e in cards],
                        "calls_before_answer": len(client.calls),
                        "outputs": [e.data for e in events if e.type == "output"],
                    }
                    if cards and approve is not None:
                        answer = {cards[0].request_id: cards[0].data.to_function_approval_response(approve)}
                        events = [e async for e in workflow.run(stream=True, responses=answer)]
                        seen["outputs"] = [e.data for e in events if e.type == "output"]
                    execute = next(e for e in workflow.get_executors_list() if e.id == wf.EXECUTE_STEP)
                    session = execute._session  # noqa: SLF001 - the executor's own session, as MAF checkpoints it
                    seen["todos"] = [(i.title, i.is_complete) for i in await todos.store.load_items(session, source_id=todos.source_id)]
                    seen["calls"] = client.calls
                    return seen

        return asyncio.run(_go())

    done = Content.from_function_call(
        call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "read"}, {"id": 2, "reason": "fixed"}]}
    )
    approved = run([plan, done, "Done: the discount is fixed."], approve=True)
    assert approved["calls"][0]["options"].get("response_format") is wf.StewardPlan, "PLAN asks for the structured plan"
    # Ollama's format enforces only the schema: a plan must carry a step (live 2026-11-01 sent "steps": [ ]).
    assert wf.StewardPlan.model_json_schema()["properties"]["steps"].get("minItems") == 1, "a plan's steps can be empty"
    assert wf.steward_plan_in('{"type": "approval", "questions": [{"message": "m"}], "steps": [ ]}') is None
    # A clarification needs a question (live 2026-11-01 sent "questions": []), and reaches the user as text.
    assert wf.StewardPlan.model_json_schema()["properties"]["questions"].get("minItems") == 1, "questions can be empty"
    assert wf.steward_plan_in('{"type": "clarification", "questions": [], "steps": ["s"]}') is None
    asked = wf.steward_plan_in('{"type": "clarification", "questions": [{"message": "Which file?", "choices": ["a.py", "b.py"]}], "steps": ["s"]}')
    assert asked is not None and wf.clarification_text(asked) == "Which file? (a.py / b.py)"
    assert approved["cards"] == [wf.APPROVE_PLAN] and approved["calls_before_answer"] == 1, "paused before anything ran"
    assert approved["outputs"] == ["Done: the discount is fixed."], "approved: EXECUTE ran and REPORT gave its answer"
    assert approved["calls"][1]["options"].get("response_format") is None, "EXECUTE is not asked for a plan"
    assert "Fix the discount line" in " ".join(m.text or "" for m in approved["calls"][1]["messages"]), "EXECUTE is given the plan"
    assert approved["todos"] == [("Read inventory.py", True), ("Fix the discount line", True)], "the plan's steps were his todos"
    assert len(approved["calls"]) == 3, "EXECUTE ran until its todos were complete, then stopped"

    denied = run([plan, "This must not run."], approve=False)
    assert denied["outputs"] == [wf.NOT_APPROVED] and len(denied["calls"]) == 1 and denied["todos"] == [], "denied: nothing ran"

    words = run(["Just words."], approve=None)
    assert words["outputs"] == ["Just words."] and words["cards"] == [], "no plan, no card"

    # An empty plan reply (the model's answer left in its reasoning) is asked again once, then the plan goes on.
    again = run(["", plan], approve=None)
    assert again["cards"] == [wf.APPROVE_PLAN] and again["calls_before_answer"] == 2, "an empty reply was asked again"
    assert wf.PLAN_AGAIN in " ".join(m.text or "" for m in again["calls"][1]["messages"])
    empty = run(["", ""], approve=None)
    assert len(empty["calls"]) == 2 and empty["cards"] == [], "asked again once, not in a loop"


def test_the_workflow_checks_what_execute_wrote_and_sends_failures_back_until_they_pass_or_attempts_run_out() -> None:
    """Piece 4: CHECK runs after EXECUTE, model-free. Failing with attempts left, REPAIR hands EXECUTE the output in
    its own session; passing, REPORT gives his answer with the result; after MAX_ATTEMPTS, REPORT says they still
    fail. The default check finds the .py files his calls to MAF's write tools named."""
    import steward_workflow as wf
    from agent_framework import Message

    plan = '{"type": "approval", "questions": [{"message": "Fix the discount."}], "steps": ["Fix the discount line"]}'
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "fixed"}]})

    def run(replies: list[Any], results: list[tuple[bool, str]]) -> tuple[list[Any], list[Any], list[int]]:
        client = ScriptedChatClient(replies)
        seen: list[int] = []

        def checks(messages: Any) -> tuple[bool, str]:
            seen.append(len(messages))
            return results.pop(0)

        async def _go() -> list[Any]:
            async with AsyncExitStack() as stack:
                agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
                async with agent:
                    workflow = wf.build_steward_workflow(agent, checks=checks)
                    events = [e async for e in workflow.run("Fix the discount bug.", stream=True)]
                    card = next(e for e in events if e.type == "request_info")
                    answer = {card.request_id: card.data.to_function_approval_response(True)}
                    return [e.data for e in [e async for e in workflow.run(stream=True, responses=answer)] if e.type == "output"]

        return asyncio.run(_go()), client.calls, seen

    outputs, calls, seen = run([plan, done, "First try.", "Fixed it."], [(False, "1 failed: test_discount"), (True, "1 passed")])
    assert len(seen) == 2 and len(calls) == 4, "checked after each attempt; repaired once"
    assert "1 failed: test_discount" in " ".join(m.text or "" for m in calls[3]["messages"]), "EXECUTE was given the failure"
    assert outputs == ["Fixed it.\n\nChecks passed:\n1 passed"], outputs

    failing = [(False, f"fail {n}") for n in range(1, wf.MAX_ATTEMPTS + 1)]
    outputs, calls, seen = run([plan, done, "a", "b", "c", "never"], failing)
    assert len(seen) == wf.MAX_ATTEMPTS and len(calls) == 2 + wf.MAX_ATTEMPTS, "stopped at the attempt limit"
    assert outputs == [f"c\n\nChecks still fail after {wf.MAX_ATTEMPTS} attempts:\nfail {wf.MAX_ATTEMPTS}"], outputs

    def call(name: str, file_name: str) -> Message:
        return Message(role="assistant", contents=[Content.from_function_call(call_id=file_name, name=name, arguments={"file_name": file_name})])

    written = [call("file_access_read", "a.py"), call("file_access_replace", "p/b.py"), call("file_access_write", "p/b.py"), call("file_access_write", "notes.md")]
    assert wf.written_python_files(written) == ["p/b.py"], "only code his write tools touched"

    # A write that waited on a card comes back as the user's answer, the call riding on it (live 2026-11-01).
    def answered(file_name: str, approved: bool) -> Message:
        write = Content.from_function_call(call_id=file_name, name="file_access_replace", arguments={"file_name": file_name})
        card = Content.from_function_approval_request(id=file_name, function_call=write)
        return Message(role="user", contents=[card.to_function_approval_response(approved)])

    assert wf.written_python_files([answered("p/c.py", True), answered("p/d.py", False)]) == ["p/c.py"], "approved writes only"
    assert wf.python_tests_for_writes([call("file_access_read", "a.py")]) is None, "nothing written, nothing run"


def test_a_denied_card_ends_execute_instead_of_sending_him_back_to_the_open_todo() -> None:
    """Live run 2026-11-01: an unasked commit step was denied twelve times, because its open todo made MAF's
    todos_remaining send him back each time. The user's No ends EXECUTE; the check and the report follow."""
    import steward_workflow as wf

    plan = '{"type": "approval", "questions": [{"message": "Edit and commit."}], "steps": ["Edit x.py", "Commit"]}'
    write = Content.from_function_call(call_id="w1", name="file_access_write", arguments={"file_name": "x.py", "content": "x = 1"})
    client = ScriptedChatClient([plan, write, "The write was denied, so I stopped.", "This must not run."])
    checked: list[Any] = []

    async def _go() -> list[Any]:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            async with agent:
                workflow = wf.build_steward_workflow(agent, checks=lambda messages: checked.append(messages))
                events = [e async for e in workflow.run("Edit x.py and commit it.", stream=True)]
                answers: list[bool] = [True, False]  # Approve the plan, deny the write
                while cards := [e for e in events if e.type == "request_info"]:
                    reply = {c.request_id: c.data.to_function_approval_response(answers.pop(0)) for c in cards}
                    events = [e async for e in workflow.run(stream=True, responses=reply)]
                return [e.data for e in events if e.type == "output"]

    outputs = asyncio.run(_go())
    assert len(client.calls) == 3, "after the No he answered once and was not sent back to the open todo"
    assert outputs == ["The write was denied, so I stopped."], outputs
    assert len(checked) == 1 and not (steward._WORKING_DIR / "x.py").exists(), "checked once; nothing written"


def test_the_hosted_workflow_sends_the_plan_card_and_runs_the_plan_on_approve(monkeypatch: Any) -> None:
    """Piece 3: MAF's Responses host serves the workflow (hosted.steward_server). A request comes back as the
    approve_plan card (mcp_approval_request) with the plan's steps; the Approve, sent as mcp_approval_response on
    previous_response_id, resumes the run from its checkpoint in a freshly built Steward, which runs the plan."""
    import json
    import tempfile

    import hosted
    from starlette.testclient import TestClient

    # A short folder: the host's state file names run to 191 characters, and Windows stops at 260 (hosted.py).
    state = tempfile.TemporaryDirectory(prefix="as")
    monkeypatch.setenv("AGENTSERVER_STATE_ROOT", state.name)
    plan = '{"type": "approval", "questions": [{"message": "Fix the discount."}], "steps": ["Read inventory.py", "Fix the discount line"]}'
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "r"}, {"id": 2, "reason": "f"}]})
    replies: list[Any] = [plan, done, "Done: the discount is fixed."]
    calls: list[Any] = []

    def fresh_client() -> ScriptedChatClient:  # the host refuses a client shared between requests
        client = ScriptedChatClient([])
        client.replies, client.calls = replies, calls
        return client

    with TestClient(hosted.steward_server(client_factory=fresh_client, enable_shell=False)) as http:
        # The Agent tab sends the console's PlanningResponse as response_format on its plan turns (steward.cjs).
        tab = {"store": True, "response_format": {"type": "object"}, "metadata": {"agent_mode": "execute"}}
        first = http.post("/responses", json={"input": "Fix the discount bug.", **tab}).json()
        [card] = [o for o in first["output"] if o["type"] == "mcp_approval_request"]
        assert card["name"] == "approve_plan" and json.loads(card["arguments"])["steps"][1] == "Fix the discount line"
        assert len(calls) == 1, "nothing ran before the Approve"
        answer = {"type": "mcp_approval_response", "approval_request_id": card["id"], "approve": True}
        second = http.post("/responses", json={"previous_response_id": first["id"], "input": [answer], **tab}).json()
    texts = [c["text"] for o in second["output"] if o["type"] == "message" for c in o["content"]]
    assert texts == ["Done: the discount is fixed."], second
    assert len(calls) == 3, "EXECUTE ran the plan until its todos were done"
    formats = [c["options"].get("response_format") for c in calls]
    assert formats[0].__name__ == "StewardPlan" and formats[1:] == [None, None], "each step's own format, not the tab's"
    # The host's tool-only identity never reaches the model call: Ollama's chat() refuses an unknown keyword.
    assert not any("additional_function_arguments" in c["kwargs"] for c in calls), "the host's identity reached the model"
    state.cleanup()


def test_an_approved_shell_command_runs_through_the_hosted_workflow(monkeypatch: Any) -> None:
    """Live run 2026-11-01: an approved run_shell failed the whole hosted run, because the workflow deep-copies each
    streamed update and MAF's shell text could not be copied (agent._shell_text_copies)."""
    import tempfile

    import hosted
    from starlette.testclient import TestClient

    state = tempfile.TemporaryDirectory(prefix="as")
    monkeypatch.setenv("AGENTSERVER_STATE_ROOT", state.name)
    plan = '{"type": "approval", "questions": [{"message": "Echo."}], "steps": ["Echo hi"]}'
    shell = Content.from_function_call(call_id="s1", name="run_shell", arguments={"command": "echo hi"})
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "echoed"}]})
    replies: list[Any] = [plan, shell, done, "Echoed."]
    calls: list[Any] = []

    def fresh_client() -> ScriptedChatClient:
        client = ScriptedChatClient([])
        client.replies, client.calls = replies, calls
        return client

    names: list[str] = []
    with TestClient(hosted.steward_server(client_factory=fresh_client)) as http:
        turn = http.post("/responses", json={"input": "Echo hi.", "store": True}).json()
        while cards := [o for o in turn["output"] if o["type"] == "mcp_approval_request"]:
            names += [c["name"] for c in cards]
            answers = [{"type": "mcp_approval_response", "approval_request_id": c["id"], "approve": True} for c in cards]
            turn = http.post("/responses", json={"previous_response_id": turn["id"], "store": True, "input": answers}).json()
    state.cleanup()
    assert names == ["approve_plan", "run_shell"], names
    assert turn["status"] == "completed", turn.get("error")
    texts = [c["text"] for o in turn["output"] if o["type"] == "message" for c in o["content"]]
    assert texts == ["Echoed."], texts
    assert "hi" in " ".join(str(m.text or "") + str([c.result for c in m.contents if c.type == "function_result"]) for m in calls[2]["messages"])


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


def test_improvement_loop_workflow_repairs_reviews_and_resumes(tmp_path: Path) -> None:
    """ADR-0001 item 12: approvals cross the workflow, failing checks go back to Steward, the review resumes from a checkpoint."""
    from agent_framework import FileCheckpointStorage

    import improvement_loop_workflow as loop

    runs = tmp_path / "runs"
    # A check that fails on its first run and passes after: one repair, then the review.
    check = (
        sys.executable, "-c",
        f"import pathlib, sys; p = pathlib.Path(r'{runs}'); n = int(p.read_text()) if p.exists() else 0; "
        "p.write_text(str(n + 1)); sys.exit(0 if n else 1)",
    )
    commit = Content.from_function_call(call_id="c1", name="git_commit", arguments={"message": "x"})
    client = ScriptedChatClient([commit, "Attempt one.", "Attempt two."])
    storage = FileCheckpointStorage(storage_path=tmp_path / "checkpoints")

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            workflow = loop.create_workflow(agent, storage, checks=[check])
            events = await workflow.run("Make a change.")
            [approval] = events.get_request_info_events()
            assert approval.data.function_call.name == "git_commit", "Steward's own approval reaches Kyle"
            events = await workflow.run(responses={approval.request_id: approval.data.to_function_approval_response(False)})
            [review] = events.get_request_info_events()
            assert (review.data.attempt, review.data.passed, review.data.summary) == (2, True, "Attempt two.")
            # A new run of the same graph resumes from the last checkpoint and re-asks the pending review.
            latest = max(await storage.list_checkpoints(workflow_name=workflow.name), key=lambda c: c.timestamp)
            resumed = loop.create_workflow(agent, storage, checks=[check])
            [again] = (await resumed.run(checkpoint_id=latest.checkpoint_id)).get_request_info_events()
            return (await resumed.run(responses={again.request_id: "keep"})).get_outputs()

    [result] = asyncio.run(_go())
    assert (result.decision, result.passed, result.attempts) == ("keep", True, 2)
    assert len(client.calls) == 3, "the rejected commit, then one attempt per check run"
    assert runs.read_text() == "2", "the checks ran after each attempt"
