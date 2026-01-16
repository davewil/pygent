from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pygent.tools.base import ToolDefinition


class ToolRegistry:
    """Central registry for all available tools.

    Provides lookup by name and serialization for LLM.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition | Callable) -> None:
        """Register a tool definition.

        Args:
            tool: The tool definition or decorated function to register.
        """
        if isinstance(tool, ToolDefinition):
            definition = tool
        elif hasattr(tool, "_tool_definition"):
            definition = tool._tool_definition  # type: ignore
        else:
            raise ValueError(f"Invalid tool: {tool}. Must be ToolDefinition or decorated function.")

        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool definition by name.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The tool definition if found, None otherwise.
        """
        return self._tools.get(name)

    def list_definitions(self) -> list[dict[str, Any]]:
        """List all tool definitions for LLM consumption.

        Returns:
            A list of dictionary representations of the tools.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]
