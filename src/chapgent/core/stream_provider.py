"""Streaming provider for Claude Max using Claude CLI's stream-json protocol.

This module provides a streaming interface to Claude Code CLI, enabling:
- Real-time streaming of responses via text deltas
- Permission handling passed through to the application
- Session persistence across messages
- Reuse of user's existing Claude Code settings and OAuth authentication
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from chapgent.core.logging import logger

# =============================================================================
# Stream Event Types
# =============================================================================


@dataclass
class TextDelta:
    """Streaming text chunk from the assistant."""

    text: str


@dataclass
class ToolCall:
    """Tool invocation event from the assistant."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResult:
    """Tool execution result."""

    id: str
    result: str
    is_error: bool = False


@dataclass
class PermissionRequest:
    """Permission request from Claude Code for a tool operation."""

    id: str
    tool: str
    args: dict[str, Any]


@dataclass
class StreamComplete:
    """Stream finished event."""

    session_id: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class StreamError:
    """Error event from the stream."""

    message: str
    code: str | None = None
    retryable: bool = False


StreamEvent = TextDelta | ToolCall | ToolResult | PermissionRequest | StreamComplete | StreamError


# =============================================================================
# Streaming Provider
# =============================================================================


class StreamingClaudeCodeProviderError(Exception):
    """Error from the streaming Claude Code provider."""

    pass


