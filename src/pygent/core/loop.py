from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pygent.core.providers import LLMResponse
from pygent.core.providers import TextBlock as ProvTextBlock
from pygent.core.providers import ToolUseBlock as ProvToolUseBlock
from pygent.session.models import ContentBlock, Message, TextBlock, ToolResultBlock, ToolUseBlock

if TYPE_CHECKING:
    from pygent.core.agent import Agent


@dataclass
class LoopEvent:
    type: str  # "text", "tool_call", "tool_result", "param_error", "permission_denied", "finished", "cache_hit"
    content: str | None = None
    tool_name: str | None = None
    tool_id: str | None = None
    cached: bool = False


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
) -> AsyncIterator[LoopEvent]:
    """Execute the agent loop until no more tool calls."""

    while True:
        # Convert messages for LLM
        llm_msgs = _convert_to_llm_messages(messages)

        # Get available tools
        tool_list = []
        for tool_info in agent.tools.list_definitions():
            tool_def = agent.tools.get(tool_info["name"])
            if tool_def:
                tool_list.append(tool_def)

        response: LLMResponse = await agent.provider.complete(
            messages=llm_msgs,
            tools=tool_list,
        )

        # Process Response
        assistant_blocks: list[ContentBlock] = []
        tool_invocations = []

        for block in response.content:
            if isinstance(block, ProvTextBlock):
                yield LoopEvent(type="text", content=block.text)
                assistant_blocks.append(TextBlock(text=block.text))

            elif isinstance(block, ProvToolUseBlock):
                yield LoopEvent(type="tool_call", tool_name=block.name, tool_id=block.id)
                assistant_blocks.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
                tool_invocations.append(block)

        # Append assistant message
        if assistant_blocks:
            messages.append(Message(role="assistant", content=assistant_blocks, timestamp=datetime.now()))

        # If no tools, we are done
        if not tool_invocations:
            break

        # Execute Tools
        result_blocks: list[ContentBlock] = []

        for tool_use in tool_invocations:
            # Check permissions
            tool_def = agent.tools.get(tool_use.name)
            if not tool_def:
                result = f"Error: Tool {tool_use.name} not found."
                result_blocks.append(ToolResultBlock(tool_use_id=tool_use.id, content=result, is_error=True))
                yield LoopEvent(type="tool_result", content=result, tool_name=tool_use.name)
                continue

            allowed = await agent.permissions.check(tool_name=tool_use.name, risk=tool_def.risk, args=tool_use.input)

            if not allowed:
                result = "Error: Permission denied by user."
                yield LoopEvent(type="permission_denied", tool_name=tool_use.name)
                result_blocks.append(ToolResultBlock(tool_use_id=tool_use.id, content=result, is_error=True))
                continue

            # Execute (with caching)
            try:
                # Check cache first
                cached_result = await agent.tool_cache.get(tool_use.name, tool_use.input)
                if cached_result is not None:
                    result = cached_result
                    yield LoopEvent(type="tool_result", content=result, tool_name=tool_use.name, cached=True)
                    result_blocks.append(ToolResultBlock(tool_use_id=tool_use.id, content=result, is_error=False))
                    continue

                # Dispatch to tool function
                # tool_def.function is async
                output = await tool_def.function(**tool_use.input)
                result = str(output)

                # Cache the result
                await agent.tool_cache.set(tool_use.name, tool_use.input, result)

                yield LoopEvent(type="tool_result", content=result, tool_name=tool_use.name)
                result_blocks.append(ToolResultBlock(tool_use_id=tool_use.id, content=result, is_error=False))

            except Exception as e:
                result = f"Error execution tool: {str(e)}"
                yield LoopEvent(type="tool_result", content=result, tool_name=tool_use.name)
                result_blocks.append(ToolResultBlock(tool_use_id=tool_use.id, content=result, is_error=True))

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

    yield LoopEvent(type="finished")
