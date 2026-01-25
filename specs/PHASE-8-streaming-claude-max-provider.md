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

## Progress

### Phase 1: StreamingClaudeCodeProvider (COMPLETE)

**Date:** 2026-01-23

Created `src/chapgent/core/stream_provider.py` with:

- **Stream Event Dataclasses:**
  - `TextDelta`: Streaming text chunks
  - `ToolCall`: Tool invocation events
  - `ToolResult`: Tool execution results (with is_error flag)
  - `PermissionRequest`: Permission requests from Claude Code
  - `StreamComplete`: Stream finished with session ID and usage
  - `StreamError`: Error events with code and retryable flag

- **StreamingClaudeCodeProvider Class:**
  - Manages persistent subprocess with stdin/stdout
  - Parses NDJSON stream via `_parse_event()`
  - Yields streaming events via async iterator
  - Handles permission requests via callback
  - Auto-denies if no permission callback provided
  - Session persistence via `session_id` property
  - Context manager support (`async with`)
  - Clean subprocess termination with timeout

- **Error Handling:**
  - `StreamingClaudeCodeProviderError` for subprocess failures
  - `StreamError` events for stream-level errors
  - Graceful handling of broken pipes and connection resets
  - Invalid JSON lines silently skipped

**Tests:** 16 behavioral tests in `tests/test_core/test_stream_provider.py`:
- TestTextStreaming: 2 tests
- TestToolExecution: 2 tests
- TestPermissionHandling: 3 tests
- TestSessionPersistence: 1 test
- TestErrorHandling: 3 tests
- TestProviderLifecycle: 3 tests
- TestPropertyBased: 2 tests

**Total tests:** 1606 passed

### Phase 2: Streaming Loop Integration (COMPLETE)

**Date:** 2026-01-23

Added `streaming_conversation_loop` to `src/chapgent/core/loop.py`:

- **New Function:**
  - `streaming_conversation_loop(provider, user_message, cancellation_token)` - Async iterator for Claude Max streaming
  - Takes `StreamingClaudeCodeProvider` instead of `Agent`
  - Yields `LoopEvent` instances converted from `StreamEvent` types
  - Handles cancellation via `CancellationToken`

- **Event Mapping (`_convert_stream_event`):**
  - `TextDelta` → `LoopEvent(type="text_delta")` for incremental text
  - `ToolCall` → `LoopEvent(type="tool_call")` with JSON-serialized input
  - `ToolResult` → `LoopEvent(type="tool_result")`
  - `StreamComplete` → `LoopEvent(type="finished")` with token totals
  - `StreamError` → `LoopEvent(type="llm_error")` with error details

- **Cancellation Support:**
  - Checks cancellation before starting
  - Checks cancellation between events during streaming
  - Yields `cancelled` event with reason on cancellation
  - Always yields final `finished` event

- **Error Handling:**
  - Catches provider exceptions and yields `llm_error` event
  - Graceful handling of stream errors from Claude Code

**Tests:** 10 behavioral tests added to `tests/test_core/test_loop.py`:
- TestStreamingLoopTextDeltas: 2 tests (text_delta events, empty deltas)
- TestStreamingLoopToolCalls: 2 tests (tool_call events, JSON serialized input)
- TestStreamingLoopCompletion: 2 tests (finished event, token tracking)
- TestStreamingLoopErrors: 2 tests (stream errors, provider exceptions)
- TestStreamingLoopCancellation: 2 tests (before start, during streaming)

**Total tests:** 1616 passed (24 loop tests, 16 stream provider tests)

### Phase 3: CLI Integration (COMPLETE)

**Date:** 2026-01-24

Updated `src/chapgent/cli/bootstrap.py` for streaming mode:

- **StreamingClaudeCodeProvider Integration:**
  - When `auth_mode == "max"`, uses `StreamingClaudeCodeProvider` instead of `ClaudeCodeProvider`
  - Maps model names to Claude Code aliases (sonnet, opus, haiku)
  - Passes working directory to streaming provider

- **Permission Callback Wiring:**
  - Creates async permission callback that invokes `app.get_permission()`
  - Wires callback to `streaming_provider.permission_callback`
  - Enables Claude Code tool permissions to flow through Chapgent TUI

- **Early Return for Streaming Mode:**
  - In streaming mode, skips Agent creation (Claude Code handles tools internally)
  - Returns app directly with streaming_provider set

