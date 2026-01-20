from __future__ import annotations

from typing import Any

from chapgent.tools.base import ToolCategory, ToolDefinition, ToolFunction


class ToolRegistry:
    """Central registry for all available tools.

    Provides lookup by name and serialization for LLM.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition | ToolFunction[Any, Any]) -> None:
        """Register a tool definition.

        Args:
            tool: The tool definition or decorated function to register.
        """
        if isinstance(tool, ToolDefinition):
            definition = tool
        else:
            definition = tool._tool_definition

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

    def list_all(self) -> list[ToolDefinition]:
        """List all registered tools.

        Returns:
            A list of all tool definitions.
        """
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> list[ToolDefinition]:
        """List tools in a specific category.

        Args:
            category: The category to filter by.

        Returns:
            A list of tool definitions in the specified category.
        """
        return [tool for tool in self._tools.values() if tool.category == category]

    def get_categories(self) -> list[ToolCategory]:
        """Get all categories that have at least one tool.

        Returns:
            A sorted list of categories with registered tools.
        """
        categories = {tool.category for tool in self._tools.values()}
        return sorted(categories, key=lambda c: c.value)
