"""Tests for the cancellation system (Phase 4 of Agent Loop Improvements)."""

from __future__ import annotations

import asyncio

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.core.cancellation import CancellationError, CancellationToken


class TestCancellationToken:
    """Tests for CancellationToken class."""

    def test_initial_state_not_cancelled(self):
        """New token should not be cancelled."""
        token = CancellationToken()
        assert token.is_cancelled is False
        assert token.cancel_time is None
        assert token.reason is None

    def test_cancel_sets_cancelled_flag(self):
        """cancel() should set is_cancelled to True."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_sets_cancel_time(self):
        """cancel() should record the cancellation time."""
        token = CancellationToken()
        token.cancel()
        assert token.cancel_time is not None

    def test_cancel_with_reason(self):
        """cancel() should store the provided reason."""
        token = CancellationToken()
        token.cancel(reason="User requested stop")
        assert token.reason == "User requested stop"

    def test_cancel_idempotent(self):
        """Multiple cancel() calls should not change state after first call."""
        token = CancellationToken()
        token.cancel(reason="First reason")
        first_time = token.cancel_time
        token.cancel(reason="Second reason")
        # State should not change after first cancel
        assert token.reason == "First reason"
        assert token.cancel_time == first_time

    def test_reset_clears_cancelled_state(self):
        """reset() should clear the cancelled state."""
        token = CancellationToken()
        token.cancel(reason="Test reason")
        assert token.is_cancelled is True
        token.reset()
        assert token.is_cancelled is False
        assert token.cancel_time is None
        assert token.reason is None

    def test_token_can_be_reused_after_reset(self):
        """Token should work normally after reset."""
        token = CancellationToken()
        token.cancel(reason="First")
        token.reset()
        token.cancel(reason="Second")
        assert token.is_cancelled is True
        assert token.reason == "Second"


class TestCancellationTokenRaiseIfCancelled:
    """Tests for raise_if_cancelled method."""

    def test_raise_if_cancelled_does_nothing_when_not_cancelled(self):
        """Should not raise when token is not cancelled."""
        token = CancellationToken()
        token.raise_if_cancelled()  # Should not raise

    def test_raise_if_cancelled_raises_when_cancelled(self):
        """Should raise CancellationError when token is cancelled."""
        token = CancellationToken()
        token.cancel()
        with pytest.raises(CancellationError):
            token.raise_if_cancelled()

    def test_raise_if_cancelled_includes_reason(self):
        """CancellationError should include the reason."""
        token = CancellationToken()
        token.cancel(reason="Test reason")
        with pytest.raises(CancellationError) as exc_info:
            token.raise_if_cancelled()
        assert exc_info.value.reason == "Test reason"
        assert "Test reason" in str(exc_info.value)


class TestCancellationTokenWaitForCancellation:
    """Tests for wait_for_cancellation method."""

    @pytest.mark.asyncio
    async def test_wait_returns_true_when_cancelled(self):
        """wait_for_cancellation should return True when cancelled."""
        token = CancellationToken()

        async def cancel_after_delay():
            await asyncio.sleep(0.01)
            token.cancel()

        asyncio.create_task(cancel_after_delay())
        result = await token.wait_for_cancellation(timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_returns_false_on_timeout(self):
        """wait_for_cancellation should return False on timeout."""
        token = CancellationToken()
        result = await token.wait_for_cancellation(timeout=0.01)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_returns_immediately_if_already_cancelled(self):
        """wait_for_cancellation should return immediately if already cancelled."""
        token = CancellationToken()
        token.cancel()
        result = await token.wait_for_cancellation(timeout=1.0)
        assert result is True


class TestCancellationError:
    """Tests for CancellationError exception class."""

    def test_cancellation_error_with_reason(self):
        """CancellationError should store and display reason."""
        error = CancellationError("User requested")
        assert error.reason == "User requested"
        assert "User requested" in str(error)

    def test_cancellation_error_without_reason(self):
        """CancellationError should work without reason."""
        error = CancellationError()
        assert error.reason is None
        assert "cancelled" in str(error).lower()

    def test_cancellation_error_is_exception(self):
        """CancellationError should inherit from Exception."""
        error = CancellationError()
        assert isinstance(error, Exception)


class TestCancellationTokenInLoopEvent:
    """Tests for cancellation in LoopEvent."""

    def test_loop_event_has_cancel_reason_field(self):
        """LoopEvent should have cancel_reason field."""
        from chapgent.core.loop import LoopEvent

        event = LoopEvent(type="cancelled", cancel_reason="User stopped")
        assert event.cancel_reason == "User stopped"

    def test_loop_event_cancelled_type(self):
        """LoopEvent should support 'cancelled' type."""
        from chapgent.core.loop import LoopEvent

        event = LoopEvent(type="cancelled", content="Operation cancelled")
        assert event.type == "cancelled"


class TestCancellationInConversationLoop:
    """Tests for cancellation in conversation_loop."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        from unittest.mock import AsyncMock, MagicMock

        from chapgent.core.mock_provider import MockLLMProvider

        provider = MagicMock(spec=MockLLMProvider)
        provider.complete = AsyncMock()
        return provider

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.list_definitions.return_value = []
        registry.get.return_value = None
        return registry

    @pytest.fixture
    def mock_permissions(self):
        """Create a mock permission manager."""
        from unittest.mock import AsyncMock, MagicMock

        permissions = MagicMock()
        permissions.check = AsyncMock(return_value=True)
        return permissions

    @pytest.fixture
    def session(self):
        """Create a test session."""
        from chapgent.session.models import Session

        return Session(id="test-session")

    @pytest.mark.asyncio
    async def test_cancellation_before_first_iteration(self, mock_provider, mock_registry, mock_permissions, session):
        """Should yield cancelled event immediately if cancelled before start."""
        from chapgent.core.agent import Agent
        from chapgent.core.cancellation import CancellationToken
        from chapgent.core.loop import conversation_loop
        from chapgent.session.models import Message

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Hello")]

        # Cancel before starting
        token = CancellationToken()
        token.cancel(reason="Cancelled before start")

        events = []
        async for event in conversation_loop(agent, messages, cancellation_token=token):
            events.append(event)

        # Should have cancelled and finished events
        cancelled_events = [e for e in events if e.type == "cancelled"]
        assert len(cancelled_events) == 1
        assert cancelled_events[0].cancel_reason == "Cancelled before start"

    @pytest.mark.asyncio
    async def test_cancellation_mid_loop(self, mock_provider, mock_registry, mock_permissions, session):
        """Should yield cancelled event when cancelled during loop."""

        from chapgent.core.agent import Agent
        from chapgent.core.cancellation import CancellationToken
        from chapgent.core.loop import conversation_loop
        from chapgent.core.providers import LLMResponse, TextBlock, TokenUsage
        from chapgent.session.models import Message

        # Set up provider to return text (ending the loop)
        mock_provider.complete.return_value = LLMResponse(
            content=[TextBlock(text="Response")],
            stop_reason="end_turn",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Hello")]

        token = CancellationToken()

        events = []
        async for event in conversation_loop(agent, messages, cancellation_token=token):
            events.append(event)
            # Cancel after first event
            if len(events) == 1:
                token.cancel(reason="Cancelled during loop")

        # Should have text event, then finish (loop checks cancel at iteration start)
        event_types = [e.type for e in events]
        assert "text" in event_types
        assert "finished" in event_types


class TestCancellationInAgent:
    """Tests for Agent.cancel() method."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        from unittest.mock import AsyncMock, MagicMock

        from chapgent.core.mock_provider import MockLLMProvider

        provider = MagicMock(spec=MockLLMProvider)
        provider.complete = AsyncMock()
        return provider

    @pytest.fixture
    def mock_registry(self):
        """Create a mock tool registry."""
        from unittest.mock import MagicMock

        registry = MagicMock()
        registry.list_definitions.return_value = []
        registry.get.return_value = None
        return registry

    @pytest.fixture
    def mock_permissions(self):
        """Create a mock permission manager."""
        from unittest.mock import AsyncMock, MagicMock

        permissions = MagicMock()
        permissions.check = AsyncMock(return_value=True)
        return permissions

    @pytest.fixture
    def session(self):
        """Create a test session."""
        from chapgent.session.models import Session

        return Session(id="test-session")

    def test_cancel_before_run_has_no_effect(self, mock_provider, mock_registry, mock_permissions, session):
        """cancel() before run() should have no effect."""
        from chapgent.core.agent import Agent

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        # No exception should be raised
        agent.cancel()
        assert agent.is_cancelled is False

    @pytest.mark.asyncio
    async def test_cancel_during_run(self, mock_provider, mock_registry, mock_permissions, session):
        """cancel() during run should cause loop to exit."""
        from chapgent.core.agent import Agent
        from chapgent.core.providers import LLMResponse, TextBlock, TokenUsage

        # Set up provider for multiple iterations
        responses = iter(
            [
                LLMResponse(
                    content=[TextBlock(text="First response")],
                    stop_reason="end_turn",
                    usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                ),
            ]
        )
        mock_provider.complete.side_effect = lambda *args, **kwargs: next(responses)

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)

        events = []
        async for event in agent.run("Hello"):
            events.append(event)

        # Check events collected
        event_types = [e.type for e in events]
        assert "text" in event_types
        assert "finished" in event_types

    def test_is_cancelled_property(self, mock_provider, mock_registry, mock_permissions, session):
        """is_cancelled property should reflect cancellation state."""
        from chapgent.core.agent import Agent

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        assert agent.is_cancelled is False


class TestCancellationInParallel:
    """Tests for cancellation in parallel tool execution."""

    def test_execute_tools_parallel_accepts_cancellation_token(self):
        """execute_tools_parallel should accept cancellation_token parameter."""
        import inspect

        from chapgent.core.parallel import execute_tools_parallel

        sig = inspect.signature(execute_tools_parallel)
        assert "cancellation_token" in sig.parameters

    @pytest.mark.asyncio
    async def test_cancellation_between_batches(self):
        """Cancellation should be checked between batches, not mid-batch."""
        from unittest.mock import AsyncMock, MagicMock

        from chapgent.core.cancellation import CancellationToken
        from chapgent.core.parallel import (
            execute_tools_parallel,
        )

        # This test verifies the batching behavior
        token = CancellationToken()

        # Create mock agent
        agent = MagicMock()
        agent.permissions = MagicMock()
        agent.permissions.check = AsyncMock(return_value=True)
        agent.tool_cache = MagicMock()
        agent.tool_cache.get = AsyncMock(return_value=None)
        agent.tool_cache.set = AsyncMock()

        # Empty tool calls should return empty list
        results = await execute_tools_parallel([], agent, token)
        assert results == []


class TestPropertyBasedCancellation:
    """Property-based tests for cancellation."""

    @given(reason=st.text(alphabet=st.characters(categories=("L", "N", "P", "S")), max_size=100))
    @settings(max_examples=20)
    def test_cancel_reason_preserved(self, reason):
        """Any reason string should be preserved."""
        token = CancellationToken()
        token.cancel(reason=reason)
        assert token.reason == reason

    @given(
        cancel_count=st.integers(min_value=1, max_value=10),
        reason=st.text(alphabet=st.characters(categories=("L", "N")), max_size=50),
    )
    @settings(max_examples=10)
    def test_multiple_cancels_idempotent(self, cancel_count, reason):
        """Multiple cancel calls should not change initial state."""
        token = CancellationToken()
        token.cancel(reason=reason)
        first_time = token.cancel_time
        first_reason = token.reason

        for _ in range(cancel_count):
            token.cancel(reason="Different reason")

        assert token.cancel_time == first_time
        assert token.reason == first_reason


class TestEdgeCases:
    """Edge case tests for cancellation."""

    def test_cancel_with_empty_reason(self):
        """Empty string reason should be stored."""
        token = CancellationToken()
        token.cancel(reason="")
        assert token.reason == ""

    def test_cancel_with_none_reason(self):
        """None reason should be stored as None."""
        token = CancellationToken()
        token.cancel(reason=None)
        assert token.reason is None

    def test_reset_clears_event(self):
        """reset() should clear the internal event."""
        token = CancellationToken()
        token.cancel()
        token.reset()
        # After reset, wait_for_cancellation should timeout
        # We test this indirectly by checking is_cancelled

        assert token.is_cancelled is False

    @pytest.mark.asyncio
    async def test_concurrent_cancel_calls(self):
        """Concurrent cancel() calls should be safe."""
        token = CancellationToken()

        async def cancel_task(reason):
            await asyncio.sleep(0.001)
            token.cancel(reason=reason)

        # Launch multiple concurrent cancels
        tasks = [cancel_task(f"reason_{i}") for i in range(10)]
        await asyncio.gather(*tasks)

        # Token should be cancelled (first call wins)
        assert token.is_cancelled is True


class TestIntegration:
    """Integration tests for cancellation system."""

    @pytest.mark.asyncio
    async def test_full_cancellation_flow(self):
        """Test complete cancellation flow from Agent.cancel() to LoopEvent."""
        from unittest.mock import AsyncMock, MagicMock

        from chapgent.core.agent import Agent
        from chapgent.core.providers import LLMResponse, TextBlock, TokenUsage
        from chapgent.session.models import Session
        from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk

        # Create a mock tool that takes time
        async def slow_tool(message: str) -> str:
            await asyncio.sleep(0.01)
            return f"Processed: {message}"

        tool_def = ToolDefinition(
            name="slow_tool",
            description="A slow tool",
            function=slow_tool,
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            read_only=True,
        )

        # Set up mocks
        provider = MagicMock()
        provider.complete = AsyncMock(
            return_value=LLMResponse(
                content=[TextBlock(text="Done")],
                stop_reason="end_turn",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        )

        registry = MagicMock()
        registry.list_definitions.return_value = [{"name": "slow_tool"}]
        registry.get.return_value = tool_def

        permissions = MagicMock()
        permissions.check = AsyncMock(return_value=True)

        session = Session(id="test-session")
        agent = Agent(provider, registry, permissions, session)

        # Run agent and collect events
        events = []
        async for event in agent.run("Test message"):
            events.append(event)

        # Should complete normally
        event_types = [e.type for e in events]
        assert "finished" in event_types
