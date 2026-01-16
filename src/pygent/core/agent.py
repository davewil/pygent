from __future__ import annotations

from collections.abc import AsyncIterator

from pygent.core.loop import LoopEvent, conversation_loop
from pygent.core.permissions import PermissionManager
from pygent.core.providers import LLMProvider
from pygent.session.models import Message, Session
from pygent.tools.registry import ToolRegistry


class Agent:
    """Main agent orchestrator."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        permissions: PermissionManager,
        session: Session,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.permissions = permissions
        self.session = session

    async def run(self, user_message: str) -> AsyncIterator[LoopEvent]:
        # Add user message to session
        # Spec says just user_message: str.
        # We wrap it in a Message
        msg = Message(role="user", content=user_message)
        self.session.messages.append(msg)

        # Call conversation_loop
        async for event in conversation_loop(self, self.session.messages):
            yield event

            # If we wanted to persist incrementally, we'd do it here.
