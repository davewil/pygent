from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import litellm

from pygent.tools.base import ToolDefinition


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    content: list[TextBlock | ToolUseBlock]
    stop_reason: str | None


class LLMProvider:
    """Wrapper around litellm for LLM interactions.

    Provides a clean async interface and handles tool formatting.
    """

    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send completion request to LLM.

        Args:
            messages: List of message dicts (role, content).
            tools: List of available tool definitions.
            max_tokens: Max tokens to generate.

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
            messages=messages,
            tools=formatted_tools,
            max_tokens=max_tokens,
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

        return LLMResponse(content=content, stop_reason=choice.finish_reason)
