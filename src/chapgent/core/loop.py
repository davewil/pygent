from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from chapgent.core.cancellation import CancellationToken
from chapgent.core.parallel import execute_tools_parallel
from chapgent.core.providers import LLMError, LLMResponse, TokenUsage, classify_llm_error
from chapgent.core.providers import TextBlock as ProvTextBlock
from chapgent.core.providers import ToolUseBlock as ProvToolUseBlock
from chapgent.session.models import ContentBlock, Message, TextBlock, ToolResultBlock, ToolUseBlock

# Default limits
DEFAULT_MAX_ITERATIONS = 50

if TYPE_CHECKING:
    from chapgent.core.agent import Agent


@dataclass
class LoopEvent:
    """Event emitted during conversation loop execution.

    Attributes:
        type: Event type - "text", "tool_call", "tool_result", "param_error",
              "permission_denied", "finished", "cache_hit", "iteration_limit_reached",
              "token_limit_reached", "llm_error", "cancelled".
        content: Event content (text or tool result).
        tool_name: Name of the tool involved (for tool events).
        tool_id: Unique ID of the tool call (for matching calls to results).
        cached: Whether the result came from cache.
        timestamp: When the event occurred (for progress tracking).
        usage: Token usage for this iteration (for token tracking).
        iteration: Current iteration number.
        total_tokens: Cumulative total tokens used across all iterations.
        error_type: Type of error (for llm_error events).
        error_message: Error message (for llm_error events).
        retryable: Whether the error can be retried (for llm_error events).
        cancel_reason: Reason for cancellation (for cancelled events).
    """

    type: str
    content: str | None = None
    tool_name: str | None = None
    tool_id: str | None = None
    cached: bool = False
    timestamp: datetime | None = None
    usage: TokenUsage | None = None
    iteration: int | None = None
    total_tokens: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    cancel_reason: str | None = None


def _convert_to_llm_messages(messages: list[Message]) -> list[dict[str, Any]]:
    llm_messages = []
    for msg in messages:
        if isinstance(msg.content, str):
            llm_messages.append({"role": msg.role, "content": msg.content})
            continue

        # Handle list of blocks
        content_buffer = []
        tool_calls = []

        # Check if this message is purely tool results
        is_tool_result = all(isinstance(b, ToolResultBlock) for b in msg.content)

        if is_tool_result:
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    llm_messages.append({"role": "tool", "tool_call_id": block.tool_use_id, "content": block.content})
            continue

        # Normal message (user or assistant)
        for block in msg.content:
            if isinstance(block, TextBlock):
                content_buffer.append(block.text)
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {"name": block.name, "arguments": json.dumps(block.input)},
                    }
                )

        llm_msg: dict[str, Any] = {"role": msg.role}
        if content_buffer:
            llm_msg["content"] = "\n".join(content_buffer)
        if tool_calls and msg.role == "assistant":
            llm_msg["tool_calls"] = tool_calls

        llm_messages.append(llm_msg)

    return llm_messages


