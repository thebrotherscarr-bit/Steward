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
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _his_memory_is_never_the_real_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Step 5: hosts pass steward_memory_store(); in the tests its default store is off (an extraction call would take
    a scripted reply), and in any case it would never be his real memory folder."""
    monkeypatch.setenv("STEWARD_AUTOMATIC_MEMORY", "off")
    monkeypatch.setattr(steward, "MEMORY_DIR", tmp_path / "agent-memory")

# Hermetic: no SecondBrain connection (and so no Atlas door), whatever agent.py's load_dotenv() found.
for _name in ("SECONDBRAIN_MCP_URL", "SECONDBRAIN_MCP_KEY"):
    os.environ.pop(_name, None)
# Hermetic: a workflow run here never runs the default check on the real repo, whose changed .py files include these
# tests (2026-11-02: that ran this file inside itself, level after level). Only the check's own test clears it.
os.environ["STEWARD_CHECK_RUNNING"] = "1"

SKILLS = ("agent-framework-builder-python", "code-review", "codebase-map", "evals", "github", "improve", "run-tests", "secondbrain-notes")


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
    # The door's and SecondBrain's tools come over MCP, which these tests do not connect.
    over_mcp = {"atlas_git_branch", "atlas_git_commit", "atlas_git_push", "atlas_git_pr", "secondbrain_write_note", "secondbrain_append_to_note"}
    assert steward._CHANGES_THINGS - {"run_shell", *over_mcp} <= offered
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
    assert 'load_skill("evals")' in hints_for("Run your small asks evals.")
    assert 'load_skill("github")' in hints_for("Send this line and open a pull request.")
    assert 'load_skill("run-tests")' in hints_for("Run the tests in the sample project.")
    assert 'load_skill("secondbrain-notes")' in hints_for("Write it up in SecondBrain.")
    assert 'load_skill("improve")' in hints_for("This is an improvement round: follow your improve skill.")
    import evals

    assert "run-tests" not in hints_for(evals.SMALL_ASK_README), "the README eval ask stays as it was"
    assert "github" not in hints_for("Commit your work now: call git_commit once."), "the commit step is not the github skill"
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


def test_a_plan_that_does_not_name_the_work_fails_the_plan_step_eval() -> None:
    """Run 15: a bug-fix plan that planned a new inventory.py passed; the plan must name the discount line's file and
    fix. Moved in step 5 (5.3) from the retired plan set's plan_before_act to the steps set's plan_step."""
    import json

    import evals

    def run(steps: list[str], message: str) -> bool:
        reply = '{"type": "approval", "questions": [{"message": "%s"}], "steps": %s}' % (message, json.dumps(steps))
        return scored(evals.plan_step, evals.STEPS_QUERY, [Message(role="assistant", contents=[Content.from_text(reply)])]).passed

    assert run(["Add inventory.py re-exporting the functions"], "Add a new file.") is False
    assert run(["Fix the discount in inventory.py"], "Divide discount_percent by 100.") is True


def test_the_small_asks_deny_a_commit_card_and_nothing_is_committed() -> None:
    """A small ask's commit card is answered Deny (git_commit is never in the approved tools), so git_commit never runs,
    HEAD stays and the run goes on; commit_by_tool and commit_message_specific read that card. Moved in step 5 (5.3)
    from the retired walkthrough set's commit step."""
    import evals
    from agent_framework import FileAccessProvider

    message = "Add item_count to inventory.py"
    commit = Content.from_function_call(call_id="c1", name="git_commit", arguments={"message": message})
    client = ScriptedChatClient([commit, "The commit was not approved."])
    approve = set(FileAccessProvider._WRITE_TOOL_NAMES)  # what small_main approves

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            async with agent:
                from agent_framework import AgentModeProvider, set_agent_mode

                modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                session = agent.create_session()
                set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
                return await evals._run_answering_cards(agent, session, evals.SMALL_ASK_NEW_CODE, approve)

    head = steward._git("rev-parse", "HEAD").stdout
    response = asyncio.run(_go())
    conversation = list(response.messages)
    assert [c.function_call.name for c in evals._cards_named(conversation, "git_commit")] == ["git_commit"], "the commit asked"
    assert steward._git("rev-parse", "HEAD").stdout == head, "the denied commit did not run"
    assert len(client.calls) == 2, "the run continued after the Deny"
    checks_passed = Message(role="assistant", contents=[Content.from_text("Checks passed:\n1 passed")])
    for check in (evals.commit_by_tool, evals.commit_message_specific):
        result = scored(check, evals.SMALL_ASK_NEW_CODE, [checks_passed, *conversation])
        assert result.passed, result.reason


