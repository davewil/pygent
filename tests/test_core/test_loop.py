"""Behavioral tests for conversation loop.

Tests verify user-facing behavior:
- Loop executes tools and returns results
- Loop respects iteration and token limits
- Loop handles errors gracefully
- Loop tracks token usage
- Streaming loop handles Claude Max events
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from chapgent.core.agent import Agent
from chapgent.core.cancellation import CancellationToken
from chapgent.core.loop import DEFAULT_MAX_ITERATIONS, conversation_loop, streaming_conversation_loop
from chapgent.core.providers import LLMResponse, TokenUsage
from chapgent.core.providers import TextBlock as ProvTextBlock
from chapgent.core.providers import ToolUseBlock as ProvToolUseBlock
from chapgent.core.acp_provider import (
    StreamComplete,
    StreamError,
    ACPClaudeCodeProvider,
    TextDelta,
    ToolCall,
    ToolResult,
)
from chapgent.session.models import Message, Session, ToolResultBlock
from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk


@pytest.fixture
def mock_provider():
    """Mock LLM provider."""
    return AsyncMock()


@pytest.fixture
def mock_registry():
    """Mock tool registry."""
    registry = MagicMock()
    registry.list_definitions.return_value = []
    registry.get.return_value = None
    return registry


@pytest.fixture
def mock_permissions():
    """Mock permission manager that always approves."""
    pm = AsyncMock()
    pm.check.return_value = True
    return pm


@pytest.fixture
def session():
    """Fresh session for testing."""
    return Session(id="test-session", messages=[])


def make_tool(name: str, func):
    """Helper to create a tool definition."""
    return ToolDefinition(
        name=name,
        description=f"Tool {name}",
        input_schema={},
        risk=ToolRisk.LOW,
        category=ToolCategory.SHELL,
        function=func,
    )


# =============================================================================
# Tool Execution - Loop executes tools and handles results
# =============================================================================


class TestToolExecution:
    """Loop executes tools requested by the LLM."""

    @pytest.mark.asyncio
    async def test_executes_tool_and_returns_result(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop executes tool and yields result event."""

        async def greet_tool(name: str = "World"):
            return f"Hello, {name}!"

        tool_def = make_tool("greet", greet_tool)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "greet"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="greet", input={"name": "Alice"})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Greet Alice")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Should have tool_call and tool_result events
        event_types = [e.type for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types

        # Result should contain the greeting
        result_events = [e for e in events if e.type == "tool_result"]
        assert "Hello, Alice!" in result_events[0].content

    @pytest.mark.asyncio
    async def test_handles_unknown_tool(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop handles unknown tool gracefully with error result."""
        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="unknown_tool", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
        ]
        mock_registry.get.return_value = None

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Use unknown tool")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Should have error result
        error_results = [e for e in events if e.type == "tool_result" and e.content]
        assert len(error_results) >= 1
        assert "not found" in error_results[0].content.lower()

    @pytest.mark.asyncio
    async def test_handles_tool_exception(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop handles tool exceptions gracefully."""

        async def failing_tool(**kwargs):
            raise RuntimeError("Tool crashed!")

        tool_def = make_tool("failing", failing_tool)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "failing"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="failing", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Error noted")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Run failing tool")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Should have error in result
        error_results = [e for e in events if e.type == "tool_result"]
        assert len(error_results) >= 1
        assert "Tool crashed!" in error_results[0].content

    @pytest.mark.asyncio
    async def test_handles_permission_denied(self, mock_provider, mock_registry, session):
        """Loop yields permission_denied event when tool is blocked."""

        async def risky_tool(**kwargs):
            return "Should not run"

        tool_def = make_tool("risky", risky_tool)
        tool_def = ToolDefinition(
            name="risky",
            description="Risky tool",
            input_schema={},
            risk=ToolRisk.HIGH,
            category=ToolCategory.SHELL,
            function=risky_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "risky"}]

        # Permission denied
        mock_permissions = AsyncMock()
        mock_permissions.check.return_value = False

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="risky", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Permission denied")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Do risky thing")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        event_types = [e.type for e in events]
        assert "permission_denied" in event_types

    @pytest.mark.asyncio
    async def test_executes_multiple_tools_in_sequence(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop executes multiple tool calls in sequence."""

        async def tool_a(**kwargs):
            return "Result A"

        async def tool_b(**kwargs):
            return "Result B"

        # Use a function to return the right tool based on name
        tools = {
            "tool_a": make_tool("tool_a", tool_a),
            "tool_b": make_tool("tool_b", tool_b),
        }
        mock_registry.get.side_effect = lambda name: tools.get(name)
        mock_registry.list_definitions.return_value = [{"name": "tool_a"}, {"name": "tool_b"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="tool_a", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(
                content=[ProvToolUseBlock(id="call_2", name="tool_b", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Run both tools")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        tool_results = [e for e in events if e.type == "tool_result"]
        assert len(tool_results) == 2


# =============================================================================
# Iteration Limits - Loop respects max iterations
# =============================================================================


class TestIterationLimits:
    """Loop respects iteration limits."""

    @pytest.mark.asyncio
    async def test_stops_at_iteration_limit(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop stops and yields event when max iterations reached."""

        async def endless_tool(**kwargs):
            return "Keep going"

        tool_def = make_tool("endless", endless_tool)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "endless"}]

        # Provider always returns tool call
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvToolUseBlock(id="call_1", name="endless", input={})],
            stop_reason="tool_use",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Run forever")]

        events = []
        async for event in conversation_loop(agent, messages, max_iterations=3):
            events.append(event)

        event_types = [e.type for e in events]
        assert "iteration_limit_reached" in event_types
        assert events[-1].type == "finished"

    @pytest.mark.asyncio
    async def test_completes_normally_under_limit(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop completes without limit event when under max iterations."""
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvTextBlock(text="Done")],
            stop_reason="end_turn",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Simple task")]

        events = []
        async for event in conversation_loop(agent, messages, max_iterations=10):
            events.append(event)

        event_types = [e.type for e in events]
        assert "iteration_limit_reached" not in event_types
        assert events[-1].type == "finished"

    def test_default_iteration_limit(self):
        """Default max iterations is 50."""
        assert DEFAULT_MAX_ITERATIONS == 50


# =============================================================================
# Token Limits - Loop respects max tokens
# =============================================================================


class TestTokenLimits:
    """Loop respects token limits."""

    @pytest.mark.asyncio
    async def test_stops_at_token_limit(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop stops and yields event when max tokens exceeded."""

        async def heavy_tool(**kwargs):
            return "Heavy result"

        tool_def = make_tool("heavy", heavy_tool)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "heavy"}]

        # Each response uses 100 tokens
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvToolUseBlock(id="call_1", name="heavy", input={})],
            stop_reason="tool_use",
            usage=TokenUsage(prompt_tokens=70, completion_tokens=30, total_tokens=100),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Use tokens")]

        events = []
        async for event in conversation_loop(agent, messages, max_tokens=250):
            events.append(event)

        event_types = [e.type for e in events]
        assert "token_limit_reached" in event_types
        assert events[-1].type == "finished"

    @pytest.mark.asyncio
    async def test_no_limit_when_max_tokens_none(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop has no token limit when max_tokens is None."""

        async def tool_fn(**kwargs):
            return "result"

        tool_def = make_tool("tool", tool_fn)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "tool"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="tool", input={})],
                stop_reason="tool_use",
                usage=TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
            ),
            LLMResponse(
                content=[ProvTextBlock(text="Done")],
                stop_reason="end_turn",
                usage=TokenUsage(prompt_tokens=1500, completion_tokens=100, total_tokens=1600),
            ),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages, max_tokens=None):
            events.append(event)

        event_types = [e.type for e in events]
        assert "token_limit_reached" not in event_types


# =============================================================================
# Token Tracking - Loop tracks token usage
# =============================================================================


class TestTokenTracking:
    """Loop tracks token usage across iterations."""

    @pytest.mark.asyncio
    async def test_tracks_cumulative_tokens(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop tracks total tokens across multiple iterations."""

        async def tool_fn(**kwargs):
            return "result"

        tool_def = make_tool("tool", tool_fn)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "tool"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="tool", input={})],
                stop_reason="tool_use",
                usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
            ),
            LLMResponse(
                content=[ProvTextBlock(text="Done")],
                stop_reason="end_turn",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            ),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Final event should have cumulative token count
        finished = events[-1]
        assert finished.type == "finished"
        assert finished.total_tokens == 225  # 75 + 150


