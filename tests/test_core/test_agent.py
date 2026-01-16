from unittest.mock import AsyncMock, MagicMock

import pytest

from pygent.core.agent import Agent
from pygent.core.loop import conversation_loop
from pygent.core.providers import LLMResponse
from pygent.core.providers import TextBlock as ProvTextBlock
from pygent.core.providers import ToolUseBlock as ProvToolUseBlock
from pygent.session.models import Message, Session, ToolUseBlock
from pygent.tools.base import ToolDefinition, ToolRisk


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    return provider


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.list_definitions.return_value = []

    # Mock get
    async def dummy_tool(**kwargs):
        return "Tool Result"

    tool_def = ToolDefinition(
        name="test_tool", description="desc", input_schema={}, risk=ToolRisk.LOW, function=dummy_tool
    )
    registry.get.return_value = tool_def
    return registry


@pytest.fixture
def mock_permissions():
    pm = AsyncMock()
    pm.check.return_value = True
    return pm


@pytest.fixture
def session():
    return Session(id="test-session", messages=[])


@pytest.mark.asyncio
async def test_loop_basic_conversation(mock_provider, mock_registry, mock_permissions, session):
    # Setup LLM response
    mock_provider.complete.return_value = LLMResponse(
        content=[ProvTextBlock(text="Hello there")], stop_reason="end_turn"
    )

    agent = Agent(mock_provider, mock_registry, mock_permissions, session)
    messages = [Message(role="user", content="Hi")]

    events = []
    async for event in conversation_loop(agent, messages):
        events.append(event)

    assert len(events) >= 1
    assert events[0].type == "text"
    assert events[0].content == "Hello there"

    assert len(messages) == 2
    assert messages[1].role == "assistant"
    assert messages[1].content[0].text == "Hello there"


@pytest.mark.asyncio
async def test_loop_tool_execution(mock_provider, mock_registry, mock_permissions, session):
    # First response: Tool Call
    # Second response: Final text

    mock_provider.complete.side_effect = [
        LLMResponse(
            content=[
                ProvTextBlock(text="Thinking..."),
                ProvToolUseBlock(id="call_1", name="test_tool", input={"arg": "val"}),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(content=[ProvTextBlock(text="Done")], stop_reason="end_turn"),
    ]

    agent = Agent(mock_provider, mock_registry, mock_permissions, session)
    messages = [Message(role="user", content="Do something")]

    events = []
    async for event in conversation_loop(agent, messages):
        events.append(event)

    types = [e.type for e in events]
    assert "text" in types
    assert "tool_call" in types
    assert "tool_result" in types

    # Check interaction flow in messages
    # 0: User "Do something"
    # 1: Assistant "Thinking...", ToolUse
    # 2: User (Tool Result)
    # 3: Assistant "Done"
    assert len(messages) == 4
    assert messages[1].role == "assistant"
    # Now valid because ToolUseBlock is from session.models
    assert isinstance(messages[1].content[1], ToolUseBlock)

    assert messages[2].role == "user"
    assert messages[2].content[0].type == "tool_result"
    assert messages[2].content[0].content == "Tool Result"
