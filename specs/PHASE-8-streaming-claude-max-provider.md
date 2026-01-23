# Plan: Implement Streaming Claude Max Provider with Permission Passthrough

## Overview

Replace the current subprocess-per-request approach (`claude --print`) with a **persistent streaming connection** using Claude CLI's native `stream-json` mode. This enables:
- Real-time streaming of responses
- Proper permission handling passed through to Chapgent TUI
- Session persistence via `--resume`
- Reuse of user's existing Claude Code settings and OAuth authentication

## Why Not ACP?

Initially considered `@zed-industries/claude-code-acp`, but:
- **Requires API key** - doesn't support Claude Max OAuth authentication
- Claude CLI's native `--output-format stream-json` already provides streaming
- Works with existing Claude Max login

## Current State

**File:** `src/chapgent/core/providers.py` (lines 202-316)

Current `ClaudeCodeProvider`:
- Spawns `claude --print --output-format json` per request
- Waits for full response before returning
- No streaming
- No permission negotiation
- Must pass `--dangerously-skip-permissions` for file writes

## Claude CLI Stream-JSON Protocol

Using `claude --print --input-format stream-json --output-format stream-json`:

**Input (NDJSON to stdin):**
```json
{"type": "user_message", "content": "Write a hello.py file"}
```

**Output (NDJSON from stdout):**
```json
{"type": "assistant", "subtype": "text_delta", "text": "I'll create"}
{"type": "assistant", "subtype": "tool_use", "name": "Write", "id": "xyz", "input": {...}}
{"type": "system", "subtype": "permission_request", "tool": "Write", "args": {...}, "id": "req_1"}
{"type": "result", "subtype": "success", "result": "...", "session_id": "..."}
```

**Permission Response (to stdin):**
```json
{"type": "permission_response", "id": "req_1", "approved": true}
```

## Architecture Changes

### New Files

1. **`src/chapgent/core/stream_provider.py`** - Streaming Claude Max provider
   - `StreamingClaudeCodeProvider` class
   - Manages persistent subprocess with stdin/stdout
   - Parses NDJSON stream
   - Yields streaming events
   - Handles permission requests via callback

### Modified Files

1. **`src/chapgent/core/providers.py`**
   - Add `StreamEvent` dataclasses for streaming
   - Keep `ClaudeCodeProvider` as non-streaming fallback

2. **`src/chapgent/core/loop.py`**
   - Add support for streaming provider (yield text deltas as they arrive)
   - Handle permission events from stream

3. **`src/chapgent/cli.py`**
   - Initialize streaming provider when `auth_mode = "claude_max"`
   - Wire permission callback to TUI's permission system

4. **`src/chapgent/tui/app.py`**
   - Handle streaming text updates (append incrementally)
   - Show Claude Code permission requests in TUI modal

## Detailed Implementation

### 1. StreamingClaudeCodeProvider (`src/chapgent/core/stream_provider.py`)

```python
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Awaitable, Any
import asyncio
import json
import shutil


@dataclass
class TextDelta:
    """Streaming text chunk."""
    text: str


@dataclass
class ToolCall:
    """Tool invocation event."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class PermissionRequest:
    """Permission request from Claude Code."""
    id: str
    tool: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    """Tool execution result."""
    id: str
    result: str


@dataclass
class StreamComplete:
    """Stream finished."""
    session_id: str
    usage: dict[str, int]


StreamEvent = TextDelta | ToolCall | PermissionRequest | ToolResult | StreamComplete


class StreamingClaudeCodeProvider:
    """Streaming provider for Claude Max using stream-json protocol."""

    def __init__(
        self,
        model: str = "sonnet",
        permission_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
    ):
        self.model = model
        self.permission_callback = permission_callback
        self._process: asyncio.subprocess.Process | None = None
        self._session_id: str | None = None

    async def start(self) -> None:
        """Start persistent Claude Code subprocess."""
        claude_path = shutil.which("claude")
        if not claude_path:
            raise RuntimeError("Claude Code CLI not found")

        cmd = [
            claude_path,
            "--print",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--model", self.model,
        ]

        # Resume session if we have one
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def send_message(self, content: str) -> AsyncIterator[StreamEvent]:
        """Send message and stream response events."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            await self.start()

        # Send user message as NDJSON
        msg = json.dumps({"type": "user_message", "content": content})
        self._process.stdin.write(f"{msg}\n".encode())
        await self._process.stdin.drain()

        # Read streaming response
        async for line in self._read_lines():
            event = self._parse_event(line)
            if event:
                # Handle permission requests inline
                if isinstance(event, PermissionRequest) and self.permission_callback:
                    approved = await self.permission_callback(event.tool, event.args)
                    await self._send_permission_response(event.id, approved)
                else:
                    yield event

                if isinstance(event, StreamComplete):
                    self._session_id = event.session_id
                    break

    async def _read_lines(self) -> AsyncIterator[str]:
        """Read NDJSON lines from stdout."""
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            yield line.decode().strip()

    def _parse_event(self, line: str) -> StreamEvent | None:
        """Parse NDJSON line into StreamEvent."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None

        msg_type = data.get("type")
        subtype = data.get("subtype")

        if msg_type == "assistant" and subtype == "text_delta":
            return TextDelta(text=data.get("text", ""))

        if msg_type == "assistant" and subtype == "tool_use":
            return ToolCall(
                id=data.get("id", ""),
                name=data.get("name", ""),
                input=data.get("input", {}),
            )

        if msg_type == "system" and subtype == "permission_request":
            return PermissionRequest(
                id=data.get("id", ""),
                tool=data.get("tool", ""),
                args=data.get("args", {}),
            )

        if msg_type == "result":
            return StreamComplete(
                session_id=data.get("session_id", ""),
                usage=data.get("usage", {}),
            )

        return None

    async def _send_permission_response(self, request_id: str, approved: bool) -> None:
        """Send permission response back to Claude Code."""
        msg = json.dumps({
            "type": "permission_response",
            "id": request_id,
            "approved": approved,
        })
        self._process.stdin.write(f"{msg}\n".encode())
        await self._process.stdin.drain()

    async def stop(self) -> None:
        """Terminate subprocess."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None
```