def said(events: list[Any]) -> list[str]:
    """What the caller is shown, in order: each output, and each step's streamed text (intermediate output), as MAF's
    WorkflowAgent and Responses host forward them."""
    shown: list[str] = []
    for event in events:
        if event.type == "output":
            shown.append(str(event.data))
        elif event.type == "intermediate" and (getattr(event.data, "text", "") or "").strip():
            shown.append(event.data.text)
    return shown


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
                        "outputs": said(events),
                    }
                    if cards and approve is not None:
                        answer = {cards[0].request_id: cards[0].data.to_function_approval_response(approve)}
                        events = [e async for e in workflow.run(stream=True, responses=answer)]
                        seen["outputs"] = said(events)
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

    # A plan labelled a clarification with no choices (live 2026-11-02, three times) gets the guide's definitions once.
    mislabelled = '{"type": "clarification", "questions": [{"message": "Should I proceed?"}], "steps": ["Fix the discount line"]}'
    relabelled = run([mislabelled, plan], approve=None)
    assert relabelled["cards"] == [wf.APPROVE_PLAN] and relabelled["calls_before_answer"] == 2, "the mislabelled plan was asked again"
    assert wf.PLAN_IS_APPROVAL in " ".join(m.text or "" for m in relabelled["calls"][1]["messages"])
    still = run([mislabelled, mislabelled], approve=None)
    assert still["outputs"] == ["Should I proceed?"] and len(still["calls"]) == 2, "asked again once, then shown as it is"
    choices = '{"type": "clarification", "questions": [{"message": "Which file?", "choices": ["a.py", "b.py"]}], "steps": ["s"]}'
    question = run([choices], approve=None)
    assert question["outputs"] == ["Which file? (a.py / b.py)"] and len(question["calls"]) == 1, "a real clarification ends the run"


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
                    return said([e async for e in workflow.run(stream=True, responses=answer)])

        return asyncio.run(_go()), client.calls, seen

    committed = Content.from_function_call(call_id="k1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "asked"}]})
    # A repair's todo (REPAIR_TODO) is his one open item until he marks it done, as any approved step.
    fixed = Content.from_function_call(call_id="f1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "fixed"}]})
    outputs, calls, seen = run(
        [plan, done, "First try.", fixed, "Fixed it.", committed, "Committed."],
        [(False, "1 failed: test_discount"), (True, "1 passed")],
    )
    assert len(seen) == 2, "checked after each attempt; repaired once"
    assert "1 failed: test_discount" in " ".join(m.text or "" for m in calls[3]["messages"]), "EXECUTE was given the failure"
    # Live 2026-11-02: his finished todos put him back in plan mode (ReturnToPlanWhenDone), so each repair was
    # answered with a new plan. The repair runs in execute mode, with the fix as its todo.
    assert calls[3]["options"].get("response_format") is None, "the repair was asked for a plan, not a fix"
    assert wf.REPAIR_TODO in " ".join(m.text or "" for m in calls[3]["messages"]), "the repair's todo is not in front of him"
    assert "Do not commit" in " ".join(m.text or "" for m in calls[1]["messages"]), "EXECUTE is told the commit comes later"
    # Passing on changed code: the commit step asks him to commit (his git_commit raises the card), then REPORT.
    assert "Commit your work now" in " ".join(m.text or "" for m in calls[5]["messages"]), "the commit came after the pass"
    assert len(calls) == 7, len(calls)
    assert outputs == ["First try.", "Fixed it.", "Checks passed:\n1 passed", "Committed."], outputs

    failing = [(False, f"fail {n}") for n in range(1, wf.MAX_ATTEMPTS + 1)]
    outputs, calls, seen = run([plan, done, "a", fixed, "b", fixed, "c", "never"], failing)
    # plan, then EXECUTE's two calls, then each repair's two (its todo marked done, then his answer)
    assert len(seen) == wf.MAX_ATTEMPTS and len(calls) == 3 + 2 * (wf.MAX_ATTEMPTS - 1), "stopped at the attempt limit; no commit asked"
    assert not any("Commit your work now" in (m.text or "") for c in calls for m in c["messages"]), "failing work is not committed"
    assert outputs == ["a", "b", "c", f"Checks still fail after {wf.MAX_ATTEMPTS} attempts:\nfail {wf.MAX_ATTEMPTS}"], outputs

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

    # The check reads the files on disk (live 2026-11-02: an edit approved before two commit cards was missed, because
    # MAF hands the next step only the messages since the last card). A changed file is tested whatever wrote it.
    import subprocess
    import tempfile

    assert wf.python_tests_for_changes([]) is None, "inside a check's own pytest, the check does not start again"
    marker = os.environ.pop(wf._CHECK_RUNNING)  # noqa: SLF001 - this test runs the check, in its own repo
    try:
        _the_check_reads_the_files_on_disk(wf)
    finally:
        os.environ[wf._CHECK_RUNNING] = marker  # noqa: SLF001


def _the_check_reads_the_files_on_disk(wf: Any) -> None:
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(prefix="ck") as folder:
        workspace = Path(folder)

        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, check=True)

        git("init", "-q")
        (workspace / "p").mkdir()
        (workspace / "p" / "test_t.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        git("add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        assert wf.python_tests_for_changes([], workspace=workspace) is None, "nothing changed, nothing run"
        # Today's broken edit: a docstring run into the next line, the assert line gone.
        (workspace / "p" / "test_t.py").write_text('def test_ok():\n    """Doc."""    x = 1\n', encoding="utf-8")
        result = wf.python_tests_for_changes([], workspace=workspace)
        assert result is not None and not result[0], "a broken change fails the check, with no write in the messages"
        assert "pytest -q p" in result[1], result


def test_the_commit_comes_after_passing_checks_on_his_own_git_commit_card() -> None:
    """Step 2 (2026-11-02): live, he asked to commit twice inside EXECUTE, before anything had checked his edit. Now
    EXECUTE is told not to commit; after passing checks the commit step asks him, his git_commit raises the user's
    card (the guide's Part 2: "Approve and the trade runs; deny and the agent adapts"), and the No commits nothing."""
    import steward_workflow as wf

    plan = '{"type": "approval", "questions": [{"message": "Fix it."}], "steps": ["Fix x"]}'
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "fixed"}]})
    commit = Content.from_function_call(call_id="g1", name="git_commit", arguments={"message": "Fix x"})
    client = ScriptedChatClient([plan, done, "Fixed x.", commit, "The commit was not approved, so nothing was committed."])
    head = steward._git("rev-parse", "HEAD").stdout

    async def _go() -> tuple[list[str], list[Any]]:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            async with agent:
                workflow = wf.build_steward_workflow(agent, checks=lambda messages: (True, "1 passed"))
                events = [e async for e in workflow.run("Fix x.", stream=True)]
                shown = said(events)
                answers, cards = [True, False], []  # Approve the plan, deny the commit
                while pending := [e for e in events if e.type == "request_info"]:
                    cards += [c.data.function_call.name for c in pending]
                    reply = {c.request_id: c.data.to_function_approval_response(answers.pop(0)) for c in pending}
                    events = [e async for e in workflow.run(stream=True, responses=reply)]
                    shown += said(events)
                return cards, shown

    cards, outputs = asyncio.run(_go())
    assert cards == [wf.APPROVE_PLAN, "git_commit"], "the commit asked on its own card, after the checks"
    assert steward._git("rev-parse", "HEAD").stdout == head, "the denied commit did not run"
    assert outputs == ["Fixed x.", "Checks passed:\n1 passed", "The commit was not approved, so nothing was committed."], outputs


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
                return said(events)

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


def test_the_steps_eval_scores_each_workflow_step_by_its_own_evaluator() -> None:
    """Piece 5: evals.py steps groups a run's conversations by executor id and scores PLAN and EXECUTE apart."""
    import evals
    import steward_workflow as wf
    from agent_framework import Message

    def plan_run(reply: str) -> dict[str, Any]:
        client = ScriptedChatClient([reply])

        async def _go() -> list[Any]:
            async with AsyncExitStack() as stack:
                agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
                async with agent:
                    return [e async for e in wf.build_steward_workflow(agent).run(evals.STEPS_QUERY, stream=True)]

        return evals.step_conversations(asyncio.run(_go()))

    good = '{"type": "approval", "questions": [{"message": "Fix the discount."}], "steps": ["Read inventory.py", "Fix the discount line"]}'
    steps = plan_run(good)
    assert list(steps) == [wf.PLAN_STEP], "the run's AgentExecutor steps, by executor id"
    assert scored(evals.plan_step, evals.STEPS_QUERY, steps[wf.PLAN_STEP][0]).passed, "a plan naming the work passes"
    asked = '{"type": "clarification", "questions": [{"message": "Which test?"}], "steps": ["Read the tests"]}'
    assert not scored(evals.plan_step, evals.STEPS_QUERY, plan_run(asked)[wf.PLAN_STEP][0]).passed, "a question is no plan"

    def answered(approved: bool) -> list[Any]:
        write = Content.from_function_call(call_id="w", name="file_access_replace", arguments={"file_name": "harness/steward/working/sample-project/inventory.py"})
        card = Content.from_function_approval_request(id="w", function_call=write)
        return [Message(role="user", contents=[card.to_function_approval_response(approved)])]

    assert scored(evals.execute_step, "go", answered(True)).passed, "an approved write to the module passes"
    assert not scored(evals.execute_step, "go", answered(False)).passed, "a denied write is no work done"


def test_the_trace_file_is_capped_and_keeps_the_newest_whole_spans() -> None:
    """Kyle, 2026-11-01: "cut the traces file down to a 100MB max". Past the cap, the oldest spans go."""
    import json
    import tempfile

    from halo_traces import HaloJsonlSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    with tempfile.TemporaryDirectory(prefix="tr") as folder:
        path = Path(folder) / "traces.jsonl"
        exporter = HaloJsonlSpanExporter(path, max_bytes=4000)
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("cap")
        for n in range(60):
            with tracer.start_as_current_span(f"span-{n}"):
                pass
        provider.shutdown()
        lines = path.read_text(encoding="utf-8").splitlines()
        assert path.stat().st_size <= 4000, path.stat().st_size
        assert all(json.loads(line) for line in lines), "every line kept is a whole span"
        assert lines and lines[-1].find("span-59") >= 0, "the newest span is kept"