class StreamingClaudeCodeProvider:
    """Streaming provider for Claude Max using stream-json protocol.

    This provider maintains a persistent subprocess connection to Claude CLI
    using the stream-json input/output format for real-time streaming.

    Attributes:
        model: Model alias ('sonnet', 'opus', 'haiku') or full name.
        permission_callback: Async callback invoked when Claude Code requests
            permission for a tool operation. Returns True to approve.
    """

    def __init__(
        self,
        model: str = "sonnet",
        permission_callback: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None,
        working_directory: str | None = None,
    ) -> None:
        """Initialize the streaming provider.

        Args:
            model: Model alias or full name to use.
            permission_callback: Async function called when permission is needed.
                Receives (tool_name, args) and should return True to approve.
            working_directory: Optional directory for Claude Code to work in.
        """
        self.model = model
        self.permission_callback = permission_callback
        self.working_directory = working_directory
        self._process: asyncio.subprocess.Process | None = None
        self._session_id: str | None = None
        self._started = False

    @property
    def session_id(self) -> str | None:
        """Get the current session ID for persistence."""
        return self._session_id

    @property
    def is_running(self) -> bool:
        """Check if the subprocess is currently running."""
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        """Start the persistent Claude Code subprocess.

        Raises:
            StreamingClaudeCodeProviderError: If Claude Code CLI is not found.
        """
        if self._started and self.is_running:
            return

        claude_path = shutil.which("claude")
        if not claude_path:
            raise StreamingClaudeCodeProviderError(
                "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )

        cmd = [
            claude_path,
            "--print",
            "--verbose",  # Required for stream-json output
            "--include-partial-messages",  # Enable streaming text deltas
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--model",
            self.model,
        ]

        # Resume session if we have one
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_directory,
        )
        self._started = True

    async def send_message(self, content: str) -> AsyncIterator[StreamEvent]:
        """Send a message and stream response events.

        This method sends a user message to Claude Code and yields streaming
        events as they arrive. Permission requests are handled via the
        permission_callback if provided.

        Args:
            content: The user message content to send.

        Yields:
            StreamEvent instances for each event in the stream:
            - TextDelta: Incremental text from the assistant
            - ToolCall: Tool invocation request
            - ToolResult: Tool execution result
            - StreamComplete: Stream finished with session ID
            - StreamError: Error occurred

        Raises:
            StreamingClaudeCodeProviderError: If subprocess communication fails.
        """
        logger.debug("StreamingClaudeCodeProvider.send_message called")

        if not self._started or not self.is_running:
            logger.debug("Starting subprocess...")
            await self.start()
            logger.debug("Subprocess started")

        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise StreamingClaudeCodeProviderError("Subprocess not properly initialized")

        # Send user message as NDJSON (Claude Code stream-json format)
        msg = json.dumps({
            "type": "user",
            "message": {"role": "user", "content": content}
        })
        logger.debug(f"Sending message: {msg[:100]}...")
        try:
            self._process.stdin.write(f"{msg}\n".encode())
            await self._process.stdin.drain()
            logger.debug("Message sent and drained")
        except (BrokenPipeError, ConnectionResetError) as e:
            raise StreamingClaudeCodeProviderError(f"Failed to send message: {e}") from e

        # Read streaming response
        logger.debug("Starting to read lines from subprocess")
        line_count = 0
        async for line in self._read_lines():
            line_count += 1
            logger.debug(f"Read line {line_count}: {line[:100]}...")
            event = self._parse_event(line)
            if event is None:
                logger.debug(f"Line {line_count} parsed to None, skipping")
                continue
            logger.debug(f"Parsed event type: {type(event).__name__}")

            # Handle permission requests via callback
            if isinstance(event, PermissionRequest):
                if self.permission_callback:
                    approved = await self.permission_callback(event.tool, event.args)
                    await self._send_permission_response(event.id, approved)
                    if not approved:
                        # Yield a tool result indicating permission denied
                        yield ToolResult(
                            id=event.id,
                            result=f"Permission denied for {event.tool}",
                            is_error=True,
                        )
                else:
                    # Auto-deny if no callback provided
                    await self._send_permission_response(event.id, False)
                    yield ToolResult(
                        id=event.id,
                        result=f"Permission denied for {event.tool} (no permission handler)",
                        is_error=True,
                    )
                continue

            yield event

            # Stop iteration on stream completion
            if isinstance(event, StreamComplete):
                self._session_id = event.session_id
                break

            # Stop iteration on error
            if isinstance(event, StreamError):
                break

    async def _read_lines(self) -> AsyncIterator[str]:
        """Read NDJSON lines from subprocess stdout.

        Yields:
            Decoded and stripped lines from stdout.
        """
        if self._process is None or self._process.stdout is None:
            return

        while True:
            try:
                line = await self._process.stdout.readline()
            except (asyncio.CancelledError, Exception):
                break

            if not line:
                break

            yield line.decode().strip()

    def _parse_event(self, line: str) -> StreamEvent | None:
        """Parse an NDJSON line into a StreamEvent.

        Claude Code stream-json format:
        - {"type":"stream_event","event":{"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}}
        - {"type":"stream_event","event":{"type":"tool_use",...}} for tool calls
        - {"type":"result","subtype":"success",...} for completion
        - {"type":"system","subtype":"permission_request",...} for permissions

        Args:
            line: Raw JSON line from the stream.

        Returns:
            Parsed StreamEvent or None if the line couldn't be parsed.
        """
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        msg_type = data.get("type")
        subtype = data.get("subtype")

        # Handle streaming events (content deltas, tool calls)
        if msg_type == "stream_event":
            event = data.get("event", {})
            event_type = event.get("type")

            # Text delta from content_block_delta
            if event_type == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    return TextDelta(text=delta.get("text", ""))

            # Tool call from content_block_start (tool_use type)
            if event_type == "content_block_start":
                content_block = event.get("content_block", {})
                if content_block.get("type") == "tool_use":
                    return ToolCall(
                        id=content_block.get("id", ""),
                        name=content_block.get("name", ""),
                        input=content_block.get("input", {}),
                    )

            return None  # Skip other stream events

        # Tool result from assistant message
        if msg_type == "assistant":
            message = data.get("message", {})
            content = message.get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    return ToolResult(
                        id=block.get("tool_use_id", ""),
                        result=block.get("content", ""),
                        is_error=block.get("is_error", False),
                    )
            return None  # Skip full assistant messages (we use stream deltas)

        # Permission request from system
        if msg_type == "system" and subtype == "permission_request":
            return PermissionRequest(
                id=data.get("id", ""),
                tool=data.get("tool", ""),
                args=data.get("args", {}),
            )

        # Stream result (completion)
        if msg_type == "result":
            return StreamComplete(
                session_id=data.get("session_id", ""),
                usage=data.get("usage", {}),
            )

        # Error event
        if msg_type == "error":
            return StreamError(
                message=data.get("message", "Unknown error"),
                code=data.get("code"),
                retryable=data.get("retryable", False),
            )

        return None

    async def _send_permission_response(self, request_id: str, approved: bool) -> None:
        """Send a permission response back to Claude Code.

        Args:
            request_id: The ID of the permission request.
            approved: Whether the permission was approved.
        """
        if self._process is None or self._process.stdin is None:
            return

        msg = json.dumps({
            "type": "permission_response",
            "id": request_id,
            "approved": approved,
        })
        try:
            self._process.stdin.write(f"{msg}\n".encode())
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Process may have exited

    async def stop(self) -> None:
        """Terminate the subprocess cleanly."""
        if self._process is None:
            return

        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()
        finally:
            self._process = None
            self._started = False

    async def __aenter__(self) -> StreamingClaudeCodeProvider:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.stop()