### 2. Integration with Loop (`src/chapgent/core/loop.py`)

Add a new streaming loop variant that yields text deltas immediately:

```python
async def streaming_conversation_loop(
    provider: StreamingClaudeCodeProvider,
    user_message: str,
) -> AsyncIterator[LoopEvent]:
    """Streaming conversation loop for Claude Max mode."""

    async for event in provider.send_message(user_message):
        if isinstance(event, TextDelta):
            yield LoopEvent(type="text_delta", content=event.text)

        elif isinstance(event, ToolCall):
            yield LoopEvent(
                type="tool_call",
                tool_name=event.name,
                tool_args=event.input,
            )

        elif isinstance(event, ToolResult):
            yield LoopEvent(
                type="tool_result",
                tool_name=event.id,
                result=event.result,
            )

        elif isinstance(event, StreamComplete):
            yield LoopEvent(
                type="finished",
                usage=event.usage,
            )
```

### 3. Permission Flow

```
User sends message
    ↓
StreamingClaudeCodeProvider.send_message() called
    ↓
Claude Code streams response (NDJSON)
    ↓
On PermissionRequest event:
    ↓
permission_callback(tool, args) invoked
    ↓
Chapgent TUI shows permission modal
    ↓
User approves/denies
    ↓
Provider sends permission_response to stdin
    ↓
Claude Code continues or skips tool
    ↓
Continue streaming
```

### 4. TUI Integration (`src/chapgent/tui/app.py`)

Handle streaming text deltas and Claude Code permission requests:

```python
async def run_streaming_agent_loop(self, user_input: str):
    """Handle streaming responses from Claude Max."""

    async for event in self.streaming_provider.send_message(user_input):
        if event.type == "text_delta":
            # Append text incrementally (no newline)
            self.conversation.append_text_delta(event.content)

        elif event.type == "tool_call":
            # Show tool execution in panel
            self.tool_panel.add_tool(event.tool_name, event.tool_args)

        elif event.type == "finished":
            self.conversation.finalize_message()
```

Permission callback wired in `cli.py`:

```python
async def claude_code_permission_callback(tool: str, args: dict) -> bool:
    """Show Claude Code permission request in TUI."""
    # Map to Chapgent's permission system
    return await app.show_permission_modal(
        f"Claude Code wants to use: {tool}",
        details=json.dumps(args, indent=2),
    )
```

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `src/chapgent/core/stream_provider.py` | **Create** | Streaming Claude Code provider |
| `src/chapgent/core/loop.py` | Modify | Add streaming loop variant |
| `src/chapgent/cli.py` | Modify | Initialize streaming provider, wire callbacks |
| `src/chapgent/tui/app.py` | Modify | Handle text deltas, permission modals |
| `src/chapgent/tui/conversation.py` | Modify | Add `append_text_delta()` method |

## Implementation Steps

1. **Create `stream_provider.py`** with `StreamingClaudeCodeProvider`
2. **Add streaming loop** in `loop.py`
3. **Wire provider in `cli.py`** with permission callback
4. **Update TUI** to handle `text_delta` events incrementally
5. **Add permission modal** for Claude Code tool requests
6. **Test** with file write operations

## Verification

1. Run Chapgent with `llm.auth_mode = "claude_max"`
2. Send: "Create a file called test.txt with hello world"
3. Verify:
   - Text streams incrementally (not all at once)
   - Permission modal appears for Write tool
   - After approval, file is created
   - Session persists for follow-up messages

## Open Questions

1. **Stream-JSON exact format**: Need to verify actual NDJSON format from `claude --output-format stream-json` (may differ from documented)
2. **Error handling**: How does Claude Code signal errors in stream mode?
3. **Cancellation**: How to send cancel signal mid-stream?
