from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, cast

from pydantic import TypeAdapter

P = ParamSpec("P")
R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)


class ToolFunction(Protocol[P, R_co]):
    """Protocol for functions decorated with @tool."""

    _tool_definition: ToolDefinition

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[R_co]:
        ...


class ToolRisk(str, Enum):
    LOW = "low"  # Auto-approved
    MEDIUM = "medium"  # Prompts unless session override
    HIGH = "high"  # Always prompts


class ToolCategory(str, Enum):
    """Categories for organizing tools."""

    FILESYSTEM = "filesystem"
    GIT = "git"
    SEARCH = "search"
    WEB = "web"
    SHELL = "shell"
    TESTING = "testing"


@dataclass
class ToolDefinition:
    """Tool definition for LLM consumption.

    Attributes:
        name: Unique tool identifier.
        description: What the tool does (shown to LLM).
        input_schema: JSON Schema for parameters.
        risk: Risk level for permission system.
        category: Tool category for organization.
        function: The actual async function to execute.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    risk: ToolRisk
    category: ToolCategory
    function: Callable[..., Awaitable[Any]]


def _generate_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Generate JSON schema from function type hints.

    This uses Pydantic's TypeAdapter to generate schemas for arguments.
    It builds a single object schema where keys are argument names.
    """
    sig = inspect.signature(func)
    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        if param.annotation == inspect.Parameter.empty:
            raise ValueError(f"Missing type annotation for parameter '{name}' in tool '{func.__name__}'")

        # Create a TypeAdapter for the parameter type
        adapter = TypeAdapter(param.annotation)
        # Get the JSON schema for this specific type
        param_schema = adapter.json_schema()

        # Extract description from docstring if possible (basic implementation here)
        # Real implementation would parse docstrings more robustly

        properties[name] = param_schema

        if param.default == inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def tool(
    name: str,
    description: str,
    risk: ToolRisk = ToolRisk.LOW,
    category: ToolCategory = ToolCategory.SHELL,
) -> Callable[[Callable[P, Awaitable[R]]], ToolFunction[P, R]]:
    """Decorator to register a function as an agent tool.

    Automatically generates JSON schema from type hints.

    Args:
        name: Unique tool identifier.
        description: What the tool does (shown to LLM).
        risk: Risk level for permission system.
        category: Tool category for organization.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> ToolFunction[P, R]:
        # Generate schema
        schema = _generate_schema(func)

        # Create definition
        definition = ToolDefinition(
            name=name,
            description=description,
            input_schema=schema,
            risk=risk,
            category=category,
            function=func,
        )

        # Store definition on the function wrapper for registry discovery
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await func(*args, **kwargs)

        # Use Any cast to avoid mypy attribute error during assignment
        wrapper_any = cast(Any, wrapper)
        wrapper_any._tool_definition = definition
        return cast(ToolFunction[P, R], wrapper)

    return decorator