def test_every_host_builds_the_same_steward_workflow() -> None:
    """Define once (the guide's Part 4): the Agent tab's service and the evals build Steward and his workflow in one
    place (steward_workflow.build_steward). The service's graph is the builder's graph (MAF's graph_signature_hash);
    the evals drive that workflow as an agent (Learn, "Using Workflows as Agents"): the plan card is answered and
    EXECUTE's work reaches them live (intermediate output). The guide's console runs the same harness agent the
    workflow wraps (build_steward_agent), as the guide ships it: a workflow's cards resume from checkpoints, not a
    console's session (MAF issue #5818)."""
    import console_app
    import evals
    import hosted
    import steward_workflow as wf

    plan = '{"type": "approval", "questions": [{"message": "Fix it."}], "steps": ["Fix x"]}'
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "fixed"}]})

    async def _go() -> tuple[str, str, Any]:
        async with AsyncExitStack() as stack:
            agent, workflow = await wf.build_steward(stack, client=ScriptedChatClient(), enable_shell=False)
            async with agent:
                built = workflow.graph_signature_hash
        served = await hosted.steward_graph(None, lambda: ScriptedChatClient(), enable_shell=False)
        _, response = await evals.run_steward("Fix x.", set(), client=ScriptedChatClient([plan, done, "Fixed x."]), enable_shell=False)
        return built, served.graph_signature_hash, response

    built, served, response = asyncio.run(_go())
    assert served == built, "the Agent tab's service builds a different graph from the shared builder"
    cards = [c.function_call.name for m in response.messages for c in m.contents if c.type == "function_approval_request"]
    assert cards == [wf.APPROVE_PLAN], f"the evals did not meet the plan card: {cards}"
    assert "Fixed x." in response.text, f"EXECUTE's work did not reach the evals: {response.text!r}"
    assert console_app.build_steward_agent is steward.build_steward_agent, "the console builds Steward somewhere else"


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


