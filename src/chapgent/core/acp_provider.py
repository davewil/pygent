"""ACP-based streaming provider for Claude Code.

This module provides a streaming interface to Claude Code CLI using the
Agent Client Protocol (ACP) SDK, enabling:
- Real-time streaming of responses via session_update callbacks
- Permission handling passed through to the application
- Session persistence across messages
- Reuse of user's existing Claude Code settings and OAuth authentication
"""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from acp import PROTOCOL_VERSION, spawn_agent_process, text_block
from acp.client.connection import ClientSideConnection
from acp.interfaces import Agent
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    AllowedOutcome,
    ClientCapabilities,
    CreateTerminalResponse,
    DeniedOutcome,
    FileSystemCapability,
    PermissionOption,
    ReadTextFileResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    ToolCallProgress,
    ToolCallStart,
    ToolCallUpdate,
    UserMessageChunk,
    AgentPlanUpdate,
    AvailableCommandsUpdate,
    CurrentModeUpdate,
    SessionInfoUpdate,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from chapgent.core.logging import logger


# =============================================================================
# Stream Event Types (preserved from stream_provider.py for API compatibility)
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
# ACP Client Implementation
# =============================================================================


class ChapgentACPClient:
    """ACP Client implementation that queues events for async iteration.

    This client receives callbacks from the ACP agent and converts them
    to our StreamEvent types, queuing them for consumption.
    """

    def __init__(
        self,
        event_queue: asyncio.Queue[StreamEvent | None],
        permission_callback: Callable[[str, dict[str, Any]], Awaitable[bool]] | None = None,
    ) -> None:
        self.event_queue = event_queue
        self.permission_callback = permission_callback
        self._pending_permission: asyncio.Future[bool] | None = None

    def on_connect(self, conn: Agent) -> None:
        """Called when connected to the agent. Required by ACP Client interface."""
        pass

    async def session_update(
        self,
        session_id: str,
        update: UserMessageChunk
        | AgentMessageChunk
        | AgentThoughtChunk
        | ToolCallStart
        | ToolCallProgress
        | AgentPlanUpdate
        | AvailableCommandsUpdate
        | CurrentModeUpdate
        | SessionInfoUpdate,
        **kwargs: Any,
    ) -> None:
        """Handle streaming session updates from the agent."""
        logger.info(f"session_update received: {type(update).__name__}")

        if isinstance(update, AgentMessageChunk):
            # Text delta from agent message - content is a TextContentBlock
            if update.content and hasattr(update.content, 'text') and update.content.text:
                await self.event_queue.put(TextDelta(text=update.content.text))

        elif isinstance(update, AgentThoughtChunk):
            # Thought/reasoning text (also show as text delta)
            if update.content and hasattr(update.content, 'text') and update.content.text:
                await self.event_queue.put(TextDelta(text=update.content.text))

        elif isinstance(update, ToolCallStart):
            # Tool call starting
            tool_name = update.title  # ACP uses 'title' for tool name
            tool_input = update.raw_input or {}
            logger.info(f"ToolCallStart: name={tool_name}, id={update.tool_call_id}, input={tool_input}")
            await self.event_queue.put(ToolCall(
                id=update.tool_call_id,
                name=tool_name,
                input=tool_input if isinstance(tool_input, dict) else {},
            ))

        elif isinstance(update, ToolCallProgress):
            # Tool call progress/result
            logger.info(f"ToolCallProgress: id={update.tool_call_id}, content_type={type(update.content).__name__}")
            if update.content:
                # Convert tool content to string
                content_str = str(update.content)
                is_error = getattr(update, 'is_error', False)
                logger.info(f"  content={content_str[:100]}..., is_error={is_error}")
                await self.event_queue.put(ToolResult(
                    id=update.tool_call_id,
                    result=content_str,
                    is_error=is_error,
                ))

        else:
            # Log ignored update types for debugging
            logger.debug(f"session_update ignored: {type(update).__name__}")

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Handle permission requests from the agent.

        This is called when the ACP agent needs permission to perform an operation.
        We delegate to the permission_callback if set, otherwise auto-deny.
        """
        tool_name = tool_call.title or "unknown"  # ACP uses 'title' for tool name
        tool_args = tool_call.raw_input or {}
        if not isinstance(tool_args, dict):
            tool_args = {}

        logger.info(f"=== PERMISSION REQUEST === tool={tool_name}, options={[o.option_id for o in options]}")
        logger.info(f"  tool_call_id={tool_call.tool_call_id}, input={tool_args}")

        if self.permission_callback:
            approved = await self.permission_callback(tool_name, tool_args)
            logger.info(f"  permission_callback returned: {approved}")
        else:
            # Auto-approve if no callback (for testing)
            approved = True
            logger.info("  no permission_callback, auto-approving")

        # Return the permission response with proper outcome format
        # The outcome must be AllowedOutcome(outcome="selected", option_id=...) or DeniedOutcome(outcome="cancelled")
        if approved:
            # Find an allow option (prefer allow_once over allow_always)
            option_id = "allow"  # Default
            for opt in options:
                if opt.kind in ("allow_once", "allow_always"):
                    option_id = opt.option_id
                    logger.info(f"  selected option: {opt.option_id} (kind={opt.kind})")
                    break
            outcome = AllowedOutcome(outcome="selected", option_id=option_id)
        else:
            logger.info("  denied - returning cancelled outcome")
            outcome = DeniedOutcome(outcome="cancelled")

        return RequestPermissionResponse(outcome=outcome)

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: Any
    ) -> WriteTextFileResponse:
        """Handle file write requests from the ACP agent.

        This is called when client capabilities are declared and the agent
        needs to write a file.
        """
        logger.info(f"=== WRITE_TEXT_FILE === path={path}, content_len={len(content)}")
        try:
            with open(path, "w") as f:
                f.write(content)
            logger.info(f"write_text_file: successfully wrote {len(content)} bytes to {path}")
            return WriteTextFileResponse()
        except Exception as e:
            logger.error(f"write_text_file error: {e}")
            raise

    async def read_text_file(
        self, path: str, session_id: str, limit: int | None = None, line: int | None = None, **kwargs: Any
    ) -> ReadTextFileResponse:
        """Handle file read requests from the ACP agent.

        This is called when client capabilities are declared and the agent
        needs to read a file.
        """
        logger.info(f"=== READ_TEXT_FILE === path={path}, limit={limit}, line={line}")
        try:
            with open(path, "r") as f:
                lines = f.readlines()

            # Handle line offset
            start_line = (line - 1) if line and line > 0 else 0
            lines = lines[start_line:]

            # Handle limit
            if limit and limit > 0:
                lines = lines[:limit]

            content = "".join(lines)
            logger.info(f"read_text_file: read {len(content)} bytes from {path}")
            return ReadTextFileResponse(content=content)
        except FileNotFoundError:
            logger.warning(f"read_text_file: file not found {path}")
            return ReadTextFileResponse(content=f"Error: File not found: {path}")
        except Exception as e:
            logger.error(f"read_text_file error: {e}")
            return ReadTextFileResponse(content=f"Error: {e}")

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[Any] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        """Handle terminal creation requests from the ACP agent.

        This is called when client capabilities are declared and the agent
        needs to run a command.
        """
        import uuid

        terminal_id = str(uuid.uuid4())
        logger.info(f"=== CREATE_TERMINAL === command={command}, args={args}, cwd={cwd}, terminal_id={terminal_id}")

        try:
            # Build full command
            full_command = command
            if args:
                full_command = f"{command} {' '.join(args)}"

            # Run the command
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )

            # Store the process for later output retrieval
            if not hasattr(self, "_terminals"):
                self._terminals: dict[str, asyncio.subprocess.Process] = {}
            self._terminals[terminal_id] = process

            logger.info(f"create_terminal: started process for '{full_command}', terminal_id={terminal_id}")
            return CreateTerminalResponse(terminal_id=terminal_id)
        except Exception as e:
            logger.error(f"create_terminal error: {e}")
            raise

    async def terminal_output(self, session_id: str, terminal_id: str, **kwargs: Any) -> TerminalOutputResponse:
        """Handle terminal output requests."""
        logger.info(f"=== TERMINAL_OUTPUT === terminal_id={terminal_id}")
        if not hasattr(self, "_terminals") or terminal_id not in self._terminals:
            logger.warning(f"terminal_output: terminal {terminal_id} not found")
            return TerminalOutputResponse(output="Terminal not found", truncated=False)

        process = self._terminals[terminal_id]
        try:
            # Try to read available output without blocking indefinitely
            if process.stdout:
                try:
                    output = await asyncio.wait_for(process.stdout.read(4096), timeout=0.1)
                    output_str = output.decode("utf-8", errors="replace")
                    logger.info(f"terminal_output: got {len(output_str)} bytes")
                    return TerminalOutputResponse(output=output_str, truncated=False)
                except asyncio.TimeoutError:
                    return TerminalOutputResponse(output="", truncated=False)
            return TerminalOutputResponse(output="", truncated=False)
        except Exception as e:
            logger.error(f"terminal_output error: {e}")
            return TerminalOutputResponse(output=f"Error: {e}", truncated=False)

    async def release_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> None:
        """Handle terminal release requests."""
        logger.info(f"release_terminal: terminal_id={terminal_id}")
        if hasattr(self, "_terminals") and terminal_id in self._terminals:
            del self._terminals[terminal_id]

    async def wait_for_terminal_exit(self, session_id: str, terminal_id: str, **kwargs: Any) -> WaitForTerminalExitResponse:
        """Handle terminal exit wait requests."""
        logger.info(f"=== WAIT_FOR_TERMINAL_EXIT === terminal_id={terminal_id}")
        if not hasattr(self, "_terminals") or terminal_id not in self._terminals:
            logger.warning(f"wait_for_terminal_exit: terminal {terminal_id} not found")
            return WaitForTerminalExitResponse(exit_code=1)

        process = self._terminals[terminal_id]
        try:
            exit_code = await process.wait()
            logger.info(f"wait_for_terminal_exit: exit_code={exit_code}")
            return WaitForTerminalExitResponse(exit_code=exit_code if exit_code >= 0 else None)
        except Exception as e:
            logger.error(f"wait_for_terminal_exit error: {e}")
            return WaitForTerminalExitResponse(exit_code=1)

    async def kill_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> None:
        """Handle terminal kill requests."""
        logger.info(f"kill_terminal: terminal_id={terminal_id}")
        if hasattr(self, "_terminals") and terminal_id in self._terminals:
            process = self._terminals[terminal_id]
            process.kill()
            del self._terminals[terminal_id]

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle extension methods."""
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle extension notifications."""
        pass


# =============================================================================
# ACP-Based Provider
# =============================================================================


class ACPClaudeCodeProviderError(Exception):
    """Error from the ACP Claude Code provider."""
    pass


class ACPClaudeCodeProvider:
    """ACP-based streaming provider for Claude Code.

    This provider uses the Agent Client Protocol SDK to communicate with
    Claude Code, providing robust subprocess lifecycle management and
    standardized event handling.

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
        """Initialize the ACP provider.

        Args:
            model: Model alias or full name to use.
            permission_callback: Async function called when permission is needed.
                Receives (tool_name, args) and should return True to approve.
            working_directory: Optional directory for Claude Code to work in.
        """
        self.model = model
        self.permission_callback = permission_callback
        self.working_directory = working_directory or os.getcwd()
        self._session_id: str | None = None
        self._connection: ClientSideConnection | None = None
        self._process: asyncio.subprocess.Process | None = None

    @property
    def session_id(self) -> str | None:
        """Get the current session ID for persistence."""
        return self._session_id

    @property
    def is_running(self) -> bool:
        """Check if the ACP connection is active."""
        return self._connection is not None

    async def start(self) -> None:
        """Start the ACP connection to Claude Code.

        Raises:
            ACPClaudeCodeProviderError: If Claude Code CLI is not found.
        """
        if self._connection is not None:
            return

        claude_path = shutil.which("claude")
        if not claude_path:
            raise ACPClaudeCodeProviderError(
                "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )

        # Note: spawn_agent_process is a context manager, we need to enter it
        # We'll manage this manually since we want persistent connection
        logger.debug(f"Starting ACP connection to Claude Code at {claude_path}")

    def _find_acp_adapter(self) -> str:
        """Find the claude-code-acp adapter binary.

        Looks in common locations:
        1. Global npm install (claude-code-acp in PATH)
        2. Local node_modules in working directory
        3. Local node_modules relative to this package
        4. Common global npm locations

        Returns:
            Path to claude-code-acp binary.

        Raises:
            ACPClaudeCodeProviderError: If adapter not found.
        """
        # Check global install
        global_path = shutil.which("claude-code-acp")
        if global_path:
            logger.debug(f"Found claude-code-acp in PATH: {global_path}")
            return global_path

        # Check local node_modules in working directory
        local_path = os.path.join(self.working_directory, "node_modules", ".bin", "claude-code-acp")
        if os.path.isfile(local_path):
            logger.debug(f"Found claude-code-acp in working dir: {local_path}")
            return local_path

        # Check relative to this package (for development)
        package_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        dev_path = os.path.join(package_dir, "node_modules", ".bin", "claude-code-acp")
        if os.path.isfile(dev_path):
            logger.debug(f"Found claude-code-acp in dev path: {dev_path}")
            return dev_path

        # Check home directory npm global install
        home_npm_path = os.path.expanduser("~/.npm/bin/claude-code-acp")
        if os.path.isfile(home_npm_path):
            logger.debug(f"Found claude-code-acp in home npm: {home_npm_path}")
            return home_npm_path

        logger.error(f"claude-code-acp not found. Checked: PATH, {local_path}, {dev_path}, {home_npm_path}")
        raise ACPClaudeCodeProviderError(
            "claude-code-acp adapter not found. Install with: npm install -g @zed-industries/claude-code-acp"
        )

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
            ACPClaudeCodeProviderError: If ACP communication fails.
        """
        logger.info("ACPClaudeCodeProvider.send_message called")

        adapter_path = self._find_acp_adapter()
        logger.info(f"Using ACP adapter at: {adapter_path}")

        # Create event queue for streaming
        event_queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

        # Create ACP client
        client = ChapgentACPClient(
            event_queue=event_queue,
            permission_callback=self.permission_callback,
        )

        try:
            # Use spawn_agent_process context manager with the ACP adapter
            # The adapter speaks ACP and uses Claude Agent SDK internally
            logger.info(f"Spawning ACP adapter with cwd={self.working_directory}")
            async with spawn_agent_process(
                client,
                adapter_path,
                cwd=self.working_directory,
            ) as (connection, process):
                logger.info("ACP connection established")

                # Initialize the connection with client capabilities
                # This tells the ACP adapter that we can handle file and terminal
                # operations, which routes those requests through our client methods
                # instead of Claude Code's built-in tools.
                logger.info("Initializing ACP connection with client capabilities...")
                client_capabilities = ClientCapabilities(
                    fs=FileSystemCapability(
                        read_text_file=True,
                        write_text_file=True,
                    ),
                    terminal=True,
                )
                logger.info(f"Client capabilities: fs.read={client_capabilities.fs.read_text_file}, fs.write={client_capabilities.fs.write_text_file}, terminal={client_capabilities.terminal}")
                await connection.initialize(
                    protocol_version=PROTOCOL_VERSION,
                    client_capabilities=client_capabilities,
                )
                logger.info("ACP initialized")

                # Create or resume session
                if self._session_id:
                    logger.info(f"Resuming session {self._session_id}")
                    await connection.resume_session(
                        cwd=self.working_directory,
                        session_id=self._session_id,
                    )
                else:
                    logger.info("Creating new session...")
                    session_response = await connection.new_session(
                        cwd=self.working_directory,
                        mcp_servers=[],
                    )
                    self._session_id = session_response.session_id
                    logger.info(f"Created session {self._session_id}")

                # Send the prompt in a background task so we can yield events as they arrive
                logger.info(f"Sending prompt: {content[:100]}...")

                prompt_done = asyncio.Event()
                prompt_error: Exception | None = None

                async def run_prompt() -> None:
                    nonlocal prompt_error
                    try:
                        await connection.prompt(
                            prompt=[text_block(content)],
                            session_id=self._session_id,
                        )
                    except Exception as e:
                        prompt_error = e
                    finally:
                        # Signal that we're done by putting None in queue
                        await event_queue.put(None)
                        prompt_done.set()

                # Start the prompt task
                logger.info("Starting prompt task...")
                prompt_task = asyncio.create_task(run_prompt())

                # Yield events as they arrive
                logger.info("Waiting for events...")
                try:
                    event_num = 0
                    while True:
                        event = await event_queue.get()
                        if event is None:
                            # Prompt finished
                            logger.info("Received end-of-stream signal")
                            break
                        event_num += 1
                        logger.info(f"Yielding event {event_num}: {type(event).__name__}")
                        yield event
                finally:
                    # Ensure task is awaited
                    await prompt_task

                # Check for errors
                if prompt_error:
                    raise prompt_error

                logger.info("Prompt completed")

                # Yield completion event
                yield StreamComplete(
                    session_id=self._session_id or "",
                    usage={},  # ACP doesn't expose usage in the same way
                )

        except Exception as e:
            logger.error(f"ACP error: {e}")
            yield StreamError(
                message=str(e),
                retryable=False,
            )

    async def stop(self) -> None:
        """Stop the ACP connection."""
        self._connection = None
        self._process = None

    async def __aenter__(self) -> ACPClaudeCodeProvider:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.stop()