**Files Modified:**
- `src/chapgent/cli/bootstrap.py`: Import StreamingClaudeCodeProvider, wire permission callback
- `tests/test_cli.py`: Update tests to expect StreamingClaudeCodeProvider in max mode

### Phase 4: TUI Streaming Support (COMPLETE)

**Date:** 2026-01-24

Updated `src/chapgent/tui/app.py` for streaming display:

- **ChapgentApp Enhancements:**
  - Added `streaming_provider` parameter to `__init__`
  - Added `_streaming_content` buffer for accumulating text deltas
  - `on_input_submitted` checks for streaming_provider first

- **New Method `run_streaming_agent_loop()`:**
  - Uses `streaming_conversation_loop` from core.loop
  - Creates streaming message placeholder via `panel.append_streaming_message()`
  - Accumulates `text_delta` events and updates message incrementally
  - Handles `tool_call` and `tool_result` events in tool panel
  - Shows errors via `append_assistant_message()`
  - Finalizes streaming message on `finished` event

- **Event Handling:**
  - `text_delta`: Accumulates content, updates streaming message
  - `tool_call`: Shows in tool panel with progress tracking
  - `tool_result`: Updates tool panel with result
  - `llm_error`: Shows error message in conversation
  - `finished`: Finalizes streaming message

**Tests:** 8 behavioral tests in `tests/test_tui/test_streaming.py`:
- TestStreamingMode: 4 tests (provider setup, text deltas, message accumulation, errors)
- TestStreamingPermissions: 1 test (permission callback wiring)
- TestStreamingToolDisplay: 2 tests (tool calls and results in panel)
- TestStreamingWithNoProvider: 1 test (error handling when no provider)

**Total tests:** 1624 passed (8 new streaming TUI tests)

### Phase 5: Refactor to Agent Client Protocol SDK (COMPLETE)

**Status:** Complete
**Date:** 2026-01-24

**Motivation:**

The current custom subprocess/stream-json implementation has issues with:
- Fragile subprocess lifecycle management (process exits after each `--print` response)
- Cleanup logic that breaks when requests are interrupted mid-stream
- Manual NDJSON parsing that may not match all edge cases
- Session management complexity with `--resume`

The `agent-client-protocol` Python SDK provides a standardized, robust implementation.

**SDK:** `agent-client-protocol` (PyPI) - https://github.com/agentclientprotocol/python-sdk

**Key SDK Components:**
- `Client` class - manages JSON-RPC communication over stdio
- `spawn_agent_process()` - helper to spawn the agent subprocess
- `session_update()` callback - receives streaming events
- Built-in permission handling via protocol methods

**Note from Zed Integration:**
Zed uses `@zed-industries/claude-code-acp` as an ACP adapter for Claude Code:
- Authentication is handled by Claude Code directly (not passed through ACP)
- The ACP layer handles protocol translation cleanly
- Subprocess lifecycle is managed by the SDK

**Implementation Plan:**

1. **Add Dependency**
   ```toml
   # pyproject.toml
   dependencies = [
       "agent-client-protocol>=0.1.0",
       # ... existing deps
   ]
   ```

2. **Create ACP-Based Provider**

   New file: `src/chapgent/core/acp_provider.py`

   ```python
   from agent_client_protocol import Client, spawn_agent_process
   from collections.abc import AsyncIterator
   from typing import Any, Callable, Awaitable
   import asyncio

   # Keep existing event dataclasses for API compatibility
   from chapgent.core.stream_provider import (
       TextDelta, ToolCall, ToolResult,
       PermissionRequest, StreamComplete, StreamError,
       StreamEvent
   )

   class ACPClaudeCodeProvider:
       """Claude Code provider using Agent Client Protocol."""

       def __init__(
           self,
           model: str = "sonnet",
           permission_callback: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None,
           working_directory: str | None = None,
       ) -> None:
           self.model = model
           self.permission_callback = permission_callback
           self.working_directory = working_directory
           self._client: Client | None = None
           self._session_id: str | None = None

       async def start(self) -> None:
           """Initialize the ACP client and spawn Claude Code."""
           process = await spawn_agent_process(
               ["claude", "--model", self.model],
               cwd=self.working_directory
           )
           self._client = Client(process.stdin, process.stdout)
           await self._client.initialize()

       async def send_message(self, content: str) -> AsyncIterator[StreamEvent]:
           """Send message and yield streaming events."""
           if self._client is None:
               await self.start()

           events_queue = asyncio.Queue()

           async def session_update(event):
               # Map ACP events to our event types
               await events_queue.put(self._map_event(event))

           # Send via ACP with streaming callback
           result = await self._client.send_message(
               content,
               session_id=self._session_id,
               session_update=session_update
           )

           # Yield all queued events
           while not events_queue.empty():
               yield await events_queue.get()

           # Update session and yield completion
           self._session_id = result.get("session_id")
           yield StreamComplete(
               session_id=self._session_id or "",
               usage=result.get("usage", {})
           )
   ```

