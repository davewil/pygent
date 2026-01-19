"""Tests for conversation loop error handling and edge cases."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pygent.core.agent import Agent
from pygent.core.loop import DEFAULT_MAX_ITERATIONS, _convert_to_llm_messages, conversation_loop
from pygent.core.providers import LLMResponse, TokenUsage
from pygent.core.providers import TextBlock as ProvTextBlock
from pygent.core.providers import ToolUseBlock as ProvToolUseBlock
from pygent.session.models import Message, Session, TextBlock, ToolResultBlock, ToolUseBlock
from pygent.tools.base import ToolCategory, ToolDefinition, ToolRisk


@pytest.fixture
def mock_provider():
    """Mock LLM provider."""
    return AsyncMock()


@pytest.fixture
def mock_registry():
    """Mock tool registry."""
    registry = MagicMock()
    registry.list_definitions.return_value = []
    registry.get.return_value = None  # Default: no tools found
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


class TestLoopToolNotFound:
    """Test behavior when LLM requests a tool that doesn't exist."""

    @pytest.mark.asyncio
    async def test_unknown_tool_yields_error_result(self, mock_provider, mock_registry, mock_permissions, session):
        """When LLM calls a tool that doesn't exist, yield error result."""
        # LLM calls a non-existent tool, then finishes
        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="unknown_tool", input={"arg": "val"})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
        ]

        # Registry returns None for unknown tool
        mock_registry.get.return_value = None

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Use unknown tool")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Should have: tool_call, tool_result (error), text, finished
        event_types = [e.type for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types

        # Find the error result
        error_results = [e for e in events if e.type == "tool_result" and e.content]
        assert len(error_results) >= 1
        assert "not found" in error_results[0].content.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_result_marked_as_error(self, mock_provider, mock_registry, mock_permissions, session):
        """Unknown tool result should be marked as error in messages."""
        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="nonexistent", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Acknowledged")], stop_reason="end_turn"),
        ]
        mock_registry.get.return_value = None

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        async for _ in conversation_loop(agent, messages):
            pass

        # Check messages for error result
        tool_result_msg = messages[2]  # 0: user, 1: assistant (tool call), 2: tool result
        assert tool_result_msg.role == "user"
        assert isinstance(tool_result_msg.content[0], ToolResultBlock)
        assert tool_result_msg.content[0].is_error is True


class TestLoopToolExecution:
    """Test behavior when tool execution raises exceptions."""

    @pytest.mark.asyncio
    async def test_tool_exception_yields_error_result(self, mock_provider, mock_registry, mock_permissions, session):
        """When tool execution raises an exception, yield error result."""

        async def failing_tool(**kwargs):
            raise RuntimeError("Tool crashed unexpectedly!")

        tool_def = ToolDefinition(
            name="failing_tool",
            description="A tool that fails",
            input_schema={},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            function=failing_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "failing_tool"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="failing_tool", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="I see an error occurred")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Run failing tool")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Find tool result with error
        error_results = [e for e in events if e.type == "tool_result"]
        assert len(error_results) >= 1
        assert "Error" in error_results[0].content or "error" in error_results[0].content.lower()
        assert "Tool crashed unexpectedly" in error_results[0].content

    @pytest.mark.asyncio
    async def test_tool_exception_marked_as_error_in_message(
        self, mock_provider, mock_registry, mock_permissions, session
    ):
        """Tool exception should mark result as error in message blocks."""

        async def crash_tool(**kwargs):
            raise ValueError("Bad input")

        tool_def = ToolDefinition(
            name="crash_tool",
            description="Crashes",
            input_schema={},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            function=crash_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "crash_tool"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="crash_tool", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        async for _ in conversation_loop(agent, messages):
            pass

        # Check tool result message
        tool_result_msg = messages[2]
        result_block = tool_result_msg.content[0]
        assert isinstance(result_block, ToolResultBlock)
        assert result_block.is_error is True
        assert "Bad input" in result_block.content


class TestLoopPermissionDenied:
    """Test behavior when permissions are denied."""

    @pytest.mark.asyncio
    async def test_permission_denied_yields_event(self, mock_provider, mock_registry, session):
        """When permission is denied, yield permission_denied event."""

        async def dummy_tool(**kwargs):
            return "Should not run"

        tool_def = ToolDefinition(
            name="risky_tool",
            description="A risky tool",
            input_schema={},
            risk=ToolRisk.HIGH,
            category=ToolCategory.SHELL,
            function=dummy_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "risky_tool"}]

        # Permission manager denies
        mock_permissions = AsyncMock()
        mock_permissions.check.return_value = False

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="risky_tool", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Permission was denied")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Do risky thing")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        event_types = [e.type for e in events]
        assert "permission_denied" in event_types

        # Find the permission denied event
        denied = [e for e in events if e.type == "permission_denied"]
        assert len(denied) == 1
        assert denied[0].tool_name == "risky_tool"

    @pytest.mark.asyncio
    async def test_permission_denied_result_marked_as_error(self, mock_provider, mock_registry, session):
        """Permission denied should result in error block in messages."""

        async def some_tool(**kwargs):
            return "result"

        tool_def = ToolDefinition(
            name="tool",
            description="desc",
            input_schema={},
            risk=ToolRisk.HIGH,
            category=ToolCategory.SHELL,
            function=some_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "tool"}]

        mock_permissions = AsyncMock()
        mock_permissions.check.return_value = False

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="tool", input={})],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Ok")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        async for _ in conversation_loop(agent, messages):
            pass

        # Check messages
        tool_result_msg = messages[2]
        result_block = tool_result_msg.content[0]
        assert isinstance(result_block, ToolResultBlock)
        assert result_block.is_error is True
        assert "Permission denied" in result_block.content or "denied" in result_block.content.lower()


