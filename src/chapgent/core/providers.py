from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import litellm

from chapgent.tools.base import ToolDefinition

# =============================================================================
# LLM Exceptions
# =============================================================================


class LLMError(Exception):
    """Base exception for LLM-related errors.

    Attributes:
        message: Human-readable error message.
        retryable: Whether the error is transient and can be retried.
        status_code: HTTP status code if applicable.
        original_error: The underlying exception that caused this error.
    """

    def __init__(
        self,
        message: str,
        retryable: bool = False,
        status_code: int | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.original_error = original_error


class RateLimitError(LLMError):
    """Rate limit exceeded (HTTP 429).

    This error is retryable - wait and try again.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        original_error: Exception | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, retryable=True, status_code=status_code, original_error=original_error)
        self.retry_after = retry_after


class NetworkError(LLMError):
    """Network-related error (timeout, connection refused, etc.).

    This error is retryable - network issues are often transient.
    """

    def __init__(
        self,
        message: str = "Network error",
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, retryable=True, status_code=None, original_error=original_error)


class AuthenticationError(LLMError):
    """Authentication failed (HTTP 401/403).

    This error is NOT retryable - fix the API key.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: int = 401,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, retryable=False, status_code=status_code, original_error=original_error)


class InvalidRequestError(LLMError):
    """Invalid request (HTTP 400).

    This error is NOT retryable - fix the request.
    """

    def __init__(
        self,
        message: str = "Invalid request",
        status_code: int = 400,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, retryable=False, status_code=status_code, original_error=original_error)


class ServiceUnavailableError(LLMError):
    """Service unavailable (HTTP 500/502/503/504).

    This error is retryable - service issues are often transient.
    """

    def __init__(
        self,
        message: str = "Service unavailable",
        status_code: int = 503,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, retryable=True, status_code=status_code, original_error=original_error)