def test_mcp_hosting_serves_steward_as_one_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-0001 item 10: mcp_app.py serves Steward as one MCP tool; a reused session_id continues his conversation."""
    from agent_framework import InMemoryHistoryProvider
    from starlette.testclient import TestClient

    import mcp_app

    monkeypatch.setattr(mcp_app, "MCP_SESSIONS_DIR", tmp_path / "mcp-sessions")  # step 5: never the real sessions

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


def test_improvement_loop_workflow_diagnoses_hands_edits_repairs_reviews_and_resumes(tmp_path: Path) -> None:
    """ADR-0001 item 12 and the split fixer (2026-11-03): Steward diagnoses and hands each edit to the coder with
    hand_to_coder; the coder gets only the change and its lines, and its write asks a card; failing checks go back to
    Steward; the review resumes from a checkpoint."""
    from agent_framework import FileCheckpointStorage

    import improvement_loop_workflow as loop

    runs = tmp_path / "runs"
    # A check that fails on its first run and passes after: one repair, then the review.
    check = (
        sys.executable, "-c",
        f"import pathlib, sys; p = pathlib.Path(r'{runs}'); n = int(p.read_text()) if p.exists() else 0; "
        "p.write_text(str(n + 1)); sys.exit(0 if n else 1)",
    )
    handed = Content.from_function_call(
        call_id="h1", name="hand_to_coder",
        arguments={"file": "README.md", "start_line": 1, "end_line": 2, "change": "Name the harness in the title."},
    )
    again = Content.from_function_call(
        call_id="h2", name="hand_to_coder",
        arguments={"file": "README.md", "start_line": 1, "end_line": 1, "change": "Shorter title."},
    )
    replace = Content.from_function_call(
        call_id="r1", name="file_access_replace", arguments={"file_name": "README.md", "old_string": "x", "new_string": "y"}
    )
    diagnoser = ScriptedChatClient([handed, "Handed one edit.", again, "Handed the fix."])
    coder_client = ScriptedChatClient([replace, "Edit one.", "Edit two."])
    storage = FileCheckpointStorage(storage_path=tmp_path / "checkpoints")

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=diagnoser, enable_shell=False, extra_tools=[loop.hand_to_coder])
            coder = loop.build_coder(coder_client)
            workflow = loop.create_workflow(agent, coder, storage, checks=[check])
            events = await workflow.run("Make a change.")
            [approval] = events.get_request_info_events()
            assert approval.data.function_call.name == "file_access_replace", "the coder's write reaches Kyle as a card"
            events = await workflow.run(responses={approval.request_id: approval.data.to_function_approval_response(False)})
            [review] = events.get_request_info_events()
            assert (review.data.attempt, review.data.passed, review.data.summary) == (2, True, "Edit two.")
            # A new run of the same graph resumes from the last checkpoint and re-asks the pending review.
            latest = max(await storage.list_checkpoints(workflow_name=workflow.name), key=lambda c: c.timestamp)
            resumed = loop.create_workflow(agent, coder, storage, checks=[check])
            [again_review] = (await resumed.run(checkpoint_id=latest.checkpoint_id)).get_request_info_events()
            return (await resumed.run(responses={again_review.request_id: "keep"})).get_outputs()

    [result] = asyncio.run(_go())
    assert (result.decision, result.passed, result.attempts) == ("keep", True, 2)
    assert runs.read_text() == "2", "the checks ran after each edit"
    first = " ".join(m.text or "" for m in coder_client.calls[0]["messages"])
    assert "CHANGE: Name the harness in the title." in first and "README.md, lines 1-2" in first
    assert "    1  " in first, "the coder sees the lines as they are now, numbered"
    assert len(first) < 4000, f"the coder's prompt is the brief and its lines, not the harness ({len(first)} chars)"
    assert "Steward" not in str(coder_client.calls[0]["options"].get("instructions") or ""), "not Steward's harness"
    repair = " ".join(m.text or "" for m in diagnoser.calls[2]["messages"])
    assert "checks failed" in repair and "hand_to_coder" in repair, "the failing checks go back to Steward, not the coder"


def test_a_bad_edit_goes_back_to_steward_with_the_reason() -> None:
    """The split fixer's gate: an edit outside the workspace, past the file's end or longer than EDIT_SPAN_MAX lines is
    not handed to the coder; Steward gets the reason."""
    import improvement_loop_workflow as loop

    assert loop.edit_problem(loop.Edit("README.md", 1, 2, "x")) is None
    assert "not a file" in loop.edit_problem(loop.Edit("../outside.md", 1, 1, "x"))
    assert "lines" in loop.edit_problem(loop.Edit("README.md", 1, 100_000, "x"))
    assert "split it" in loop.edit_problem(loop.Edit("harness/steward/step04_production_ready/agent.py", 1, 200, "x"))
    assert "no change" in loop.edit_problem(loop.Edit("README.md", 1, 1, " "))


def test_the_small_asks_check_each_of_todays_failures() -> None:
    """Step 4: each small-ask check fails on the failure it is named for, passes on the right run, and passes an ask
    that is not its own (the guide's evaluators)."""
    import evals
    import steward_workflow as wf
    from agent import PLAN_REPLY_NUDGE

    def card(name: str, args: dict[str, Any]) -> Message:
        call = Content.from_function_call(call_id=f"{name}-1", name=name, arguments=args)
        return Message(role="assistant", contents=[Content.from_function_approval_request(id=f"{name}-1", function_call=call)])

    def approved_write(file_name: str) -> Message:
        from agent_framework import FileAccessProvider

        call = Content.from_function_call(
            call_id="w1", name=FileAccessProvider.WRITE_TOOL_NAME, arguments={"file_name": file_name, "content": "x"}
        )
        request = Content.from_function_approval_request(id="w1", function_call=call)
        return Message(role="user", contents=[request.to_function_approval_response(approved=True)])

    def said(text: str) -> Message:
        return Message(role="assistant", contents=[Content.from_text(text)])

    def passed(check: Any, query: str, conversation: list[Any]) -> bool:
        return scored(check, query, conversation).passed

    new_code, discount, readme = evals.SMALL_ASK_NEW_CODE, evals.SMALL_ASK_DISCOUNT, evals.SMALL_ASK_README
    module = "harness/steward/working/sample-project/inventory.py"
    checks_passed = said("Checks passed:\n$ pytest -q harness/steward/working/sample-project\n(exit 0)")

    # 1. The plan labelled as a clarification.
    assert passed(evals.plan_is_approval, new_code, [card(wf.APPROVE_PLAN, {"steps": ["Add it"]})])
    assert not passed(evals.plan_is_approval, new_code, [said("Should I proceed? (yes)")])
    assert passed(evals.commit_by_tool, readme, []), "not the README ask's check"

    # 2. A write missed behind a later card.
    assert passed(evals.check_covers_writes, new_code, [approved_write(module), checks_passed])
    assert not passed(evals.check_covers_writes, new_code, [approved_write(module), said("Done.")])

    # 3. A broken edit (tabs).
    evals.SMALL_ASK_ORIGINALS[module] = "def order_total(items):\n    return 0\n"
    evals.SMALL_ASK_FILES[new_code] = {module: 'def order_total(items):\n    """Total."""\n    return 0\n'}
    assert passed(evals.edit_keeps_file_whole, new_code, [])
    evals.SMALL_ASK_FILES[new_code] = {module: 'def order_total(items):\n\t"""Total."""\n    return 0\n'}
    assert not passed(evals.edit_keeps_file_whole, new_code, [])
    evals.SMALL_ASK_FILES.clear()
    evals.SMALL_ASK_ORIGINALS.clear()

    # 4. "Proceed?" instead of git_commit, and the door's commit, which would park a real card.
    commit_card = card("git_commit", {"message": "Add item_count to inventory.py"})
    assert passed(evals.commit_by_tool, new_code, [checks_passed, commit_card])
    assert not passed(evals.commit_by_tool, new_code, [checks_passed, said("Shall I proceed with the commit?")])
    door = Message(role="assistant", contents=[Content.from_function_call(call_id="d1", name="atlas_git_commit", arguments={})])
    assert not passed(evals.commit_by_tool, new_code, [checks_passed, door, commit_card])

    # 5. A vague commit message.
    assert passed(evals.commit_message_specific, new_code, [commit_card])
    assert not passed(evals.commit_message_specific, new_code, [card("git_commit", {"message": "Update"})])

    # 6. The loop's nudge in his reply.
    assert passed(evals.no_nudge_in_reply, readme, [said("Added the line to README.md on running the tests.")])
    assert not passed(evals.no_nudge_in_reply, readme, [said(PLAN_REPLY_NUDGE)])

    # 7. An off-topic final answer.
    assert passed(evals.answer_on_topic, discount, [said("Fixed the discount: it divides by 100 now.")])
    assert not passed(evals.answer_on_topic, discount, [said("Paris is the capital of France.")])


def test_an_eval_run_never_touches_stewards_real_memory() -> None:
    """Live 2026-11-02: eval runs saved plans into his real memory (agent-file-memory/steward) and a later run's commit
    message described them. run_steward gives each run a throwaway memory store, so a memory written in an eval stays
    out of the folder every real session reads. Step 5: his automatic memory is a throwaway store in an eval too."""
    import evals

    real = steward._WORKING_DIR / "agent-file-memory" / "steward" / "eval-leak-check.md"
    write = Content.from_function_call(
        call_id="m1", name="file_memory_write", arguments={"file_name": "eval-leak-check.md", "content": "leak"}
    )
    client = ScriptedChatClient([write, "Saved."])
    try:
        asyncio.run(evals.run_steward("Remember the word leak.", set(), client=client, enable_shell=False))
        his_calls = [c for c in client.calls if "durable memory" not in " ".join(m.text or "" for m in c["messages"])]
        assert len(his_calls) == 2, "the memory write ran"
        assert len(client.calls) > len(his_calls), "his automatic memory ran in the eval, on its throwaway store"
        assert not real.exists(), "an eval's memory write must not reach his real memory"
        assert not steward.MEMORY_DIR.exists(), "nor his real automatic memory"
    finally:
        real.unlink(missing_ok=True)
        real.with_name("eval-leak-check_description.md").unlink(missing_ok=True)


def test_his_shell_runs_his_own_python() -> None:
    """Live 2026-11-02: he ran `python .../evals.py` in his shell, and the system Python had no agent_framework. His
    shell starts with his own Python first, so `python` is the interpreter he runs on, with MAF installed."""

    async def _go() -> Any:
        shell = steward._build_shell()
        await shell.start()
        try:
            return await shell.run('python -c "import agent_framework, sys; print(sys.prefix)"')
        finally:
            await shell.close()

    result = asyncio.run(_go())
    assert result.exit_code == 0, f"python in his shell cannot import agent_framework: {result.stderr[-300:]}"
    assert Path(result.stdout.strip()).resolve() == Path(sys.prefix).resolve(), result.stdout


def test_a_skill_read_while_planning_is_not_demanded_again_when_the_work_is_done() -> None:
    """Live 2026-11-02: he loaded the evals skill in the plan step; the execute step's session never saw that call, the
    required-tools check said load_skill was missing, and he ran the whole eval set a second time. A hint requires only
    the work's tools, so finished work that never re-reads its skill is not sent back."""
    assert all("load_skill" not in tools for _, _, tools in steward.REQUEST_HINTS), "no hint may require load_skill"
    client, _, _ = run_steward(["The pull request is open."], "Open a pull request for this line.", mode="execute")
    assert len(client.calls) == 1, "no 'Before you finish' nudge for a skill read in another step"
    assert not any(steward.REQUIRED_TOOLS_NUDGE in str(m.text) for m in client.calls[0]["messages"])


def test_the_split_fixer_is_steward_diagnosing_and_a_small_coder_on_the_coder_model() -> None:
    """Step 6 (2026-11-03): Steward diagnoses on his own harness with hand_to_coder beside his tools; the coder is a
    small MAF Agent on the coder model with only MAF's file tools (writes ask), his tool-call limits and a 16K window."""
    from agent_framework import FileAccessProvider

    import improvement_loop_workflow as loop

    assert loop.fixer_client().model == steward._CODER_MODEL
    assert steward._CODER_MODEL == os.environ.get("STEWARD_CODER_MODEL", "qwen2.5-coder:14b")
    client = ScriptedChatClient([])
    coder = loop.build_coder(client)
    assert coder.default_options.get("num_ctx") == loop.FIXER_CONTEXT == 16_384
    assert coder.default_options.get("keep_alive") == steward.OLLAMA_OPTIONS["keep_alive"]
    [files] = [p for p in coder.context_providers if isinstance(p, FileAccessProvider)]
    assert len(coder.context_providers) == 1, "only the file tools: no harness, skills, memory or Charter"
    assert {k: client.function_invocation_configuration[k] for k in steward.TOOL_CALLS} == steward.TOOL_CALLS

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            return await loop.build_diagnoser(stack, client=ScriptedChatClient(["ok"]), enable_shell=False)

    diagnoser = asyncio.run(_go())
    names = {getattr(t, "name", "") for t in diagnoser.default_options.get("tools", [])}
    assert "hand_to_coder" in names and "git_commit" in names, "his own tools, and the hand-off"


def test_the_eval_gate_counts_only_applicable_checks_and_fails_a_drop(tmp_path: Path) -> None:
    """Step 6, 6.2: the gate counts the checks that apply to their ask and fails when they drop below the baseline."""
    from types import SimpleNamespace

    import evals
    import improvement_loop_workflow as loop

    def score(passed: bool, reason: str) -> Any:
        return SimpleNamespace(passed=passed, sample={"reason": reason})

    items = [
        SimpleNamespace(scores=[score(True, "On topic."), score(False, "Message 'Update'."), score(True, "Not this case.")]),
        SimpleNamespace(scores=[score(True, "The plan came as an approval card."), score(True, "Not this case.")]),
    ]
    assert evals.applicable_checks(items) == (2, 3), "a 'Not this case.' pass is not counted"
    baselines = tmp_path / "eval_baselines.json"
    baselines.write_text('{"small": {"checks": 10}}', encoding="utf-8")
    assert evals.gate(9, 14, baselines=baselines) == 1, "a drop fails the gate"
    assert evals.gate(10, 14, baselines=baselines) == 0
    assert evals.gate(11, 14, baselines=baselines) == 0
    assert evals.gate(10, 14) == 0, "the recorded baseline is 10 of 14"
    assert any("evals.py" in part for check in loop.GATE_CHECKS for part in check), "the loop's gate runs the evals"


def test_an_improve_turn_runs_the_improvement_loop_on_the_host_and_its_review_comes_back_as_a_card(monkeypatch: Any) -> None:
    """Step 6, 6.3: a turn with {"steward_workflow": "improve"} runs the improvement loop on his host (the coder
    fixer, the gate, the review). The review comes back as MAF's request_info call; its answer, sent as
    function_call_output on previous_response_id, resumes the loop to its decision. Other turns are untouched."""
    import json
    import tempfile

    import hosted
    import improvement_loop_workflow as loop
    from starlette.testclient import TestClient

    state = tempfile.TemporaryDirectory(prefix="as")
    monkeypatch.setenv("AGENTSERVER_STATE_ROOT", state.name)
    monkeypatch.setattr(loop, "GATE_CHECKS", [[sys.executable, "-c", "print('gate ok')"]])
    replies: list[Any] = ["Done: nothing needed changing."]
    calls: list[Any] = []

    def fresh_client() -> ScriptedChatClient:
        client = ScriptedChatClient([])
        client.replies, client.calls = replies, calls
        return client

    improve = {"store": True, "metadata": {"steward_workflow": "improve"}}
    with TestClient(hosted.steward_server(client_factory=fresh_client, enable_shell=False)) as http:
        first = http.post("/responses", json={"input": "improve: the plan comes back as prose", **improve}).json()
        [review] = [o for o in first["output"] if o["type"] == "function_call" and o["name"] == "request_info"]
        asked = json.loads(review["arguments"])["request"]
        assert asked["passed"] is True and "keep" in asked["prompt"], asked
        asked_fixer = " ".join(m.text or "" for m in calls[0]["messages"])
        assert "the plan comes back as prose" in asked_fixer, "the fixer got the task"
        assert "improve:" not in asked_fixer, "without the improve: prefix"
        answer = {"type": "function_call_output", "call_id": review["call_id"], "output": "keep"}
        second = http.post("/responses", json={"previous_response_id": first["id"], "input": [answer], **improve}).json()
    assert not any(o["type"] == "function_call" for o in second["output"]), "the loop decided; no further card"
    assert "keep" in json.dumps(second["output"]), second["output"]
    assert hosted.steward_options(None, {"metadata": {"steward_workflow": "improve"}}) == {}, "the key never reaches the model"
    state.cleanup()


def test_a_round_that_names_nothing_takes_the_diagnosis_first_priority(tmp_path: Path, monkeypatch: Any) -> None:
    """Step 6, 6.4: the cookbook's handoff feeds the loop. A round with no task ("improve:" alone) hands the fixer the
    handoff's first top priority, from each shape HALO writes; a named failure is used as named; no handoff stops it."""
    import json

    import improvement_loop as diagnosis
    import improvement_loop_workflow as loop
    import pytest

    def handoff(priorities: Any) -> str:
        block = json.dumps({"top_priorities": priorities})
        return f"## Executive summary\nok\n\n## Machine-readable summary\n```json\n{block}\n```\n"

    assert diagnosis.handoff_priorities(handoff(["Fix the plan", "Second"])) == ["Fix the plan", "Second"]
    assert diagnosis.handoff_priorities(handoff([{"id": "A", "description": "Fix the plan"}])) == ["Fix the plan"]
    assert diagnosis.handoff_priorities(handoff([{"recommendation": "Fix the plan"}])) == ["Fix the plan"]
    escaped = tmp_path / "escaped.md"
    escaped.write_text(json.dumps(handoff(["Fix the plan"]))[1:] + "}", encoding="utf-8")
    assert diagnosis.handoff_priorities(diagnosis.read_handoff(escaped)) == ["Fix the plan"], "a JSON-escaped handoff"
    with pytest.raises(ValueError):
        diagnosis.handoff_priorities(handoff([]))

    path = tmp_path / "handoff.md"
    monkeypatch.setattr(diagnosis, "HANDOFF_PATH", path)
    with pytest.raises(FileNotFoundError):
        loop.round_task("improve:")
    path.write_text(handoff([{"description": "Make the plan an approval card"}, "Second"]), encoding="utf-8")
    assert loop.round_task("improve: the plan comes back as prose") == "the plan comes back as prose"

    monkeypatch.setattr(loop, "_changed_paths", lambda: (set(), set()))
    client = ScriptedChatClient(["Done."])

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            workflow = loop.create_workflow(agent, loop.build_coder(ScriptedChatClient([])), None, checks=[[sys.executable, "-c", "print('ok')"]])
            return (await workflow.run("improve:")).get_request_info_events()

    [review] = asyncio.run(_go())
    sent = " ".join(m.text for m in client.calls[0]["messages"])
    assert "TASK: Make the plan an approval card" in sent, "the fixer got the handoff's first priority"
    assert "Second" in sent, "with the whole handoff as its evidence"
    assert review.data.passed is True


def test_maf_tool_call_limits_stop_a_repeating_call() -> None:
    """Step 4, 4.3: MAF's tool-call settings are on his client (one call at a time, detailed errors, a call cap and a
    time cap per pass). Round 1's fault, the same finished todo completed again and again, now stops at the cap."""
    from agent_framework import AgentModeProvider, set_agent_mode

    call = Content.from_function_call(call_id="t", name="todos_complete", arguments={"items": [{"id": 2, "reason": "x"}]})
    client = ScriptedChatClient([call] * 200)

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            config = client.function_invocation_configuration
            assert {k: config[k] for k in steward.TOOL_CALLS} == steward.TOOL_CALLS, "the settings are on his client"
            session = agent.create_session()
            modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
            set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
            return await agent.run("Finish the todo.", session=session)

    asyncio.run(_go())
    cap = steward.TOOL_CALLS["max_function_calls"]
    assert len(client.calls) <= cap + 2, f"{len(client.calls)} model calls: the repeat was not stopped at {cap}"
    assert steward.TOOL_CALLS["allow_concurrent_invocation"] is False


def test_steward_and_his_team_send_their_own_ollama_window_and_keep_alive() -> None:
    """Step 4, 4.2: Steward, CodeExplorer and WebResearchAgent send num_ctx and keep_alive on every call (MAF's
    OllamaChatOptions), so his window never rests on the server's default; his compaction budget is that window; the
    fixer's own 32K window wins over his."""
    from agent_framework import BackgroundAgentsProvider

    import improvement_loop_workflow as loop

    def lookup(topic: str) -> str:
        """A stand-in web tool."""
        return topic

    client = ScriptedChatClient(["Hello."])

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            [team] = [p for p in agent.context_providers if isinstance(p, BackgroundAgentsProvider)]
            await agent.run("Say hello.", session=agent.create_session())
            fixer = loop.build_coder(ScriptedChatClient([]))
            return team, fixer

    team, fixer = asyncio.run(_go())
    wanted = {"num_ctx": 65_536, "keep_alive": "30m"}
    assert steward.OLLAMA_OPTIONS == wanted
    assert {k: client.calls[0]["options"].get(k) for k in wanted} == wanted, "his calls carry them"
    assert {k: team._agents["codeexplorer"].default_options.get(k) for k in wanted} == wanted
    research = steward._build_web_research_agent(client, lookup)
    assert {k: research.default_options.get(k) for k in wanted} == wanted
    assert fixer.default_options["num_ctx"] == loop.FIXER_CONTEXT and fixer.default_options["keep_alive"] == "30m"
    assert steward._STEWARD_CONTEXT == wanted["num_ctx"], "the compaction budget is the same window"


def test_a_turn_does_not_end_while_a_background_agent_still_runs() -> None:
    """Step 4, 4.4: MAF's background_tasks_running in his harness loop. A turn that started CodeExplorer does not end
    while the task still runs: the loop reminds him which task (background_tasks_running_message), he waits for it,
    and the loop stops once no task runs."""
    from agent_framework import Agent, AgentModeProvider, BackgroundAgentsProvider, set_agent_mode

    start = Content.from_function_call(
        call_id="s1",
        name="background_agents_start_task",
        arguments={"agent_name": "CodeExplorer", "input": "Explore harness/.", "description": "Explore harness"},
    )
    wait = Content.from_function_call(call_id="w1", name="background_agents_wait_for_first_completion", arguments={"task_ids": [1]})

    async def _go() -> tuple[ScriptedChatClient, Any]:
        finish = asyncio.Event()

        class Steward(ScriptedChatClient):
            """Lets CodeExplorer finish only once the loop has told him a task still runs."""

            def _inner_get_response(self, *, messages: Sequence[Message], **kwargs: Any) -> Any:
                if any("background task(s) running" in (m.text or "") for m in messages):
                    finish.set()
                return super()._inner_get_response(messages=messages, **kwargs)

        class Explorer(ScriptedChatClient):
            """CodeExplorer's model, still busy until the gate opens."""

            def _inner_get_response(self, **kwargs: Any) -> Any:
                reply = super()._inner_get_response(**kwargs)

                async def _later() -> ChatResponse:
                    await finish.wait()
                    return await reply

                return _later()

        client = Steward([start, "Started CodeExplorer.", wait, "CodeExplorer is done."])
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            [team] = [p for p in agent.context_providers if isinstance(p, BackgroundAgentsProvider)]
            team._agents["codeexplorer"] = Agent(client=Explorer(["harness/ holds the steps."]), name="CodeExplorer")
            async with agent:
                session = agent.create_session()
                modes = next(p for p in agent.context_providers if isinstance(p, AgentModeProvider))
                set_agent_mode(session, "execute", source_id=modes.source_id, available_modes=modes.available_modes)
                await agent.run("Ask CodeExplorer what harness/ holds.", session=session)
                return client, session.state[team.source_id]

    client, state = asyncio.run(_go())
    assert len(client.calls) == 4, f"{len(client.calls)} model calls: the turn ended while CodeExplorer still ran"
    reminder = " ".join(m.text or "" for m in client.calls[2]["messages"])
    assert "#1 (CodeExplorer): Explore harness" in reminder, "the loop names the running task"
    assert [task["status"] for task in state["tasks"]] == ["completed"], "and stops once none runs"


def test_his_skills_are_discovered_once_per_build_not_every_turn(monkeypatch: Any) -> None:
    """Step 4, 4.5: MAF's CachingSkillsSource wraps his skills source, so a second turn on the same agent reads the
    cached list instead of walking the skill files (and re-listing SecondBrain's skills) again."""
    discoveries: list[int] = []
    discover = steward.FileSkillsSource.get_skills

    async def counted(self: Any, context: Any) -> Any:
        discoveries.append(1)
        return await discover(self, context)

    monkeypatch.setattr(steward.FileSkillsSource, "get_skills", counted)
    client = ScriptedChatClient(["Hello.", "Hello again."])

    async def _go() -> None:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            async with agent:
                session = agent.create_session()
                await agent.run("Hello", session=session)
                await agent.run("Hello again", session=session)

    asyncio.run(_go())
    assert len(client.calls) == 2, "two turns ran"
    assert all(skill in str(call["options"].get("instructions") or "") for call in client.calls for skill in SKILLS)
    assert len(discoveries) == 1, f"the skill files were discovered {len(discoveries)} times in two turns"


def test_reading_a_skill_asks_no_card_and_running_its_script_still_does() -> None:
    """Step 4, 4.5: MAF's SkillsProvider.read_only_tools_auto_approval_rule approves load_skill and
    read_skill_resource (they only read a skill), while run_skill_script, which runs code, keeps its card."""
    read = Content.from_function_call(
        call_id="s1",
        name="read_skill_resource",
        arguments={"skill_name": "code-review", "resource_name": "references/review-checklist.md"},
    )
    client, _, response = run_steward([read, "Read it."], "Read the code-review checklist.", mode="execute")
    assert not approval_requests(response), "reading a skill's resource asked a card"
    assert any("Code review checklist" in r for r in function_results(client.calls[1])), "the resource was read"

    script = Content.from_function_call(
        call_id="s2", name="run_skill_script", arguments={"skill_name": "codebase-map", "script_name": "scripts/repo_map.py"}
    )
    client, _, response = run_steward([script], "Map the codebase.", mode="execute")
    assert [r.function_call.name for r in approval_requests(response)] == ["run_skill_script"]
    assert len(client.calls) == 1, "nothing ran before the approval"


def test_what_he_learns_in_one_conversation_is_in_front_of_him_in_the_next(tmp_path: Path) -> None:
    """Step 5 (5.1): MAF's MemoryContextProvider beside his history. After a turn, one call on his own client extracts
    a durable fact; a new conversation starts with it in front of him; within a conversation his history is intact."""
    client = ScriptedChatClient([
        "Noted.",
        '{"memories": [{"topic": "releases", "memory": "The release codename is Juniper."}]}',
        "You told me the codename.",
        '{"memories": []}',
        "Juniper.",
        '{"memories": []}',
    ])

    async def _go() -> None:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(
                stack, client=client, enable_shell=False, memory_store=steward.steward_memory_store(tmp_path / "memory")
            )
            first = agent.create_session()
            await agent.run("The release codename is Juniper.", session=first)
            await agent.run("What did I just tell you?", session=first)
            await agent.run("What is the release codename?", session=agent.create_session())

    asyncio.run(_go())

    def texts(call: int) -> str:
        return " ".join(m.text or "" for m in client.calls[call]["messages"])

    assert "durable memory" in texts(1), "after a turn, the extraction call on his own client"
    assert client.calls[1]["messages"][0].text == steward.MEMORY_EXTRACTION_PROMPT, "with his extraction rules"
    assert "harness's own messages" in steward.MEMORY_EXTRACTION_PROMPT and "the assistant itself" in steward.MEMORY_EXTRACTION_PROMPT
    assert "The release codename is Juniper." in texts(2) and "Noted." in texts(2), "his history within a conversation"
    assert "Juniper" in texts(4), "a new conversation starts with what he learned"
    [index] = (tmp_path / "memory").rglob("MEMORY.md")
    assert "codename is Juniper" in index.read_text(encoding="utf-8")


def test_the_memory_eval_recalls_in_a_new_conversation_what_the_first_one_saved() -> None:
    """Step 5 (5.3): evals.py memory runs two requests through his workflow (run_steward), each a new conversation, on
    one throwaway memory. What the first request's extraction saved is in front of him in the second, memory_recalled
    scores the recall, and his real memory folders are untouched."""
    import evals

    class Remembering(ScriptedChatClient):
        """His replies from the script; each extraction call (MAF's "durable memory" prompt) from its own list."""

        def __init__(self, replies: list[Any], extractions: list[str]) -> None:
            super().__init__(replies)
            self.extractions = list(extractions)

        def _inner_get_response(self, *, messages: Sequence[Message], **kwargs: Any) -> Any:
            if "durable memory" in " ".join(m.text or "" for m in messages):
                self.replies.insert(0, self.extractions.pop(0) if self.extractions else '{"memories": []}')
            return super()._inner_get_response(messages=messages, **kwargs)

    plan = '{"type": "approval", "questions": [{"message": "Note it."}], "steps": ["Note it"]}'
    done = Content.from_function_call(call_id="d1", name="todos_complete", arguments={"items": [{"id": 1, "reason": "noted"}]})
    fact = f"The sample project's next release is codenamed {evals.MEMORY_FACT}."
    client = Remembering(
        [plan, done, "Noted.", plan, done, f"It is {evals.MEMORY_FACT}."],
        ['{"memories": [{"topic": "releases", "memory": "%s"}]}' % fact],
    )
    real = [steward._WORKING_DIR / name for name in ("agent-memory", "agent-file-memory", "storage")]

    def listing() -> dict[Path, list[Path]]:
        return {folder: sorted(folder.rglob("*")) if folder.exists() else [] for folder in real}

    def text(call: dict[str, Any]) -> str:
        return " ".join(m.text or "" for m in call["messages"])

    before = listing()
    _, responses = asyncio.run(evals.memory_runs(client=client, enable_shell=False))
    assert evals.MEMORY_FACT not in evals.MEMORY_RECALL, "the recall request does not carry the fact itself"
    recall = next(c for c in client.calls if evals.MEMORY_RECALL in text(c) and "durable memory" not in text(c))
    assert evals.MEMORY_REMEMBER not in text(recall), "the second request is a new conversation"
    assert evals.MEMORY_FACT in text(recall), "what the first request saved is in front of him in the second"
    assert listing() == before, "his real memory folders are untouched"
    assert scored(evals.memory_recalled, evals.MEMORY_RECALL, list(responses[1].messages)).passed
    forgot = [Message(role="assistant", contents=[Content.from_text("I do not know the codename.")])]
    assert not scored(evals.memory_recalled, evals.MEMORY_RECALL, forgot).passed
    assert scored(evals.memory_recalled, evals.MEMORY_REMEMBER, forgot).passed, "not the recall case"


def test_without_a_memory_store_nothing_is_extracted_and_hosts_pass_his_store() -> None:
    """Step 5: automatic memory is the host's to pass (tests and other callers are untouched), and every host passes
    steward_memory_store(): the Agent tab's service, the improvement loop, the MCP door, the console and DevUI."""
    import inspect

    import console_app
    import devui_app
    import hosted
    import mcp_app

    client = ScriptedChatClient(["Hello."])

    async def _go() -> None:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=client, enable_shell=False)
            await agent.run("Say hello.", session=agent.create_session())

    asyncio.run(_go())
    assert len(client.calls) == 1, "no extraction call without a store"
    assert inspect.getsource(hosted).count("memory_store=steward_memory_store()") == 2, "his requests and the loop"
    for host in (mcp_app, console_app, devui_app):
        assert "memory_store=steward_memory_store()" in inspect.getsource(host), host.__name__


