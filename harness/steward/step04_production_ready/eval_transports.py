"""The eval runner's transports (evals.py ``--transport``): an asks set's case driven against a running host.

``in-process`` (the default) runs Steward's workflow in evals.py's own process (run_steward), with no transport. The
two others send the same ask to a host already running on this PC and answer its cards over the wire, so a set scores
the harness as a client sees it:

* ``responses``: hosted.py on http://127.0.0.1:43120 (MAF's Responses host). One streamed ``POST /responses`` per
  round; a card is an ``mcp_approval_request`` output item, answered by an ``mcp_approval_response`` on the next
  round's input with ``previous_response_id``, as SecondBrain's Agent tab does (worlds/jesster
  secondbrain/electron/agent/steward.cjs, ``turn``).
* ``ag-ui``: ag_ui_app.py on http://127.0.0.1:43122/ (MAF's AG-UI package). One streamed ``POST /`` per round; the
  cards are the interrupts of the round's RUN_FINISHED, answered by a new run on the same threadId with
  ``resume: [{"interruptId", "status": "resolved", "payload": {"approved"}}]`` and ``forwardedProps: {"checkpointId"}``
  (ag_ui_app.py's docstring; test_the_ag_ui_host_streams_the_workflow_and_raises_a_write_card_as_an_interrupt).

The approval policy is the caller's (evals.card_approved): the plan, the writes and the sample project's pytest only.
What comes back is turned into the Messages the in-process run gives (function_approval_request on the turn, the
answer as the user's function_approval_response, tool calls and results, his words as assistant text named for their
step where the transport says it), so the same checks score it. Each case's clock (CaseClock) records the time to the
first text or reasoning event, the total time, each card and whether its resume went through, and the stream's
errors; evals.py writes them into the history as ``timings``.

A stream that drops, a host that refuses a resume (a dropped AG-UI checkpoint) or answers with an error ends the case
with a reason (TransportFailure), never a crash: the case is scored on what came back, and fails run_completed.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from agent_framework import AgentResponse, Content, Message

TRANSPORTS = ("in-process", "responses", "ag-ui")
RESPONSES_URL = f"http://127.0.0.1:{os.environ.get('STEWARD_PORT', '43120')}"
AG_UI_URL = f"http://127.0.0.1:{os.environ.get('STEWARD_AG_UI_PORT', '43122')}/"
# The streamed text and reasoning events each protocol sends (the first one starts first_event_s).
RESPONSES_TEXT_EVENTS = (
    "response.output_text.delta", "response.reasoning_summary_text.delta", "response.reasoning_text.delta",
)
AG_UI_TEXT_EVENTS = ("TEXT_MESSAGE_CONTENT", "REASONING_MESSAGE_CONTENT", "THINKING_TEXT_MESSAGE_CONTENT")
# A model turn can be quiet for minutes (a local model thinking); a stream with no byte for this long is a drop.
READ_TIMEOUT_S = 900.0
# Set by the tests: an httpx transport (httpx.ASGITransport over a fake host) in place of the network.
HTTP_TRANSPORT: httpx.AsyncBaseTransport | None = None


@dataclass
class CaseClock:
    """One case's transport record: when it began, its first text or reasoning event, each card (its tool, the answer,
    whether the resume went through) and the stream's errors."""

    transport: str = "in-process"
    started: float = field(default_factory=time.monotonic)
    first_event: float | None = None
    ended: float | None = None
    cards: list[dict[str, Any]] = field(default_factory=list)
    stream_errors: list[str] = field(default_factory=list)

    def text(self) -> None:
        """A text or reasoning event arrived (only the first one is kept)."""
        if self.first_event is None:
            self.first_event = time.monotonic()

    def card(self, name: str, approved: bool) -> dict[str, Any]:
        """A card answered; its ``resumed`` is set when the run that carried the answer comes back."""
        entry = {"name": name, "approved": approved, "resumed": None}
        self.cards.append(entry)
        return entry

    def timings(self) -> dict[str, Any]:
        """The history's ``timings`` for this case (seconds, rounded to 0.01; None when there was no text event)."""
        end = self.ended if self.ended is not None else time.monotonic()
        return {
            "transport": self.transport,
            "first_event_s": None if self.first_event is None else round(self.first_event - self.started, 2),
            "total_s": round(end - self.started, 2),
            "cards": len(self.cards),
            "cards_resumed": sum(card["resumed"] is True for card in self.cards),
            "card_log": [dict(card) for card in self.cards],
            "stream_errors": list(self.stream_errors),
        }


