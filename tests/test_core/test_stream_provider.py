"""Behavioral tests for StreamingClaudeCodeProvider.

These tests verify the streaming provider's behavior from a user's perspective:
- Receiving text deltas as Claude responds
- Handling tool calls and results
- Permission request/response flow
- Session persistence across messages
- Error handling and recovery
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chapgent.core.stream_provider import (
    StreamComplete,
    StreamError,
    StreamingClaudeCodeProvider,
    StreamingClaudeCodeProviderError,
    TextDelta,
    ToolCall,
    ToolResult,
)

# =============================================================================
# Test Fixtures
# =============================================================================


def create_mock_process(stdout_lines: list[str]) -> MagicMock:
    """Create a mock subprocess with predefined stdout output."""
    mock_process = MagicMock()
    mock_process.returncode = None

    # Create mock stdin
    mock_stdin = MagicMock()
    mock_stdin.write = MagicMock()
    mock_stdin.drain = AsyncMock()
    mock_process.stdin = mock_stdin

    # Create mock stdout that yields lines
    stdout_queue: asyncio.Queue[bytes] = asyncio.Queue()
    for line in stdout_lines:
        stdout_queue.put_nowait(f"{line}\n".encode())
    stdout_queue.put_nowait(b"")  # EOF

    async def mock_readline() -> bytes:
        return await stdout_queue.get()

    mock_stdout = MagicMock()
    mock_stdout.readline = mock_readline
    mock_process.stdout = mock_stdout

    mock_process.stderr = MagicMock()
    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()

    return mock_process


# =============================================================================
# Behavioral Tests: Text Streaming
# =============================================================================


class TestTextStreaming:
    """Tests for receiving text deltas during streaming."""

    @pytest.mark.asyncio
    async def test_user_receives_text_as_it_streams(self) -> None:
        """When Claude responds, user receives text deltas incrementally."""
        # Claude Code stream-json format uses stream_event with content_block_delta
        stdout_lines = [
            json.dumps({"type": "system", "subtype": "init", "session_id": "sess_123"}),
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}}}),
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": ", world!"}}}),
            json.dumps({"type": "result", "session_id": "sess_123", "usage": {"input_tokens": 10, "output_tokens": 5}}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                events = []
                async for event in provider.send_message("Say hello"):
                    events.append(event)

        # User should receive text deltas in order
        assert len(events) == 3
        assert isinstance(events[0], TextDelta)
        assert events[0].text == "Hello"
        assert isinstance(events[1], TextDelta)
        assert events[1].text == ", world!"
        assert isinstance(events[2], StreamComplete)

    @pytest.mark.asyncio
    async def test_empty_text_deltas_are_preserved(self) -> None:
        """Empty text deltas (e.g., for formatting) are passed through."""
        stdout_lines = [
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": ""}}}),
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Content"}}}),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                events = [e async for e in provider.send_message("Hello")]

        text_deltas = [e for e in events if isinstance(e, TextDelta)]
        assert len(text_deltas) == 2
        assert text_deltas[0].text == ""
        assert text_deltas[1].text == "Content"


# =============================================================================
# Behavioral Tests: Tool Execution
# =============================================================================


class TestToolExecution:
    """Tests for tool call and result handling."""

    @pytest.mark.asyncio
    async def test_user_sees_tool_calls_in_stream(self) -> None:
        """When Claude calls a tool, user receives the tool call event."""
        # Claude Code uses content_block_start for tool_use and assistant message for tool results
        stdout_lines = [
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Let me read that file."}}}),
            json.dumps({
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "content_block": {
                        "type": "tool_use",
                        "id": "tool_123",
                        "name": "Read",
                        "input": {"file_path": "/path/to/file.txt"},
                    }
                }
            }),
            json.dumps({
                "type": "assistant",
                "message": {
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": "tool_123",
                        "content": "File contents here",
                        "is_error": False,
                    }]
                }
            }),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                events = [e async for e in provider.send_message("Read file.txt")]

        # Find the tool call event
        tool_calls = [e for e in events if isinstance(e, ToolCall)]
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "Read"
        assert tool_calls[0].input == {"file_path": "/path/to/file.txt"}

        # Find the tool result event
        tool_results = [e for e in events if isinstance(e, ToolResult)]
        assert len(tool_results) == 1
        assert tool_results[0].result == "File contents here"
        assert tool_results[0].is_error is False

    @pytest.mark.asyncio
    async def test_tool_error_results_are_marked(self) -> None:
        """Tool execution errors are marked with is_error flag."""
        stdout_lines = [
            json.dumps({
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "content_block": {
                        "type": "tool_use",
                        "id": "tool_123",
                        "name": "Read",
                        "input": {"file_path": "/nonexistent"},
                    }
                }
            }),
            json.dumps({
                "type": "assistant",
                "message": {
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": "tool_123",
                        "content": "File not found: /nonexistent",
                        "is_error": True,
                    }]
                }
            }),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                events = [e async for e in provider.send_message("Read /nonexistent")]

        tool_results = [e for e in events if isinstance(e, ToolResult)]
        assert len(tool_results) == 1
        assert tool_results[0].is_error is True
        assert "not found" in tool_results[0].result.lower()


# =============================================================================
# Behavioral Tests: Permission Handling
# =============================================================================


class TestPermissionHandling:
    """Tests for permission request and response flow."""

    @pytest.mark.asyncio
    async def test_user_can_approve_permission_request(self) -> None:
        """When Claude requests permission, user approval is sent back."""
        stdout_lines = [
            json.dumps({
                "type": "system",
                "subtype": "permission_request",
                "id": "perm_123",
                "tool": "Write",
                "args": {"file_path": "/tmp/test.txt", "content": "Hello"},
            }),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)
        permission_callback = AsyncMock(return_value=True)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(
                    model="sonnet",
                    permission_callback=permission_callback,
                )
                await provider.start()

                _ = [e async for e in provider.send_message("Write test.txt")]

        # Permission callback should have been called with tool and args
        permission_callback.assert_called_once_with("Write", {"file_path": "/tmp/test.txt", "content": "Hello"})

        # Verify permission response was sent
        stdin_writes = [call[0][0] for call in mock_process.stdin.write.call_args_list]
        # Should have sent user message and permission response
        assert len(stdin_writes) >= 2
        permission_response = json.loads(stdin_writes[-1].decode().strip())
        assert permission_response["type"] == "permission_response"
        assert permission_response["id"] == "perm_123"
        assert permission_response["approved"] is True

    @pytest.mark.asyncio
    async def test_user_can_deny_permission_request(self) -> None:
        """When user denies permission, denial is sent and error result yielded."""
        stdout_lines = [
            json.dumps({
                "type": "system",
                "subtype": "permission_request",
                "id": "perm_456",
                "tool": "Bash",
                "args": {"command": "rm -rf /"},
            }),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)
        permission_callback = AsyncMock(return_value=False)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(
                    model="sonnet",
                    permission_callback=permission_callback,
                )
                await provider.start()

                events = [e async for e in provider.send_message("Delete everything")]

        # Should yield a tool result indicating permission denied
        tool_results = [e for e in events if isinstance(e, ToolResult)]
        assert len(tool_results) == 1
        assert tool_results[0].is_error is True
        assert "permission denied" in tool_results[0].result.lower()

        # Permission response should indicate denial
        stdin_writes = [call[0][0] for call in mock_process.stdin.write.call_args_list]
        permission_response = json.loads(stdin_writes[-1].decode().strip())
        assert permission_response["approved"] is False

    @pytest.mark.asyncio
    async def test_no_permission_callback_auto_denies(self) -> None:
        """Without a permission callback, all requests are auto-denied."""
        stdout_lines = [
            json.dumps({
                "type": "system",
                "subtype": "permission_request",
                "id": "perm_789",
                "tool": "Write",
                "args": {"file_path": "/tmp/file.txt"},
            }),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")  # No callback
                await provider.start()

                events = [e async for e in provider.send_message("Write file")]

        # Should auto-deny
        tool_results = [e for e in events if isinstance(e, ToolResult)]
        assert len(tool_results) == 1
        assert tool_results[0].is_error is True
        assert "no permission handler" in tool_results[0].result.lower()


# =============================================================================
# Behavioral Tests: Session Persistence
# =============================================================================


class TestSessionPersistence:
    """Tests for session ID persistence across messages."""

    @pytest.mark.asyncio
    async def test_session_id_stored_after_completion(self) -> None:
        """Session ID from completion is stored for future messages."""
        stdout_lines = [
            json.dumps({"type": "assistant", "subtype": "text_delta", "text": "Hi!"}),
            json.dumps({"type": "result", "session_id": "sess_abc123", "usage": {}}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                # Initially no session ID
                assert provider.session_id is None

                # Consume the stream
                _ = [e async for e in provider.send_message("Hello")]

                # Session ID should be stored
                assert provider.session_id == "sess_abc123"


# =============================================================================
# Behavioral Tests: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error conditions and recovery."""

    @pytest.mark.asyncio
    async def test_claude_cli_not_found_raises_error(self) -> None:
        """If Claude CLI is not installed, a clear error is raised."""
        with patch("shutil.which", return_value=None):
            provider = StreamingClaudeCodeProvider(model="sonnet")
            with pytest.raises(StreamingClaudeCodeProviderError) as exc_info:
                await provider.start()

            assert "Claude Code CLI not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_error_events_are_yielded(self) -> None:
        """Error events from the stream are yielded to the caller."""
        error_event = {
            "type": "error",
            "message": "Something went wrong",
            "code": "INTERNAL_ERROR",
            "retryable": True,
        }
        stdout_lines = [
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Working..."}}}),
            json.dumps(error_event),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                events = [e async for e in provider.send_message("Do something")]

        # Should have text delta and then error
        assert isinstance(events[0], TextDelta)
        assert isinstance(events[1], StreamError)
        assert events[1].message == "Something went wrong"
        assert events[1].code == "INTERNAL_ERROR"
        assert events[1].retryable is True

    @pytest.mark.asyncio
    async def test_invalid_json_lines_are_skipped(self) -> None:
        """Malformed JSON lines are silently skipped."""
        stdout_lines = [
            "not valid json",
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Valid"}}}),
            "{incomplete json",
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                events = [e async for e in provider.send_message("Hello")]

        # Should only get the valid events
        assert len(events) == 2
        assert isinstance(events[0], TextDelta)
        assert isinstance(events[1], StreamComplete)


# =============================================================================
# Behavioral Tests: Provider Lifecycle
# =============================================================================


class TestProviderLifecycle:
    """Tests for provider start/stop and context manager usage."""

    @pytest.mark.asyncio
    async def test_provider_can_be_used_as_context_manager(self) -> None:
        """Provider works as an async context manager."""
        stdout_lines = [
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}}),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                async with StreamingClaudeCodeProvider(model="sonnet") as provider:
                    events = [e async for e in provider.send_message("Hello")]

        # Should have received events
        assert len(events) == 2

        # Process should have been cleaned up after message completion
        # (subprocess exits after --print mode response, we wait for it)
        mock_process.wait.assert_called()

    @pytest.mark.asyncio
    async def test_stop_terminates_subprocess(self) -> None:
        """Calling stop() terminates the subprocess cleanly."""
        mock_process = create_mock_process([])

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                provider = StreamingClaudeCodeProvider(model="sonnet")
                await provider.start()

                assert provider.is_running

                await provider.stop()

                mock_process.terminate.assert_called_once()
                assert not provider.is_running

    @pytest.mark.asyncio
    async def test_send_message_auto_starts_if_needed(self) -> None:
        """send_message() automatically starts the subprocess if not running."""
        stdout_lines = [
            json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}}}),
            json.dumps({"type": "result", "session_id": "sess_123"}),
        ]

        mock_process = create_mock_process(stdout_lines)

        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
                provider = StreamingClaudeCodeProvider(model="sonnet")
                # Don't call start() explicitly

                events = [e async for e in provider.send_message("Hello")]

        # Should have auto-started
        mock_exec.assert_called_once()
        assert len(events) == 2


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @pytest.mark.asyncio
    async def test_any_text_delta_content_is_preserved(self) -> None:
        """Text delta content is preserved exactly as received."""
        from hypothesis import given, settings
        from hypothesis import strategies as st

        @given(text=st.text(min_size=0, max_size=1000))
        @settings(max_examples=20)
        def check_text_preserved(text: str) -> None:
            # Create event and verify text is preserved
            event = TextDelta(text=text)
            assert event.text == text

        check_text_preserved()

    @pytest.mark.asyncio
    async def test_tool_call_input_dict_is_preserved(self) -> None:
        """Tool call input dictionaries are preserved exactly."""
        from hypothesis import given, settings
        from hypothesis import strategies as st

        @given(
            name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=["L", "N"])),
            input_dict=st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(st.text(), st.integers(), st.booleans()),
                max_size=5,
            ),
        )
        @settings(max_examples=20)
        def check_input_preserved(name: str, input_dict: dict[str, Any]) -> None:
            event = ToolCall(id="test_id", name=name, input=input_dict)
            assert event.name == name
            assert event.input == input_dict

        check_input_preserved()