class TestMessageConversion:
    """Test _convert_to_llm_messages helper."""

    def test_simple_text_message(self):
        """Convert simple text messages."""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        result = _convert_to_llm_messages(messages)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there"}

    def test_message_with_text_blocks(self):
        """Convert messages with TextBlock content."""
        messages = [
            Message(role="user", content="Question?"),
            Message(role="assistant", content=[TextBlock(text="Answer 1"), TextBlock(text="Answer 2")]),
        ]
        result = _convert_to_llm_messages(messages)
        assert len(result) == 2
        # Multiple text blocks joined
        assert "Answer 1" in result[1]["content"]
        assert "Answer 2" in result[1]["content"]

    def test_message_with_tool_use(self):
        """Convert assistant message with tool use."""
        messages = [
            Message(role="user", content="Do task"),
            Message(
                role="assistant",
                content=[
                    TextBlock(text="Let me use a tool"),
                    ToolUseBlock(id="call_123", name="test_tool", input={"arg": "val"}),
                ],
            ),
        ]
        result = _convert_to_llm_messages(messages)
        assert len(result) == 2
        assert result[1]["role"] == "assistant"
        assert "tool_calls" in result[1]
        assert result[1]["tool_calls"][0]["id"] == "call_123"
        assert result[1]["tool_calls"][0]["function"]["name"] == "test_tool"

    def test_message_with_tool_result(self):
        """Convert tool result messages properly."""
        messages = [
            Message(
                role="user",
                content=[ToolResultBlock(tool_use_id="call_123", content="Result data", is_error=False)],
            ),
        ]
        result = _convert_to_llm_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call_123"
        assert result[0]["content"] == "Result data"