class TransportFailure(RuntimeError):
    """A case the transport could not finish: a dropped stream, a refused resume, an error event, a host not up."""


def _client() -> httpx.AsyncClient:
    timeout = httpx.Timeout(connect=10.0, read=READ_TIMEOUT_S, write=30.0, pool=10.0)
    if HTTP_TRANSPORT is not None:
        return httpx.AsyncClient(transport=HTTP_TRANSPORT, timeout=timeout, base_url="http://fake-host")
    return httpx.AsyncClient(timeout=timeout)


async def _sse(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """The JSON events of a Server-Sent Events stream (``data:`` lines; comments and keepalives skipped)."""
    data: list[str] = []
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
            continue
        if line.strip() == "" and data:
            block, data = "\n".join(data), []
            try:
                event = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event
    if data:
        try:
            event = json.loads("\n".join(data))
        except json.JSONDecodeError:
            return
        if isinstance(event, dict):
            yield event


async def _stream(client: httpx.AsyncClient, url: str, body: dict[str, Any], clock: CaseClock, what: str) -> list[dict[str, Any]]:
    """One streamed POST's events. A host that does not answer, or answers with an HTTP error, is a TransportFailure."""
    events: list[dict[str, Any]] = []
    try:
        async with client.stream("POST", url, json=body, headers={"Accept": "text/event-stream"}) as response:
            if response.status_code >= 400:
                text = (await response.aread()).decode("utf-8", errors="replace")
                raise TransportFailure(f"{what}: HTTP {response.status_code}: {text.strip()[:200]}")
            async for event in _sse(response):
                events.append(event)
    except httpx.HTTPError as error:
        clock.stream_errors.append(f"{what}: {type(error).__name__}: {error}"[:300])
        if not events:
            raise TransportFailure(f"{what}: the host at {url} did not answer ({type(error).__name__})") from error
    return events


def _content_text(item: dict[str, Any]) -> str:
    return "".join(str(part.get("text") or "") for part in item.get("content") or [] if isinstance(part, dict))


def _call_content(call: dict[str, Any], fallback_id: str) -> Content:
    arguments = call.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            arguments = {"arguments": arguments}
    return Content.from_function_call(
        call_id=str(call.get("call_id") or fallback_id), name=str(call.get("name") or ""), arguments=arguments or {},
    )


def _drop_carded_calls(messages: list[Message], cards: list[Content]) -> list[Message]:
    """A call that waited on a card is in the run as its card, as in-process (the approved call rides on the answer):
    the tool call a transport also streams for it is left out (same call id, or same tool and arguments)."""
    ids = {card.function_call.call_id for card in cards}
    same = {(card.function_call.name, json.dumps(card.function_call.parse_arguments() or {}, sort_keys=True)) for card in cards}
    kept: list[Message] = []
    for message in messages:
        contents = [
            c for c in message.contents or []
            if not (c.type == "function_call" and (
                c.call_id in ids or (c.name, json.dumps(c.parse_arguments() or {}, sort_keys=True)) in same
            ))
        ]
        if contents:
            kept.append(Message(role=message.role, contents=contents, author_name=message.author_name))
    return kept


# <responses>
def responses_messages(items: list[dict[str, Any]]) -> tuple[list[Message], list[Content], list[dict[str, Any]]]:
    """A Responses round's output items as Messages, its cards (function_approval_request contents, each with the
    mcp_approval_request's id) and any request_info question (which an eval cannot answer)."""
    messages: list[Message] = []
    cards: list[Content] = []
    questions: list[dict[str, Any]] = []
    for item in items:
        kind = item.get("type")
        if kind == "message":
            if text := _content_text(item):
                messages.append(Message(role="assistant", contents=[Content.from_text(text)]))
        elif kind == "reasoning":
            # The words his steps stream as intermediate output come as reasoning (summary_text), as AG-UI's come as
            # REASONING_*; in-process they are his assistant text, and so they are here.
            text = "".join(str(part.get("text") or "") for part in item.get("summary") or [] if isinstance(part, dict))
            if text := text or _content_text(item):
                messages.append(Message(role="assistant", contents=[Content.from_text(text)]))
        elif kind == "function_call" and item.get("name") == "request_info":
            questions.append(item)
        elif kind == "function_call":
            messages.append(Message(role="assistant", contents=[_call_content(item, str(item.get("id") or ""))]))
        elif kind == "function_call_output":
            messages.append(Message(role="tool", contents=[
                Content.from_function_result(call_id=str(item.get("call_id") or ""), result=str(item.get("output") or ""))
            ]))
        elif kind == "mcp_approval_request":
            call = _call_content({**item, "call_id": item.get("id")}, str(item.get("id") or ""))
            card = Content.from_function_approval_request(id=str(item.get("id") or ""), function_call=call)
            cards.append(card)
            messages.append(Message(role="assistant", contents=[card]))
    return _drop_carded_calls(messages, cards), cards, questions


async def _responses_round(client: httpx.AsyncClient, base: str, body: dict[str, Any], clock: CaseClock, what: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One round: the final response (response.completed / failed / incomplete) and its output items, each once."""
    events = await _stream(client, f"{base.rstrip('/')}/responses", body, clock, what)
    final: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    for event in events:
        kind = str(event.get("type") or "")
        if kind in RESPONSES_TEXT_EVENTS and event.get("delta"):
            clock.text()
        elif kind == "response.output_item.done" and isinstance(event.get("item"), dict):
            items.append(event["item"])
        elif kind == "error":
            message = event.get("message") or (event.get("error") or {}).get("message") or "stream error"
            clock.stream_errors.append(f"{what}: {message}"[:300])
            final = {"status": "failed", "error": {"message": message}}
        if isinstance(event.get("response"), dict) and kind in ("response.completed", "response.failed", "response.incomplete"):
            final = event["response"]
    if final is None:
        clock.stream_errors.append(f"{what}: the stream ended without a final response")
        raise TransportFailure(f"{what}: the Responses stream ended without a final response")
    seen = {json.dumps(item, sort_keys=True, default=str) for item in items}
    ids = {item.get("id") for item in items if item.get("id")}
    for item in final.get("output") or []:  # anything the stream did not hand over item by item (steward.cjs)
        if isinstance(item, dict) and item.get("id") not in ids and json.dumps(item, sort_keys=True, default=str) not in seen:
            items.append(item)
    if final.get("status") == "failed" or final.get("error"):
        message = str((final.get("error") or {}).get("message") or "the turn failed")
        if not any(message in error for error in clock.stream_errors):
            clock.stream_errors.append(f"{what}: {message}"[:300])
        raise TransportFailure(f"{what}: {message}")
    return final, items


async def run_responses(
    query: str, answer: Callable[[Content], bool], clock: CaseClock, rounds: int, base: str = RESPONSES_URL,
) -> tuple[list[Message], str | None]:
    """The ask on the Responses host, its cards answered by ``answer``; the run's Messages and a failure reason."""
    messages: list[Message] = []
    body: dict[str, Any] = {"input": query, "stream": True}
    pending: list[dict[str, Any]] = []
    async with _client() as client:
        try:
            for round_ in range(rounds + 1):
                what = "the ask" if round_ == 0 else f"the answer to {', '.join(c['name'] for c in pending)}"
                try:
                    final, items = await _responses_round(client, base, body, clock, what)
                except TransportFailure:
                    for card in pending:
                        card["resumed"] = False
                    raise
                for card in pending:
                    card["resumed"] = True
                turn, cards, questions = responses_messages(items)
                messages += turn
                if questions:
                    raise TransportFailure("the host asked a request_info question the eval cannot answer")
                if not cards:
                    return messages, None
                if round_ == rounds:
                    return messages, f"the eval stopped answering cards after {rounds} rounds"
                answers = [card.to_function_approval_response(approved=answer(card.function_call)) for card in cards]
                pending = [clock.card(card.function_call.name, reply.approved) for card, reply in zip(cards, answers)]
                messages.append(Message(role="user", contents=answers))
                body = {
                    "input": [
                        {"type": "mcp_approval_response", "approval_request_id": card.id, "approve": bool(reply.approved)}
                        for card, reply in zip(cards, answers)
                    ],
                    "stream": True,
                    "previous_response_id": final.get("id"),
                }
        except TransportFailure as failure:
            return messages, str(failure)
        finally:
            clock.ended = time.monotonic()
    return messages, None
# </responses>


# <ag-ui>
def ag_ui_messages(events: list[dict[str, Any]], clock: CaseClock | None = None) -> tuple[list[Message], list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    """An AG-UI run's events as Messages (his words named for the step that streamed them), the interrupts of its
    RUN_FINISHED, the RUN_FINISHED event itself (None: the stream dropped) and its RUN_ERROR messages."""
    messages: list[Message] = []
    texts: dict[str, list[str]] = {}
    order: list[tuple[str, str | None]] = []  # (message id, step), in the order they started
    calls: dict[str, dict[str, Any]] = {}
    step: str | None = None
    finished: dict[str, Any] | None = None
    errors: list[str] = []
    slots: dict[str, int] = {}

    def flush_text(message_id: str) -> None:
        text = "".join(texts.get(message_id, []))
        if text and message_id in slots:
            messages[slots[message_id]] = Message(
                role="assistant", contents=[Content.from_text(text)], author_name=messages[slots[message_id]].author_name
            )

    for event in events:
        kind = str(event.get("type") or "")
        if kind in AG_UI_TEXT_EVENTS and event.get("delta") and clock is not None:
            clock.text()
        if kind == "STEP_STARTED":
            step = event.get("stepName") or step
        elif kind in ("TEXT_MESSAGE_START", "REASONING_MESSAGE_START", "THINKING_TEXT_MESSAGE_START"):
            message_id = str(event.get("messageId") or f"m{len(order)}")
            texts.setdefault(message_id, [])
            if message_id not in slots:
                slots[message_id] = len(messages)
                messages.append(Message(role="assistant", contents=[Content.from_text("")], author_name=step))
                order.append((message_id, step))
        elif kind in AG_UI_TEXT_EVENTS:
            message_id = str(event.get("messageId") or (order[-1][0] if order else "m0"))
            if message_id not in slots:
                slots[message_id] = len(messages)
                messages.append(Message(role="assistant", contents=[Content.from_text("")], author_name=step))
                order.append((message_id, step))
            texts.setdefault(message_id, []).append(str(event.get("delta") or ""))
            flush_text(message_id)
        elif kind == "TOOL_CALL_START":
            calls[str(event.get("toolCallId"))] = {"name": event.get("toolCallName"), "args": []}
        elif kind == "TOOL_CALL_ARGS":
            calls.setdefault(str(event.get("toolCallId")), {"name": None, "args": []})["args"].append(str(event.get("delta") or ""))
        elif kind == "TOOL_CALL_END":
            call_id = str(event.get("toolCallId"))
            call = calls.get(call_id) or {}
            if call.get("name") and call.get("name") != "request_info":
                messages.append(Message(role="assistant", contents=[
                    _call_content({"call_id": call_id, "name": call["name"], "arguments": "".join(call["args"]) or "{}"}, call_id)
                ]))
        elif kind == "TOOL_CALL_RESULT":
            call_id = str(event.get("toolCallId"))
            if (calls.get(call_id) or {}).get("name") != "request_info":
                messages.append(Message(role="tool", contents=[
                    Content.from_function_result(call_id=call_id, result=str(event.get("content") or ""))
                ]))
        elif kind == "RUN_ERROR":
            errors.append(str(event.get("message") or event.get("code") or "RUN_ERROR"))
        elif kind == "RUN_FINISHED":
            finished = event
    messages = [m for m in messages if m.text or any(c.type != "text" for c in m.contents or [])]
    outcome = (finished or {}).get("outcome") or {}
    interrupts = list(outcome.get("interrupts") or []) if outcome.get("type") == "interrupt" else []
    return messages, interrupts, finished, errors


def ag_ui_card(interrupt: dict[str, Any]) -> Content:
    """An interrupt as the card in-process runs see: a function_approval_request on the call it holds back."""
    meta = ((interrupt.get("metadata") or {}).get("agent_framework") or {})
    call = meta.get("function_call") or {"name": interrupt.get("message") or "request_info"}
    return Content.from_function_approval_request(
        id=str(interrupt.get("id") or ""), function_call=_call_content(call, str(interrupt.get("toolCallId") or interrupt.get("id") or "")),
    )


async def run_ag_ui(
    query: str, answer: Callable[[Content], bool], clock: CaseClock, rounds: int, url: str = AG_UI_URL,
) -> tuple[list[Message], str | None]:
    """The ask on the AG-UI host, its interrupts answered by ``answer``; the run's Messages and a failure reason. A
    resume the host refuses (RUN_ERROR, e.g. WORKFLOW_CHECKPOINT_LOAD_FAILED for a dropped checkpoint) marks its cards
    not resumed and ends the case with that reason."""
    thread = f"eval-{uuid.uuid4().hex[:12]}"
    messages: list[Message] = []
    body: dict[str, Any] = {
        "threadId": thread, "runId": f"{thread}-0", "messages": [{"id": f"{thread}-u", "role": "user", "content": query}],
    }
    pending: list[dict[str, Any]] = []
    target = url if HTTP_TRANSPORT is None else "/"
    async with _client() as client:
        try:
            for round_ in range(rounds + 1):
                what = "the ask" if round_ == 0 else f"the resume of {', '.join(c['name'] for c in pending)}"
                try:
                    events = await _stream(client, target, body, clock, what)
                    turn, interrupts, finished, errors = ag_ui_messages(events, clock)
                    cards = [ag_ui_card(interrupt) for interrupt in interrupts]
                    messages += _drop_carded_calls(turn, cards)
                    if errors:
                        clock.stream_errors.extend(f"{what}: {error}"[:300] for error in errors)
                        raise TransportFailure(f"{what}: RUN_ERROR: {errors[0]}")
                    if finished is None:
                        clock.stream_errors.append(f"{what}: the stream ended without RUN_FINISHED")
                        raise TransportFailure(f"{what}: the AG-UI stream ended without RUN_FINISHED")
                except TransportFailure:
                    for card in pending:
                        card["resumed"] = False
                    raise
                for card in pending:
                    card["resumed"] = True
                if not interrupts:
                    return messages, None
                if round_ == rounds:
                    return messages, f"the eval stopped answering cards after {rounds} rounds"
                answers = [card.to_function_approval_response(approved=answer(card.function_call)) for card in cards]
                messages += [Message(role="assistant", contents=[card]) for card in cards]
                messages.append(Message(role="user", contents=answers))
                pending = [clock.card(card.function_call.name, reply.approved) for card, reply in zip(cards, answers)]
                checkpoint = next(
                    (((i.get("metadata") or {}).get("agent_framework") or {}).get("checkpoint_id") for i in interrupts), None
                )
                body = {
                    "threadId": thread,
                    "runId": f"{thread}-{round_ + 1}",
                    "messages": [],
                    "resume": [
                        {"interruptId": interrupt.get("id"), "status": "resolved", "payload": {"approved": bool(reply.approved)}}
                        for interrupt, reply in zip(interrupts, answers)
                    ],
                    "forwardedProps": {"checkpointId": checkpoint} if checkpoint else {},
                }
        except TransportFailure as failure:
            return messages, str(failure)
        finally:
            clock.ended = time.monotonic()
    return messages, None
# </ag-ui>


async def run_over(transport: str, query: str, answer: Callable[[Content], bool], clock: CaseClock, rounds: int) -> tuple[AgentResponse[Any], str | None]:
    """The ask over ``transport`` (responses or ag-ui): the run as an AgentResponse, and the reason it failed (None)."""
    clock.transport = transport
    runner = {"responses": run_responses, "ag-ui": run_ag_ui}.get(transport)
    if runner is None:
        raise ValueError(f"no transport {transport!r}; the transports: {', '.join(TRANSPORTS)}")
    messages, failure = await runner(query, answer, clock, rounds)
    return AgentResponse(messages=messages), failure