def test_the_mcp_doors_sessions_are_kept_on_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Step 5 (5.2): his MCP door keeps each session_id's session in MAF's FileSessionStore, so a session Manjuel
    continues survives a restart: a fresh store over the same folder reads it back."""
    from agent_framework import FileSessionStore

    import mcp_app

    built: list[Any] = []
    real = mcp_app.AgentState

    def recording(*args: Any, **kwargs: Any) -> Any:
        built.append(real(*args, **kwargs))
        return built[-1]

    monkeypatch.setattr(mcp_app, "MCP_SESSIONS_DIR", tmp_path / "mcp-sessions")
    monkeypatch.setattr(mcp_app, "AgentState", recording)

    async def _go() -> Any:
        async with AsyncExitStack() as stack:
            agent = await steward.build_steward_agent(stack, client=ScriptedChatClient([]), enable_shell=False)
            mcp_app.build_mcp_app(agent)
            [state] = built
            session = await state.get_or_create_session("manjuel-1")
            session.state["marker"] = "kept"
            await state.set_session("manjuel-1", session)
            return await FileSessionStore(tmp_path / "mcp-sessions").get("manjuel-1")

    restored = asyncio.run(_go())
    assert restored is not None and restored.state.get("marker") == "kept", "a fresh store reads the session back"


def test_the_diagnosis_traces_the_small_asks_and_a_plain_question_through_his_workflow(monkeypatch: Any) -> None:
    """Step 6: the diagnosis traced a bare agent on five old read-only questions, an agent nobody uses. It runs the small
    asks and one plain question through his workflow (evals.run_steward) as evals.py small runs them, through the one
    shared runner: the same approvals, the discount bug planted for the discount ask only, the sample project put back,
    each ask in its own trace span, and the harness described from the agent that ran."""
    import inspect
    from types import SimpleNamespace

    import agent_framework.observability as observability
    import evals
    import halo_traces
    import improvement_loop as diagnosis
    from agent_framework import AgentResponse, FileAccessProvider
    from opentelemetry.sdk.trace import TracerProvider

    module = steward._WORKING_DIR / "harness" / "steward" / "working" / "sample-project" / "inventory.py"
    before = module.read_bytes()
    ran: list[tuple[str, set[str], dict[str, Any], bool]] = []

    async def recorder(query: str, approve: set[str], **build: Any) -> Any:
        ran.append((query, set(approve), dict(build), b"(1 - discount_percent)" in module.read_bytes()))
        said = Message(role="assistant", contents=[Content.from_text(f"Answer {len(ran)}")])
        return SimpleNamespace(name="Steward"), AgentResponse(messages=[said])

    async def scores(agent: Any, asks: list[str], responses: list[Any]) -> Any:
        return SimpleNamespace(items=[SimpleNamespace(scores=[]) for _ in asks])

    provider = TracerProvider()
    serialize = diagnosis.serialize_agent_config
    monkeypatch.setattr(evals, "run_steward", recorder)
    monkeypatch.setattr(evals, "score_small_asks", scores)
    monkeypatch.setattr(halo_traces, "setup_halo_tracing", lambda path: None)
    monkeypatch.setattr(observability, "get_tracer", lambda *args, **kwargs: provider.get_tracer("test"))
    monkeypatch.setattr(diagnosis, "serialize_agent_config", lambda agent: {"described": agent.name})

    asks = diagnosis.traced_asks()
    assert asks == [*evals.SMALL_ASKS, diagnosis.PLAIN_QUESTION], "the small asks and one plain question"
    traces, harness, checks = asyncio.run(diagnosis.generate_traces(asks))
    assert [query for query, _, _, _ in ran] == asks, "each ask ran through run_steward"
    assert all(approve == set(FileAccessProvider._WRITE_TOOL_NAMES) for _, approve, _, _ in ran), "small_main's approvals"
    assert all(build == {"auto_approve_skill_scripts": True} for _, _, build, _ in ran)
    assert [planted for _, _, _, planted in ran] == [query == evals.SMALL_ASK_DISCOUNT for query in asks]
    assert module.read_bytes() == before, "the sample project is put back"
    assert [t.trace_label for t in traces] == ["trace-01", "trace-02", "trace-03", "trace-04"]
    assert [(t.question, t.answer) for t in traces] == [(q, f"Answer {i}") for i, q in enumerate(asks, 1)]
    assert len({t.trace_id for t in traces}) == 4 and "0" * 32 not in {t.trace_id for t in traces}, "a span per ask"
    assert harness == {"described": "Steward"} and len(checks) == 4
    assert "run_small_asks(SMALL_ASKS)" in inspect.getsource(evals.small_main), "define once: small_main runs it too"
    assert "build_steward_agent" not in inspect.getsource(diagnosis.generate_traces), "no bare agent"

    import steward_workflow as wf

    async def _built() -> tuple[Any, Any]:
        async with AsyncExitStack() as stack:
            agent, workflow = await wf.build_steward(stack, client=ScriptedChatClient([]), enable_shell=False)
            return agent, workflow.as_agent(name="Steward")

    agent, ran_as = asyncio.run(_built())
    config = serialize(ran_as)
    assert config["system_prompt"] == agent.default_options.get("instructions"), "the agent his workflow ran"
    assert {wf.PLAN_STEP, wf.EXECUTE_STEP, wf.COMMIT_STEP} <= set(config["tool_policy"]["workflow_steps"])


def test_the_diagnosis_reads_its_feedback_file_and_adds_each_failing_check(tmp_path: Path) -> None:
    """Step 6: the feedback is diagnosis_feedback.json, keyed by the ask, not code; an ask with no entry gets none. Each
    failing small-ask check on a traced run is one more item (source_type eval_checks) carrying the check's reason."""
    import json
    from types import SimpleNamespace

    import improvement_loop as diagnosis

    asks = diagnosis.traced_asks()
    entries = json.loads(diagnosis.FEEDBACK_PATH.read_text(encoding="utf-8"))
    assert [entry["ask"] for entry in entries] == asks, "one entry per traced ask"
    [plain] = [entry for entry in entries if entry["ask"] == diagnosis.PLAIN_QUESTION]
    assert "it does not become a plan, a clarification or an approval card" in plain["summary"]

    traces = [diagnosis.TraceRecord(f"t{i}", f"trace-{i:02d}", q, "a", "workflow") for i, q in enumerate([*asks, "Unlisted?"], 1)]
    edited = tmp_path / "feedback.json"
    edited.write_text(json.dumps([{
        "ask": asks[0], "summary": "Edited.", "required_observations": ["r"], "prohibited_claims": ["p"], "theme": "t",
    }]), encoding="utf-8")
    [item] = diagnosis.generate_human_feedback(traces, edited)
    assert (item["trace_id"], item["summary"], item["source_type"]) == ("t1", "Edited.", "human_feedback"), "the file is read"
    assert [i["question"] for i in diagnosis.generate_human_feedback(traces)] == asks, "the unlisted ask gets none"

    def score(name: str, passed: bool, reason: str) -> Any:
        return SimpleNamespace(name=name, passed=passed, sample={"reason": reason})

    items = [
        SimpleNamespace(scores=[score("plan_is_approval", False, "No plan card: 'Proceed?'"), score("answer_on_topic", True, "On topic.")]),
        SimpleNamespace(scores=[score("commit_by_tool", True, "Not this case.")]),
        *[SimpleNamespace(scores=[]) for _ in range(3)],
    ]
    [check] = diagnosis.eval_check_feedback(traces, items)
    assert (check["source_type"], check["trace_id"], check["theme"]) == ("eval_checks", "t1", "plan_is_approval")
    assert "No plan card: 'Proceed?'" in check["summary"], "with the check's reason"
    assert set(check) == set(item), "the feedback shape"