async def conversation_loop(
    agent: Agent,
    messages: list[Message],
    system_prompt: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int | None = None,
    cancellation_token: CancellationToken | None = None,
) -> AsyncIterator[LoopEvent]:
    """Execute the agent loop until no more tool calls.

    Args:
        agent: The agent instance with provider, tools, and permissions.
        messages: List of conversation messages.
        system_prompt: Optional system prompt to prepend to the conversation.
        max_iterations: Maximum number of iterations before graceful exit (default: 50).
        max_tokens: Maximum total tokens to use before graceful exit (None = unlimited).
        cancellation_token: Optional token for cancelling execution. When the token
            is cancelled, the loop will exit gracefully after the current operation.

    Yields:
        LoopEvent instances for each step of the conversation.
    """
    iteration = 0
    total_tokens_used = 0

    while True:
        # Check cancellation at start of iteration
        if cancellation_token is not None and cancellation_token.is_cancelled:
            yield LoopEvent(
                type="cancelled",
                content="Operation cancelled by user",
                cancel_reason=cancellation_token.reason,
                iteration=iteration,
                total_tokens=total_tokens_used,
                timestamp=datetime.now(),
            )
            break

        # Check iteration limit
        if iteration >= max_iterations:
            yield LoopEvent(
                type="iteration_limit_reached",
                content=f"Reached maximum iterations limit ({max_iterations})",
                iteration=iteration,
                total_tokens=total_tokens_used,
                timestamp=datetime.now(),
            )
            break

        iteration += 1
        # Convert messages for LLM
        llm_msgs = _convert_to_llm_messages(messages)

        # Prepend system message if provided
        if system_prompt:
            llm_msgs = [{"role": "system", "content": system_prompt}] + llm_msgs

        # Get available tools
        tool_list = []
        for tool_info in agent.tools.list_definitions():
            tool_def = agent.tools.get(tool_info["name"])
            if tool_def:
                tool_list.append(tool_def)

        # Call LLM with error handling
        try:
            response: LLMResponse = await agent.provider.complete(
                messages=llm_msgs,
                tools=tool_list,
            )
        except Exception as e:
            # Classify the error
            llm_error: LLMError = classify_llm_error(e) if not isinstance(e, LLMError) else e

            yield LoopEvent(
                type="llm_error",
                content=llm_error.message,
                error_type=type(llm_error).__name__,
                error_message=llm_error.message,
                retryable=llm_error.retryable,
                iteration=iteration,
                total_tokens=total_tokens_used,
                timestamp=datetime.now(),
            )
            # Exit loop on error - caller can decide to retry
            break

        # Track token usage
        iteration_tokens = 0
        if response.usage:
            iteration_tokens = response.usage.total_tokens
            total_tokens_used += iteration_tokens

        # Check token limit (after response, before processing)
        if max_tokens is not None and total_tokens_used > max_tokens:
            yield LoopEvent(
                type="token_limit_reached",
                content=f"Reached maximum token limit ({max_tokens}). Used: {total_tokens_used}",
                iteration=iteration,
                total_tokens=total_tokens_used,
                usage=response.usage,
                timestamp=datetime.now(),
            )
            break

        # Process Response
        assistant_blocks: list[ContentBlock] = []
        tool_invocations = []

        for block in response.content:
            if isinstance(block, ProvTextBlock):
                yield LoopEvent(
                    type="text",
                    content=block.text,
                    iteration=iteration,
                    total_tokens=total_tokens_used,
                    usage=response.usage,
                )
                assistant_blocks.append(TextBlock(text=block.text))

            elif isinstance(block, ProvToolUseBlock):
                yield LoopEvent(
                    type="tool_call",
                    tool_name=block.name,
                    tool_id=block.id,
                    timestamp=datetime.now(),
                    iteration=iteration,
                    total_tokens=total_tokens_used,
                    usage=response.usage,
                )
                assistant_blocks.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
                tool_invocations.append(block)

        # Append assistant message
        if assistant_blocks:
            messages.append(Message(role="assistant", content=assistant_blocks, timestamp=datetime.now()))

        # If no tools, we are done
        if not tool_invocations:
            break

        # Execute Tools (with parallel execution where safe)
        result_blocks: list[ContentBlock] = []

        # Build list of tool calls with definitions
        tool_calls: list[tuple[ProvToolUseBlock, Any]] = []
        tool_not_found: list[ProvToolUseBlock] = []

        for tool_use in tool_invocations:
            tool_def = agent.tools.get(tool_use.name)
            if not tool_def:
                tool_not_found.append(tool_use)
            else:
                tool_calls.append((tool_use, tool_def))

        # Handle tools not found
        for tool_use in tool_not_found:
            result = f"Error: Tool {tool_use.name} not found."
            result_blocks.append(ToolResultBlock(tool_use_id=tool_use.id, content=result, is_error=True))
            yield LoopEvent(type="tool_result", content=result, tool_name=tool_use.name)

        # Execute valid tool calls with parallel execution
        if tool_calls:
            results = await execute_tools_parallel(tool_calls, agent, cancellation_token)

            for tool_result in results:
                # Yield appropriate event type
                if tool_result.is_error and "Permission denied" in tool_result.result:
                    yield LoopEvent(
                        type="permission_denied",
                        tool_name=tool_result.tool_name,
                        tool_id=tool_result.tool_use_id,
                        timestamp=datetime.now(),
                    )
                else:
                    yield LoopEvent(
                        type="tool_result",
                        content=tool_result.result,
                        tool_name=tool_result.tool_name,
                        tool_id=tool_result.tool_use_id,
                        cached=tool_result.was_cached,
                        timestamp=datetime.now(),
                    )

                result_blocks.append(
                    ToolResultBlock(
                        tool_use_id=tool_result.tool_use_id,
                        content=tool_result.result,
                        is_error=tool_result.is_error,
                    )
                )

        # Check cancellation after tool execution (let tools finish first)
        if cancellation_token is not None and cancellation_token.is_cancelled:
            # Still append results so the conversation state is consistent
            if result_blocks:
                messages.append(Message(role="user", content=result_blocks))
            yield LoopEvent(
                type="cancelled",
                content="Operation cancelled after tool execution",
                cancel_reason=cancellation_token.reason,
                iteration=iteration,
                total_tokens=total_tokens_used,
                timestamp=datetime.now(),
            )
            break

        # Append Tool Results
        if result_blocks:
            messages.append(
                Message(
                    role="user",
                    # Tools are part of user/tool role logic, but Message model limits. Spec implies User or Tool role?
                    # We used "tool" role in conversion if ToolResultBlock.
                    # So we can use "user" here but convert based on block type.
                    content=result_blocks,
                )
            )

    yield LoopEvent(
        type="finished",
        iteration=iteration,
        total_tokens=total_tokens_used,
        timestamp=datetime.now(),
    )
