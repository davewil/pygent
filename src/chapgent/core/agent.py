from __future__ import annotations

from collections.abc import AsyncIterator

from chapgent.core.cache import ToolCache
from chapgent.core.cancellation import CancellationToken
from chapgent.core.loop import DEFAULT_MAX_ITERATIONS, LoopEvent, conversation_loop
from chapgent.core.permissions import PermissionManager
from chapgent.core.providers import LLMProvider
from chapgent.session.models import Message, Session
from chapgent.tools.registry import ToolRegistry


class Agent:
    """Main agent orchestrator.

    Attributes:
        provider: The LLM provider for completions.
        tools: Registry of available tools.
        permissions: Permission manager for tool execution.
        session: The current conversation session.
        tool_cache: Cache for tool results.
        system_prompt: Optional system prompt to prepend to conversations.
        max_iterations: Maximum iterations per run (default: 50).
        max_tokens: Maximum total tokens per run (None = unlimited).
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        permissions: PermissionManager,
        session: Session,
        tool_cache: ToolCache | None = None,
        system_prompt: str | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_tokens: int | None = None,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.permissions = permissions
        self.session = session
        self.tool_cache = tool_cache or ToolCache()
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self._cancellation_token: CancellationToken | None = None

    def cancel(self, reason: str | None = None) -> None:
        """Request cancellation of the current run.

        This method is safe to call from any thread or coroutine.
        The agent will exit gracefully after the current operation completes.

        Args:
            reason: Optional human-readable reason for cancellation.
        """
        if self._cancellation_token is not None:
            self._cancellation_token.cancel(reason)

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested.

        Returns:
            True if cancel() was called during the current run.
        """
        return self._cancellation_token is not None and self._cancellation_token.is_cancelled

    async def run(self, user_message: str) -> AsyncIterator[LoopEvent]:
        """Run the agent with a user message.

        Args:
            user_message: The user's input message.

        Yields:
            LoopEvent instances for each step of the conversation.
        """
        # Create a fresh cancellation token for this run
        self._cancellation_token = CancellationToken()

        # Add user message to session
        msg = Message(role="user", content=user_message)
        self.session.messages.append(msg)

        try:
            # Call conversation_loop with system prompt, limits, and cancellation token
            async for event in conversation_loop(
                self,
                self.session.messages,
                self.system_prompt,
                max_iterations=self.max_iterations,
                max_tokens=self.max_tokens,
                cancellation_token=self._cancellation_token,
            ):
                yield event
        finally:
            # Clear the token after run completes
            self._cancellation_token = None