3. **Map ACP Events to Existing Types**

   | ACP Event Type | Our Type |
   |---------------|----------|
   | `content_block_delta` with `text_delta` | `TextDelta` |
   | `content_block_start` with `tool_use` | `ToolCall` |
   | `tool_result` | `ToolResult` |
   | Error events | `StreamError` |

4. **Handle Permissions via ACP**

   ACP provides built-in permission handling:
   - Register permission handler with client
   - When permission is requested, invoke `permission_callback`
   - Return response via ACP's permission response mechanism

5. **Update TUI Integration**

   Replace provider instantiation in `src/chapgent/tui/app.py`:
   ```python
   # Before
   from chapgent.core.stream_provider import StreamingClaudeCodeProvider

   # After
   from chapgent.core.acp_provider import ACPClaudeCodeProvider
   ```

   The streaming loop should work unchanged since we preserve the event type interface.

6. **Keep Old Provider as Fallback (Optional)**

   Keep `stream_provider.py` with deprecation warning for fallback.

**Files to Modify:**

| File | Change |
|------|--------|
| `pyproject.toml` | Add `agent-client-protocol` dependency |
| `src/chapgent/core/acp_provider.py` | New file - ACP-based provider |
| `src/chapgent/core/stream_provider.py` | Add deprecation warning (optional) |
| `src/chapgent/tui/app.py` | Import new provider |
| `tests/test_core/test_stream_provider.py` | Update/add tests for new provider |

**Verification:**

1. **Unit tests:** Run existing tests adapted for new implementation
2. **Integration test:** Launch TUI, send message, verify streaming works
3. **Multi-message test:** Send 2+ messages, verify session persistence
4. **Interruption test:** Send message, interrupt with new, verify no stale state
5. **Permission test:** Trigger tool requiring permission, verify callback works

```bash
# Run tests
uv run pytest tests/test_core/test_stream_provider.py -v

# Manual TUI test
uv run python -m chapgent.tui.app
```

**Risks and Mitigations:**

| Risk | Mitigation |
|------|------------|
| ACP SDK version incompatibility | Pin to specific version, test thoroughly |
| Different event format than expected | Map events carefully, add logging |
| Session management differences | Verify resume functionality works |

**Implementation Notes:**

Implemented `ACPClaudeCodeProvider` in `src/chapgent/core/acp_provider.py` which:
- Uses `spawn_agent_process()` context manager to spawn Claude Code subprocess
- Implements `ChapgentACPClient` class that handles ACP callbacks:
  - `session_update()` - receives streaming updates and maps to our event types
  - `request_permission()` - handles permission requests via callback
- Maps ACP events (`AgentMessageChunk`, `ToolCallStart`, etc.) to existing `TextDelta`, `ToolCall`, etc. event types
- Preserves API compatibility with the old `StreamingClaudeCodeProvider`

**Files Changed:**
- `pyproject.toml` - Added `agent-client-protocol>=0.1.0` dependency
- `src/chapgent/core/acp_provider.py` - New ACP-based provider (created)
- `src/chapgent/core/loop.py` - Updated imports to use ACPClaudeCodeProvider
- `src/chapgent/cli/bootstrap.py` - Updated imports to use ACPClaudeCodeProvider
- `src/chapgent/tui/app.py` - Updated type hints and removed old provider-specific cleanup
- `tests/test_cli.py` - Updated mocks to use ACPClaudeCodeProvider
- `tests/test_core/test_loop.py` - Updated imports and mocks
- `tests/test_tui/test_streaming.py` - Updated imports

**Test Results:** 1625 passed, 1 skipped