def classify_llm_error(error: Exception) -> LLMError:
    """Classify an exception into the appropriate LLMError type.

    Args:
        error: The original exception from litellm or underlying provider.

    Returns:
        An appropriate LLMError subclass with retryable flag set.
    """
    error_str = str(error).lower()

    # Check for litellm specific exception types
    if hasattr(litellm, "RateLimitError") and isinstance(error, litellm.RateLimitError):
        return RateLimitError(str(error), original_error=error)

    if hasattr(litellm, "AuthenticationError") and isinstance(error, litellm.AuthenticationError):
        return AuthenticationError(str(error), original_error=error)

    if hasattr(litellm, "BadRequestError") and isinstance(error, litellm.BadRequestError):
        return InvalidRequestError(str(error), original_error=error)

    if hasattr(litellm, "ServiceUnavailableError") and isinstance(error, litellm.ServiceUnavailableError):
        return ServiceUnavailableError(str(error), original_error=error)

    # Check for network-related errors by message patterns
    network_patterns = ["timeout", "connection", "network", "socket", "dns", "refused"]
    if any(pattern in error_str for pattern in network_patterns):
        return NetworkError(str(error), original_error=error)

    # Check for rate limit patterns
    rate_limit_patterns = ["rate limit", "rate_limit", "too many requests", "429"]
    if any(pattern in error_str for pattern in rate_limit_patterns):
        return RateLimitError(str(error), original_error=error)

    # Check for auth patterns
    auth_patterns = ["authentication", "unauthorized", "invalid api key", "api key", "401", "403"]
    if any(pattern in error_str for pattern in auth_patterns):
        return AuthenticationError(str(error), original_error=error)

    # Check for service unavailable patterns
    service_patterns = ["service unavailable", "503", "502", "504", "500", "internal server error"]
    if any(pattern in error_str for pattern in service_patterns):
        return ServiceUnavailableError(str(error), original_error=error)

    # Default: non-retryable generic error
    return LLMError(str(error), retryable=False, original_error=error)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class TokenUsage:
    """Token usage statistics from an LLM response.

    Attributes:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Total tokens used (prompt + completion).
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: list[TextBlock | ToolUseBlock]
    stop_reason: str | None
    usage: TokenUsage | None = None


class ClaudeCodeProvider:
    """Provider that delegates to Claude Code CLI for Claude Max subscription.

    Spawns claude --print as a subprocess and uses its OAuth authentication.
    Claude Code runs its own agent loop with tools like Bash, Read, Edit, etc.
    """

    def __init__(self, model: str = "sonnet") -> None:
        """Initialize Claude Code provider.

        Args:
            model: Model alias ('sonnet', 'opus', 'haiku') or full name.
        """
        self.model = model
        self._session_id: str | None = None

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],  # noqa: ARG002 - Claude Code uses its own tools
        max_output_tokens: int = 4096,  # noqa: ARG002 - Claude Code manages this
    ) -> LLMResponse:
        """Send completion request via Claude Code CLI.

        Note: Claude Code runs its own agent loop and executes tools internally.
        The tools parameter is ignored - Claude Code uses its own tool set.

        Args:
            messages: List of message dicts (role, content).
            tools: Ignored - Claude Code uses its own tools.
            max_output_tokens: Ignored - Claude Code manages output length.

        Returns:
            LLMResponse containing the final text result.
        """
        import asyncio
        import json
        import shutil

        # Find claude binary
        claude_path = shutil.which("claude")
        if not claude_path:
            raise LLMError("Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code")

        # Extract the last user message as the prompt
        prompt = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    prompt = content
                elif isinstance(content, list):
                    # Extract text from content blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            prompt = block.get("text", "")
                            break
                break

        if not prompt:
            raise InvalidRequestError("No user message found in messages")

        # Build command
        cmd = [claude_path, "--print", "--output-format", "json", "--model", self.model]

        # Resume session if we have one
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        # Run claude CLI
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate(input=prompt.encode())

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise LLMError(f"Claude Code CLI failed: {error_msg}")

        # Parse JSON response
        try:
            result = json.loads(stdout.decode())
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse Claude Code response: {e}") from e

        # Store session ID for continuation
        self._session_id = result.get("session_id")

        # Extract result text
        result_text = result.get("result", "")

        # Build usage from response
        usage_data = result.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0) + usage_data.get("cache_read_input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=(
                usage_data.get("input_tokens", 0)
                + usage_data.get("cache_read_input_tokens", 0)
                + usage_data.get("output_tokens", 0)
            ),
        )

        # Determine stop reason
        stop_reason = "end_turn" if result.get("subtype") == "success" else "error"

        return LLMResponse(
            content=[TextBlock(text=result_text)],
            stop_reason=stop_reason,
            usage=usage,
        )


class LLMProvider:
    """Wrapper around litellm for LLM interactions.

    Provides a clean async interface and handles tool formatting.
    Supports custom base URLs and headers for LiteLLM proxy/gateway support.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.extra_headers = extra_headers

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
        max_output_tokens: int = 4096,
    ) -> LLMResponse:
        """Send completion request to LLM.

        Args:
            messages: List of message dicts (role, content).
            tools: List of available tool definitions.
            max_output_tokens: Maximum tokens in the model's response.

        Returns:
            LLMResponse containing content blocks and stop reason.
        """
        # Format tools for litellm
        formatted_tools = None
        if tools:
            formatted_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in tools
            ]

        response = await litellm.acompletion(
            model=self.model,
            api_key=self.api_key,
            api_base=self.base_url,
            extra_headers=self.extra_headers,
            messages=messages,
            tools=formatted_tools,
            max_tokens=max_output_tokens,  # litellm uses max_tokens
        )

        choice = response.choices[0]
        message = choice.message

        content: list[TextBlock | ToolUseBlock] = []

        if message.content:
            content.append(TextBlock(text=message.content))

        if message.tool_calls:
            for tool_call in message.tool_calls:
                # litellm returns arguments as string JSON sometimes, or dict?
                # usually it handles it, but let's assume it might need parsing if it's a string
                # or rely on litellm object structure.
                # functionality-wise, litellm returns an object with `arguments` usually as a string JSON for OAI.
                import json

                args = tool_call.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}  # Fail-safe or raise?

                content.append(ToolUseBlock(id=tool_call.id, name=tool_call.function.name, input=args))

        # Parse token usage from response
        usage = None
        if hasattr(response, "usage") and response.usage is not None:
            usage = TokenUsage(
                prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
            )

        return LLMResponse(content=content, stop_reason=choice.finish_reason, usage=usage)
