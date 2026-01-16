from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from pydantic import TypeAdapter

P = ParamSpec("P")
R = TypeVar("R")


class ToolRisk(str, Enum):
    LOW = "low"  # Auto-approved
    MEDIUM = "medium"  # Prompts unless session override
    HIGH = "high"  # Always prompts


@dataclass
class ToolDefinition:
    """Tool definition for LLM consumption.

    Attributes:
        name: Unique tool identifier.
        description: What the tool does (shown to LLM).
        input_schema: JSON Schema for parameters.
        risk: Risk level for permission system.
        function: The actual async function to execute.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    risk: ToolRisk
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
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator to register a function as an agent tool.

    Automatically generates JSON schema from type hints.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        # Generate schema
        schema = _generate_schema(func)

        # Create definition
        definition = ToolDefinition(
            name=name,
            description=description,
            input_schema=schema,
            risk=risk,
            function=func,  # type: ignore
        )

        # Store definition on the function wrapper for registry discovery
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await func(*args, **kwargs)

        wrapper._tool_definition = definition
        return wrapper

    return decorator