class TestLoopMultipleToolCalls:
    """Test handling of multiple tool calls in single response."""

    @pytest.mark.asyncio
    async def test_multiple_tools_in_one_response(self, mock_provider, mock_permissions, session):
        """LLM can call multiple tools in one response."""
        registry = MagicMock()

        async def tool_a(**kwargs):
            return "Result A"

        async def tool_b(**kwargs):
            return "Result B"

        def get_tool(name):
            tools = {
                "tool_a": ToolDefinition("tool_a", "Tool A", {}, ToolRisk.LOW, ToolCategory.SHELL, tool_a),
                "tool_b": ToolDefinition("tool_b", "Tool B", {}, ToolRisk.LOW, ToolCategory.SHELL, tool_b),
            }
            return tools.get(name)

        registry.get.side_effect = get_tool
        registry.list_definitions.return_value = [{"name": "tool_a"}, {"name": "tool_b"}]

        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[
                    ProvToolUseBlock(id="call_1", name="tool_a", input={}),
                    ProvToolUseBlock(id="call_2", name="tool_b", input={}),
                ],
                stop_reason="tool_use",
            ),
            LLMResponse(content=[ProvTextBlock(text="Both done")], stop_reason="end_turn"),
        ]

        agent = Agent(mock_provider, registry, mock_permissions, session)
        messages = [Message(role="user", content="Use both tools")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        tool_calls = [e for e in events if e.type == "tool_call"]
        tool_results = [e for e in events if e.type == "tool_result"]

        assert len(tool_calls) == 2
        assert len(tool_results) == 2
        assert "Result A" in tool_results[0].content
        assert "Result B" in tool_results[1].content


class TestLoopPropertyBased:
    """Property-based tests for loop behavior."""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=20)
    def test_user_message_always_leads_to_response(self, user_text):
        """Any user message should lead to a finished event."""
        import asyncio

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvTextBlock(text="Response")], stop_reason="end_turn"
        )

        mock_registry = MagicMock()
        mock_registry.list_definitions.return_value = []
        mock_registry.get.return_value = None

        mock_permissions = AsyncMock()
        mock_permissions.check.return_value = True

        session = Session(id="prop-test", messages=[])

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content=user_text)]

        async def run_loop():
            events = []
            async for event in conversation_loop(agent, messages):
                events.append(event)
            return events

        events = asyncio.run(run_loop())

        # Always ends with finished
        assert events[-1].type == "finished"
        # Always has at least text or finished
        assert len(events) >= 1

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=10)
    def test_n_tool_calls_produce_n_results(self, n):
        """N tool calls should produce N results."""
        import asyncio

        mock_provider = AsyncMock()

        async def good_tool(**kwargs):
            return "ok"

        tool_def = ToolDefinition("good_tool", "desc", {}, ToolRisk.LOW, ToolCategory.SHELL, good_tool)

        mock_registry = MagicMock()
        mock_registry.list_definitions.return_value = [{"name": "good_tool"}]
        mock_registry.get.return_value = tool_def

        mock_permissions = AsyncMock()
        mock_permissions.check.return_value = True

        # Generate n tool calls
        tool_uses = [ProvToolUseBlock(id=f"call_{i}", name="good_tool", input={}) for i in range(n)]

        mock_provider.complete.side_effect = [
            LLMResponse(content=tool_uses, stop_reason="tool_use"),
            LLMResponse(content=[ProvTextBlock(text="All done")], stop_reason="end_turn"),
        ]

        session = Session(id="prop-test", messages=[])
        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        async def run_loop():
            events = []
            async for event in conversation_loop(agent, messages):
                events.append(event)
            return events

        events = asyncio.run(run_loop())

        tool_calls = [e for e in events if e.type == "tool_call"]
        tool_results = [e for e in events if e.type == "tool_result"]

        assert len(tool_calls) == n
        assert len(tool_results) == n


class TestLoopIterationLimit:
    """Test iteration limit functionality."""

    @pytest.mark.asyncio
    async def test_iteration_limit_triggers_event(self, mock_provider, mock_registry, mock_permissions, session):
        """When max_iterations is reached, yield iteration_limit_reached event."""

        # LLM keeps calling tools endlessly
        async def endless_tool(**kwargs):
            return "Keep going"

        tool_def = ToolDefinition(
            name="endless_tool",
            description="A tool that runs forever",
            input_schema={},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            function=endless_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "endless_tool"}]

        # Provider always returns tool call
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvToolUseBlock(id="call_1", name="endless_tool", input={})],
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

        # Find the limit event
        limit_event = next(e for e in events if e.type == "iteration_limit_reached")
        assert "3" in limit_event.content
        assert limit_event.iteration == 3

        # Should end with finished
        assert events[-1].type == "finished"

    @pytest.mark.asyncio
    async def test_iteration_limit_default_value(self):
        """Default max_iterations should be DEFAULT_MAX_ITERATIONS."""
        assert DEFAULT_MAX_ITERATIONS == 50

    @pytest.mark.asyncio
    async def test_no_limit_reached_when_under_max(self, mock_provider, mock_registry, mock_permissions, session):
        """When iterations are under max, no limit event should be yielded."""
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


