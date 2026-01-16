"""Tests for MockLLMProvider."""

import pytest

from pygent.core.mock_provider import MockLLMProvider
from pygent.core.providers import LLMResponse
from pygent.tools.base import ToolDefinition, ToolRisk


@pytest.fixture
def mock_provider():
    """Create a mock provider with no delay for fast tests."""
    return MockLLMProvider(delay=0)


@pytest.fixture
def tools():
    """Standard tools list."""
    return [
        ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk=ToolRisk.LOW,
            function=lambda: None,  # type: ignore
        ),
        ToolDefinition(
            name="list_files",
            description="List files",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk=ToolRisk.LOW,
            function=lambda: None,  # type: ignore
        ),
        ToolDefinition(
            name="edit_file",
            description="Edit a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk=ToolRisk.MEDIUM,
            function=lambda: None,  # type: ignore
        ),
        ToolDefinition(
            name="shell",
            description="Run shell command",
            input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
            risk=ToolRisk.HIGH,
            function=lambda: None,  # type: ignore
        ),
    ]


class TestMockProviderTextResponses:
    """Test text response generation."""

    @pytest.mark.asyncio
    async def test_greeting_response(self, mock_provider, tools):
        """Test greeting responses."""
        messages = [{"role": "user", "content": "Hello!"}]
        response = await mock_provider.complete(messages, tools)

        assert isinstance(response, LLMResponse)
        assert response.stop_reason == "end_turn"
        assert len(response.content) == 1
        assert "Hello" in response.content[0].text or "help" in response.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_help_response(self, mock_provider, tools):
        """Test help responses."""
        messages = [{"role": "user", "content": "What can you do?"}]
        response = await mock_provider.complete(messages, tools)

        assert isinstance(response, LLMResponse)
        assert "read_file" in response.content[0].text or "tool" in response.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_default_response(self, mock_provider, tools):
        """Test default response for unknown input."""
        messages = [{"role": "user", "content": "something random xyz"}]
        response = await mock_provider.complete(messages, tools)

        assert isinstance(response, LLMResponse)
        assert response.stop_reason == "end_turn"


class TestMockProviderToolCalls:
    """Test tool call generation."""

    @pytest.mark.asyncio
    async def test_read_file_trigger(self, mock_provider, tools):
        """Test that 'read file' triggers read_file tool."""
        messages = [{"role": "user", "content": "read file README.md"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        # Find tool use block
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "read_file"
        assert tool_calls[0].input.get("path") == "README.md"

    @pytest.mark.asyncio
    async def test_case_insensitive_trigger(self, mock_provider, tools):
        """Test that triggers are case-insensitive but filenames preserve case."""
        messages = [{"role": "user", "content": "READ FILE MyFile.Txt"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "read_file"
        assert tool_calls[0].input.get("path") == "MyFile.Txt"

    @pytest.mark.asyncio
    async def test_list_files_trigger(self, mock_provider, tools):
        """Test that 'list files' triggers list_files tool."""
        messages = [{"role": "user", "content": "list files in current directory"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "list_files"

    @pytest.mark.asyncio
    async def test_shell_trigger(self, mock_provider, tools):
        """Test that 'run command' triggers shell tool."""
        messages = [{"role": "user", "content": "execute shell command echo hello"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "shell"

    @pytest.mark.asyncio
    async def test_tool_result_continuation(self, mock_provider, tools):
        """Test response after tool result."""
        messages = [
            {"role": "user", "content": "read file test.txt"},
            {"role": "assistant", "content": "Reading..."},
            {"role": "tool", "tool_call_id": "call_1", "content": "file contents here"},
        ]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "end_turn"
        assert "completed" in response.content[0].text.lower() or "anything else" in response.content[0].text.lower()


class TestMockProviderNoTools:
    """Test behavior when tools are not available."""

    @pytest.mark.asyncio
    async def test_no_tool_call_without_tools(self, mock_provider):
        """If no tools available, should return text response."""
        messages = [{"role": "user", "content": "read file test.txt"}]
        response = await mock_provider.complete(messages, tools=[])

        assert response.stop_reason == "end_turn"
        # Should not have tool calls
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) == 0
