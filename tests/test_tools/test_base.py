import pytest
from pygent.tools.base import ToolDefinition, ToolRisk, tool


@pytest.mark.asyncio
async def test_tool_decorator_basic():
    @tool(name="test_tool", description="A test tool", risk=ToolRisk.LOW)
    async def sample_tool(x: int, y: str) -> str:
        """Sample docstring."""
        return f"{y}-{x}"

    # Check if definition was attached
    assert hasattr(sample_tool, "_tool_definition")
    definition: ToolDefinition = sample_tool._tool_definition

    assert definition.name == "test_tool"
    assert definition.description == "A test tool"
    assert definition.risk == ToolRisk.LOW

    # Check schema generation
    schema = definition.input_schema
    assert schema["type"] == "object"
    assert "x" in schema["properties"]
    assert "y" in schema["properties"]
    assert schema["properties"]["x"]["type"] == "integer"
    assert schema["properties"]["y"]["type"] == "string"
    assert "x" in schema["required"]
    assert "y" in schema["required"]


@pytest.mark.asyncio
async def test_tool_decorator_defaults():
    @tool(name="default_tool", description="Tool with defaults")
    async def default_tool(a: int, b: int = 10) -> int:
        return a + b

    definition: ToolDefinition = default_tool._tool_definition
    schema = definition.input_schema

    assert "a" in schema["required"]
    assert "b" not in schema["required"]


def test_missing_type_hints():
    with pytest.raises(ValueError, match="Missing type annotation"):

        @tool(name="bad_tool", description="Bad tool")
        async def bad_tool(x):
            pass


@pytest.mark.asyncio
async def test_tool_execution():
    @tool(name="exec_tool", description="Exec")
    async def exec_tool(val: str) -> str:
        return val.upper()

    result = await exec_tool("hello")
    assert result == "HELLO"
