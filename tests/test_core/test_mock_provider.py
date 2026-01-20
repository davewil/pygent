"""Tests for MockLLMProvider."""

import pytest

from chapgent.core.mock_provider import MockLLMProvider
from chapgent.core.providers import LLMResponse
from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk


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
            category=ToolCategory.FILESYSTEM,
            function=lambda: None,  # type: ignore
        ),
        ToolDefinition(
            name="list_files",
            description="List files",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk=ToolRisk.LOW,
            category=ToolCategory.FILESYSTEM,
            function=lambda: None,  # type: ignore
        ),
        ToolDefinition(
            name="edit_file",
            description="Edit a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk=ToolRisk.MEDIUM,
            category=ToolCategory.FILESYSTEM,
            function=lambda: None,  # type: ignore
        ),
        ToolDefinition(
            name="shell",
            description="Run shell command",
            input_schema={"type": "object", "properties": {"command": {"type": "string"}}},
            risk=ToolRisk.HIGH,
            category=ToolCategory.SHELL,
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


class TestMockProviderDelay:
    """Test delay feature."""

    @pytest.mark.asyncio
    async def test_provider_with_delay(self, tools):
        """Test that delay is applied to responses (covers line 41)."""
        import time

        provider = MockLLMProvider(delay=0.1)
        messages = [{"role": "user", "content": "hello"}]

        start = time.monotonic()
        await provider.complete(messages, tools)
        elapsed = time.monotonic() - start

        # Should have delayed at least 0.1 seconds (with small tolerance for timer resolution)
        assert elapsed >= 0.09  # Allow 10ms tolerance for Windows timer resolution


class TestMockProviderEdgeCases:
    """Test edge cases and uncovered paths."""

    @pytest.mark.asyncio
    async def test_no_user_message_returns_empty_string(self, mock_provider, tools):
        """Test when conversation has no user messages (covers line 73)."""
        # Messages without any user role
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "assistant", "content": "Hello"},
        ]
        response = await mock_provider.complete(messages, tools)

        assert isinstance(response, LLMResponse)
        assert response.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_edit_file_trigger_returns_text_response(self, mock_provider, tools):
        """Test edit file trigger returns guidance text (covers lines 115-116)."""
        messages = [{"role": "user", "content": "edit the config file"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "end_turn"
        # Should return guidance text, not a tool call
        assert "edit" in response.content[0].text.lower() or "specify" in response.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_read_file_with_quoted_filename(self, mock_provider, tools):
        """Test filename extraction with quotes (covers line 198)."""
        messages = [{"role": "user", "content": "read file 'config.yaml'"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "read_file"
        assert tool_calls[0].input.get("path") == "config.yaml"

    @pytest.mark.asyncio
    async def test_list_files_with_quoted_path(self, mock_provider, tools):
        """Test path extraction with quotes (covers line 210)."""
        messages = [{"role": "user", "content": "list files in 'src/components'"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "list_files"
        assert tool_calls[0].input.get("path") == "src/components"

    @pytest.mark.asyncio
    async def test_shell_with_quoted_command(self, mock_provider, tools):
        """Test command extraction with quotes (covers line 224)."""
        messages = [{"role": "user", "content": "run command 'git status'"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "shell"
        assert tool_calls[0].input.get("command") == "git status"

    @pytest.mark.asyncio
    async def test_tool_result_as_only_message(self, mock_provider, tools):
        """Test when last message is tool result but no preceding user message (covers line 80)."""
        messages = [
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
        ]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "end_turn"
        # Should return continuation response
        assert "completed" in response.content[0].text.lower() or "anything else" in response.content[0].text.lower()

    @pytest.mark.asyncio
    async def test_user_message_with_non_string_content(self, mock_provider, tools):
        """Test handling user message with list content."""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        ]
        response = await mock_provider.complete(messages, tools)

        assert isinstance(response, LLMResponse)
        # Should fall back to empty string since content is not a string
        assert response.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_extract_path_without_quotes(self, mock_provider, tools):
        """Test path extraction for relative paths (covers line 215)."""
        # Use a path pattern that will match the common path regex (foo/bar pattern)
        messages = [{"role": "user", "content": "list files in src/components"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "list_files"
        assert tool_calls[0].input.get("path") == "src/components"

    @pytest.mark.asyncio
    async def test_extract_command_common_pattern(self, mock_provider, tools):
        """Test command extraction for common commands (covers line 231)."""
        # Use "execute" instead of "run" to avoid overlap with list patterns
        messages = [{"role": "user", "content": "execute git status"}]
        response = await mock_provider.complete(messages, tools)

        assert response.stop_reason == "tool_use"
        tool_calls = [b for b in response.content if hasattr(b, "name")]
        assert len(tool_calls) >= 1
        assert tool_calls[0].name == "shell"
        # Should extract "git status"
        assert "git" in tool_calls[0].input.get("command", "")
