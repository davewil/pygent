from unittest.mock import AsyncMock, patch

import pytest
from pygent.core.providers import LLMProvider, LLMResponse, TextBlock
from pygent.tools.base import ToolDefinition, ToolRisk


@pytest.fixture
def mock_litellm_completion():
    with patch("pygent.core.providers.litellm.acompletion", new_callable=AsyncMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_complete_text_only(mock_litellm_completion):
    # Setup mock response
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(finish_reason="stop", message=AsyncMock(content="Hello world", tool_calls=None))]
    mock_litellm_completion.return_value = mock_response

    provider = LLMProvider(model="gpt-4o", api_key="test-key")
    messages = [{"role": "user", "content": "Hi"}]

    response = await provider.complete(messages=messages, tools=[])

    assert isinstance(response, LLMResponse)
    assert len(response.content) == 1
    assert isinstance(response.content[0], TextBlock)
    assert response.content[0].text == "Hello world"
    assert response.stop_reason == "stop"

    # Verify litellm call
    mock_litellm_completion.assert_awaited_once()
    call_kwargs = mock_litellm_completion.await_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["api_key"] == "test-key"
    assert call_kwargs["messages"] == messages


@pytest.mark.asyncio
async def test_complete_with_tools_formatting():
    # Verify tools are correctly formatted for litellm
    with patch("pygent.core.providers.litellm.acompletion", new_callable=AsyncMock) as mock_completion:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(finish_reason="stop", message=AsyncMock(content="ok", tool_calls=None))]
        mock_completion.return_value = mock_response

        provider = LLMProvider(model="claude-3")

        async def dummy_tool(x: int):
            pass

        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            risk=ToolRisk.LOW,
            function=dummy_tool,
        )

        await provider.complete(messages=[], tools=[tool_def])

        call_kwargs = mock_completion.await_args.kwargs
        assert "tools" in call_kwargs
        tools_arg = call_kwargs["tools"]
        assert len(tools_arg) == 1
        assert tools_arg[0]["type"] == "function"
        assert tools_arg[0]["function"]["name"] == "test_tool"
        assert tools_arg[0]["function"]["description"] == "A test tool"