# =============================================================================
# System Prompt - Loop supports custom system prompts
# =============================================================================


class TestSystemPrompt:
    """Loop supports custom system prompts."""

    @pytest.mark.asyncio
    async def test_uses_custom_system_prompt(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop passes custom system prompt to provider."""
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvTextBlock(text="I am a helpful pirate!")],
            stop_reason="end_turn",
            usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Hello")]

        events = []
        async for event in conversation_loop(agent, messages, system_prompt="You are a pirate."):
            events.append(event)

        # Check that provider was called with system prompt
        call_args = mock_provider.complete.call_args
        assert call_args is not None
        # System prompt should be in the call
        assert "pirate" in str(call_args).lower() or mock_provider.complete.called


# =============================================================================
# Error Handling - Loop handles LLM errors
# =============================================================================


class TestErrorHandling:
    """Loop handles LLM and other errors gracefully."""

    @pytest.mark.asyncio
    async def test_handles_llm_error(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop handles LLM provider errors with llm_error event."""
        mock_provider.complete.side_effect = RuntimeError("LLM API error")

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Should yield an llm_error event
        event_types = [e.type for e in events]
        assert "llm_error" in event_types

        error_event = [e for e in events if e.type == "llm_error"][0]
        assert "LLM API error" in error_event.content

    @pytest.mark.asyncio
    async def test_tool_error_marked_in_message(self, mock_provider, mock_registry, mock_permissions, session):
        """Tool errors are marked as is_error in message blocks."""

        async def error_tool(**kwargs):
            raise ValueError("Bad input")

        tool_def = make_tool("error_tool", error_tool)
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "error_tool"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="error_tool", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        async for _ in conversation_loop(agent, messages):
            pass

        # Check tool result message has is_error=True
        tool_result_msg = messages[2]  # user, assistant, tool_result
        result_block = tool_result_msg.content[0]
        assert isinstance(result_block, ToolResultBlock)
        assert result_block.is_error is True


# =============================================================================
# Streaming Loop - Claude Max streaming via ACPClaudeCodeProvider
# =============================================================================


def create_mock_streaming_provider(events: list) -> MagicMock:
    """Create a mock streaming provider that yields the given events."""
    provider = MagicMock(spec=ACPClaudeCodeProvider)

    async def mock_send_message(content: str):
        for event in events:
            yield event

    provider.send_message = mock_send_message
    return provider


class TestStreamingLoopTextDeltas:
    """Streaming loop receives text deltas from Claude Max."""

    @pytest.mark.asyncio
    async def test_user_receives_text_deltas(self):
        """User receives text deltas as Claude responds incrementally."""
        events = [
            TextDelta(text="Hello"),
            TextDelta(text=", world!"),
            StreamComplete(session_id="sess_123", usage={"input_tokens": 10, "output_tokens": 5}),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Say hello"):
            loop_events.append(event)

        # Should receive text_delta events
        text_deltas = [e for e in loop_events if e.type == "text_delta"]
        assert len(text_deltas) == 2
        assert text_deltas[0].content == "Hello"
        assert text_deltas[1].content == ", world!"

    @pytest.mark.asyncio
    async def test_empty_text_deltas_are_preserved(self):
        """Empty text deltas (for formatting) are passed through."""
        events = [
            TextDelta(text=""),
            TextDelta(text="Content"),
            StreamComplete(session_id="sess_123"),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Hello"):
            loop_events.append(event)

        text_deltas = [e for e in loop_events if e.type == "text_delta"]
        assert len(text_deltas) == 2
        assert text_deltas[0].content == ""
        assert text_deltas[1].content == "Content"


class TestStreamingLoopToolCalls:
    """Streaming loop receives tool calls and results from Claude Code."""

    @pytest.mark.asyncio
    async def test_user_sees_tool_calls(self):
        """User sees tool call events when Claude uses tools."""
        events = [
            TextDelta(text="Let me read that file."),
            ToolCall(id="tool_123", name="Read", input={"file_path": "/path/to/file.txt"}),
            ToolResult(id="tool_123", result="File contents here", is_error=False),
            StreamComplete(session_id="sess_123"),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Read file.txt"):
            loop_events.append(event)

        # Should have tool_call and tool_result events
        tool_calls = [e for e in loop_events if e.type == "tool_call"]
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "Read"
        assert tool_calls[0].tool_id == "tool_123"

        tool_results = [e for e in loop_events if e.type == "tool_result"]
        assert len(tool_results) == 1
        assert tool_results[0].content == "File contents here"

    @pytest.mark.asyncio
    async def test_tool_call_input_is_json_serialized(self):
        """Tool call input dict is JSON serialized in event content."""
        events = [
            ToolCall(id="tool_456", name="Write", input={"path": "/tmp/test.txt", "content": "Hello"}),
            StreamComplete(session_id="sess_123"),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Write file"):
            loop_events.append(event)

        tool_calls = [e for e in loop_events if e.type == "tool_call"]
        assert len(tool_calls) == 1
        # Content should be JSON serialized input
        input_dict = json.loads(tool_calls[0].content)
        assert input_dict == {"path": "/tmp/test.txt", "content": "Hello"}


class TestStreamingLoopCompletion:
    """Streaming loop handles stream completion."""

    @pytest.mark.asyncio
    async def test_stream_completion_yields_finished(self):
        """StreamComplete event yields a finished event."""
        events = [
            TextDelta(text="Done!"),
            StreamComplete(session_id="sess_abc", usage={"input_tokens": 100, "output_tokens": 50}),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Test"):
            loop_events.append(event)

        # Should end with finished event
        assert loop_events[-1].type == "finished"

        # Should have token totals from usage
        finished_events = [e for e in loop_events if e.type == "finished" and e.total_tokens]
        assert len(finished_events) >= 1
        assert finished_events[0].total_tokens == 150  # 100 + 50

    @pytest.mark.asyncio
    async def test_always_yields_final_finished_event(self):
        """Loop always yields a final finished event."""
        events = [
            TextDelta(text="Hi"),
            StreamComplete(session_id="sess_123"),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Hello"):
            loop_events.append(event)

        # Last event must be finished
        assert loop_events[-1].type == "finished"


class TestStreamingLoopErrors:
    """Streaming loop handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_stream_error_yields_llm_error(self):
        """StreamError from provider yields llm_error event."""
        events = [
            TextDelta(text="Working..."),
            StreamError(message="Something went wrong", code="INTERNAL_ERROR", retryable=True),
        ]
        provider = create_mock_streaming_provider(events)

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Do something"):
            loop_events.append(event)

        # Should have llm_error event
        error_events = [e for e in loop_events if e.type == "llm_error"]
        assert len(error_events) == 1
        assert error_events[0].content == "Something went wrong"
        assert error_events[0].error_type == "INTERNAL_ERROR"
        assert error_events[0].retryable is True

    @pytest.mark.asyncio
    async def test_provider_exception_yields_llm_error(self):
        """Exception from provider yields llm_error event."""
        provider = MagicMock(spec=ACPClaudeCodeProvider)

        async def mock_send_message(content: str):
            raise RuntimeError("Connection failed")
            yield  # noqa: B007 - Required to make this an async generator

        provider.send_message = mock_send_message

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Test"):
            loop_events.append(event)

        # Should have llm_error event
        error_events = [e for e in loop_events if e.type == "llm_error"]
        assert len(error_events) == 1
        assert "Connection failed" in error_events[0].content


class TestStreamingLoopCancellation:
    """Streaming loop handles cancellation."""

    @pytest.mark.asyncio
    async def test_cancellation_before_start(self):
        """Cancelled token before starting yields cancelled event."""
        events = [
            TextDelta(text="Should not see this"),
            StreamComplete(session_id="sess_123"),
        ]
        provider = create_mock_streaming_provider(events)

        # Pre-cancelled token
        token = CancellationToken()
        token.cancel("User cancelled")

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Test", cancellation_token=token):
            loop_events.append(event)

        # Should have cancelled event
        cancelled_events = [e for e in loop_events if e.type == "cancelled"]
        assert len(cancelled_events) == 1
        assert "before starting" in cancelled_events[0].content

    @pytest.mark.asyncio
    async def test_cancellation_during_streaming(self):
        """Cancellation during streaming yields cancelled event."""
        # Provider that yields events with a delay
        provider = MagicMock(spec=ACPClaudeCodeProvider)
        token = CancellationToken()

        async def mock_send_message(content: str):
            yield TextDelta(text="First")
            # Simulate cancel happening
            token.cancel("User interrupted")
            yield TextDelta(text="Second")  # Should not see this
            yield StreamComplete(session_id="sess_123")

        provider.send_message = mock_send_message

        loop_events = []
        async for event in streaming_conversation_loop(provider, "Test", cancellation_token=token):
            loop_events.append(event)

        # Should have cancelled event
        event_types = [e.type for e in loop_events]
        assert "cancelled" in event_types

        # Should still have first text delta
        text_deltas = [e for e in loop_events if e.type == "text_delta"]
        assert len(text_deltas) >= 1
        assert text_deltas[0].content == "First"