class TestLoopTokenLimit:
    """Test token limit functionality."""

    @pytest.mark.asyncio
    async def test_token_limit_triggers_event(self, mock_provider, mock_registry, mock_permissions, session):
        """When max_tokens is exceeded, yield token_limit_reached event."""

        async def token_heavy_tool(**kwargs):
            return "Heavy result"

        tool_def = ToolDefinition(
            name="heavy_tool",
            description="A token-heavy tool",
            input_schema={},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            function=token_heavy_tool,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "heavy_tool"}]

        # Each response uses 100 tokens
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvToolUseBlock(id="call_1", name="heavy_tool", input={})],
            stop_reason="tool_use",
            usage=TokenUsage(prompt_tokens=70, completion_tokens=30, total_tokens=100),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Use tokens")]

        events = []
        # Limit to 250 tokens - should trigger after 3rd iteration (300 tokens)
        async for event in conversation_loop(agent, messages, max_tokens=250):
            events.append(event)

        event_types = [e.type for e in events]
        assert "token_limit_reached" in event_types

        # Find the limit event
        limit_event = next(e for e in events if e.type == "token_limit_reached")
        assert "250" in limit_event.content  # Max tokens mentioned
        assert limit_event.total_tokens > 250  # Exceeded the limit

        # Should end with finished
        assert events[-1].type == "finished"

    @pytest.mark.asyncio
    async def test_token_limit_none_means_unlimited(self, mock_provider, mock_registry, mock_permissions, session):
        """When max_tokens is None, no token limit is enforced."""

        async def tool_fn(**kwargs):
            return "result"

        tool_def = ToolDefinition(
            name="tool",
            description="desc",
            input_schema={},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            function=tool_fn,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "tool"}]

        # Use lots of tokens but with a normal flow (tool then done)
        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="tool", input={})],
                stop_reason="tool_use",
                usage=TokenUsage(prompt_tokens=5000, completion_tokens=5000, total_tokens=10000),
            ),
            LLMResponse(
                content=[ProvTextBlock(text="Done")],
                stop_reason="end_turn",
                usage=TokenUsage(prompt_tokens=5000, completion_tokens=5000, total_tokens=10000),
            ),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages, max_tokens=None):
            events.append(event)

        event_types = [e.type for e in events]
        assert "token_limit_reached" not in event_types
        assert events[-1].type == "finished"

    @pytest.mark.asyncio
    async def test_no_token_limit_reached_when_under_max(self, mock_provider, mock_registry, mock_permissions, session):
        """When tokens are under max, no limit event should be yielded."""
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvTextBlock(text="Done")],
            stop_reason="end_turn",
            usage=TokenUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Small task")]

        events = []
        async for event in conversation_loop(agent, messages, max_tokens=1000):
            events.append(event)

        event_types = [e.type for e in events]
        assert "token_limit_reached" not in event_types
        assert events[-1].type == "finished"


class TestLoopTokenTracking:
    """Test token usage tracking in events."""

    @pytest.mark.asyncio
    async def test_events_include_iteration_and_tokens(self, mock_provider, mock_registry, mock_permissions, session):
        """Events should include iteration count and cumulative token usage."""
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvTextBlock(text="Response")],
            stop_reason="end_turn",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Text event should have iteration and token info
        text_event = next(e for e in events if e.type == "text")
        assert text_event.iteration == 1
        assert text_event.total_tokens == 150
        assert text_event.usage is not None
        assert text_event.usage.total_tokens == 150

        # Finished event should have final counts
        finished_event = events[-1]
        assert finished_event.iteration == 1
        assert finished_event.total_tokens == 150

    @pytest.mark.asyncio
    async def test_cumulative_token_tracking(self, mock_provider, mock_registry, mock_permissions, session):
        """Token tracking should be cumulative across iterations."""

        async def tool_fn(**kwargs):
            return "result"

        tool_def = ToolDefinition(
            name="tool",
            description="desc",
            input_schema={},
            risk=ToolRisk.LOW,
            category=ToolCategory.SHELL,
            function=tool_fn,
        )
        mock_registry.get.return_value = tool_def
        mock_registry.list_definitions.return_value = [{"name": "tool"}]

        # First call: tool use (100 tokens), Second call: done (50 tokens)
        mock_provider.complete.side_effect = [
            LLMResponse(
                content=[ProvToolUseBlock(id="call_1", name="tool", input={})],
                stop_reason="tool_use",
                usage=TokenUsage(prompt_tokens=70, completion_tokens=30, total_tokens=100),
            ),
            LLMResponse(
                content=[ProvTextBlock(text="Done")],
                stop_reason="end_turn",
                usage=TokenUsage(prompt_tokens=30, completion_tokens=20, total_tokens=50),
            ),
        ]

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # First iteration events should show 100 tokens
        tool_call_event = next(e for e in events if e.type == "tool_call")
        assert tool_call_event.iteration == 1
        assert tool_call_event.total_tokens == 100

        # Second iteration events should show 150 tokens (cumulative)
        text_event = next(e for e in events if e.type == "text")
        assert text_event.iteration == 2
        assert text_event.total_tokens == 150

        # Final event should have full count
        finished_event = events[-1]
        assert finished_event.total_tokens == 150

    @pytest.mark.asyncio
    async def test_handles_missing_usage(self, mock_provider, mock_registry, mock_permissions, session):
        """Loop should handle responses without usage information gracefully."""
        mock_provider.complete.return_value = LLMResponse(
            content=[ProvTextBlock(text="Response")],
            stop_reason="end_turn",
            usage=None,  # No usage info
        )

        agent = Agent(mock_provider, mock_registry, mock_permissions, session)
        messages = [Message(role="user", content="Test")]

        events = []
        async for event in conversation_loop(agent, messages):
            events.append(event)

        # Should complete without error
        assert events[-1].type == "finished"
        assert events[-1].total_tokens == 0  # No tokens counted