def test_the_diagnosis_drops_background_mcp_spans_and_keeps_every_span_of_an_ask(tmp_path: Path, monkeypatch: Any) -> None:
    """Step 6: background MCP housekeeping (pings, tools/list, discover, initialize, their POSTs) outnumbered the request
    spans three to one in the trace file and steered the handoff to trace attributes. Those traces are dropped before
    HALO's context is written; every span of a traced ask's trace is kept. Children are written before their roots."""
    import json

    import improvement_loop as diagnosis

    def span(trace: str, span_id: str, name: str, parent: str = "") -> str:
        return json.dumps({"trace_id": trace, "span_id": span_id, "parent_span_id": parent, "name": name})

    lines = [
        span("a1", "3", "MCP send resources/read", "2"), span("a1", "4", "POST", "3"),
        span("a1", "5", "MCP send ping", "1"), span("a1", "2", "invoke_agent.invoke_agent Steward", "1"),
        span("a1", "1", "Steward improvement loop trace-01"),
        span("p", "7", "POST", "6"), span("p", "6", "MCP send ping"),
        span("l", "10", "POST", "9"), span("l", "9", "MCP send tools/list", "8"), span("l", "8", "tools/list"),
        span("d", "11", "MCP send server/discover"), span("i", "12", "MCP send initialize"), span("h", "13", "POST"),
        span("w", "14", "workflow.build"),
    ]
    kept = diagnosis.drop_background_spans(lines, {"a1"})
    assert [json.loads(line)["span_id"] for line in kept] == ["3", "4", "5", "2", "1", "14"]

    monkeypatch.setattr(diagnosis, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(diagnosis, "HALO_TRACE_PATH", tmp_path / "traces.jsonl")
    (tmp_path / "traces.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    check = {
        "feedback_id": "eval-trace-01-plan_is_approval", "trace_id": "a1", "trace_label": "trace-01", "question": "q",
        "source_type": "eval_checks", "theme": "plan_is_approval", "summary": "No plan card.",
        "required_observations": [], "prohibited_claims": [],
    }
    context = {
        "traces": [{"trace_id": "a1"}], "human_feedback": [check], "llm_feedback": [], "eval_suite": [],
        "gate_result": {"total": 0, "passed": 0, "failed": 0, "rows": []},
        "agent_config": {"version": "x", "system_prompt": "", "model_settings": {}, "tool_policy": {}, "eval_metadata": {}},
    }
    written = [json.loads(line) for line in diagnosis.write_halo_optimization_context(context).read_text(encoding="utf-8").splitlines()]
    assert [s["span_id"] for s in written[:6]] == ["3", "4", "5", "2", "1", "14"], "the context carries no housekeeping"
    [verdict] = [s for s in written if s.get("attributes", {}).get("optimizer.signal_source") == "eval_checks"]
    assert verdict["name"] == "eval_checks.verdict"
    assert verdict["attributes"]["feedback.summary"] == "No plan card."
