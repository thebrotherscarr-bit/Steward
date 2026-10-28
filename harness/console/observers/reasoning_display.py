# Copyright (c) Microsoft. All rights reserved.

"""Reasoning display observer for showing thinking content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.markup import escape

from .base import ConsoleObserver

if TYPE_CHECKING:
    from agent_framework import Agent, Content

    from ..state_driver import IUXStateDriver


class ReasoningDisplayObserver(ConsoleObserver):
    """Displays reasoning/thinking content from the agent.

    Some models (like o1) provide reasoning steps that show their
    internal thought process. This observer displays them with a 💭 prefix
    in a dimmed style.

    Local models (e.g. Ollama) stream reasoning one token per update, so chunks
    are buffered and shown as one block when the thought ends: on the first
    update without reasoning (before its tool call or text is drawn) or when
    the stream completes.
    """

    def __init__(self) -> None:
        self._buffer: list[str] = []

    def _flush(self, ux: IUXStateDriver) -> None:
        thought = "".join(self._buffer).strip()
        self._buffer.clear()
        if thought:
            ux.append_info_line(f"💭 {escape(thought)}", "dim")

    async def on_response_update(
        self,
        ux: IUXStateDriver,
        update: Any,
        agent: Agent,
        session: Any,
    ) -> None:
        """Flush buffered reasoning once an update carries no more of it."""
        contents = getattr(update, "contents", None) or []
        if self._buffer and not any(self._extract_reasoning(c) for c in contents):
            self._flush(ux)

    async def on_stream_complete(
        self,
        ux: IUXStateDriver,
        agent: Agent,
        session: Any,
    ) -> list | None:
        """Flush any reasoning left when the stream ends."""
        self._flush(ux)
        return None

    async def on_content(
        self,
        ux: IUXStateDriver,
        content: Content,
        agent: Agent,
        session: Any,
    ) -> None:
        """Display reasoning content.

        Args:
            ux: The UX state driver for UI updates.
            content: The content item to check for reasoning.
            agent: The AI agent.
            session: The agent session.
        """
        reasoning_text = self._extract_reasoning(content)
        if reasoning_text:
            self._buffer.append(reasoning_text)

    def _extract_reasoning(self, content: Content) -> str | None:
        """Extract reasoning text from content.

        Args:
            content: The content item to extract reasoning from.

        Returns:
            The reasoning text, or None if no reasoning is present.
        """
        # Check for reasoning content type
        if hasattr(content, "type") and content.type in {"text_reasoning", "reasoning"}:
            if hasattr(content, "text"):
                return content.text
            content_attr = getattr(content, "content", None)
            if content_attr:
                return str(content_attr)

        # Check for reasoning attribute
        reasoning = getattr(content, "reasoning", None)
        if reasoning is not None:
            if isinstance(reasoning, str):
                return reasoning
            if hasattr(reasoning, "text"):
                return reasoning.text

        # Check for thinking attribute (alternative name)
        thinking = getattr(content, "thinking", None)
        if thinking is not None:
            if isinstance(thinking, str):
                return thinking
            if hasattr(thinking, "text"):
                return thinking.text

        return None
