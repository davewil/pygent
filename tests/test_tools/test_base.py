import pytest

from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk, tool


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


class TestToolCategory:
    """Tests for ToolCategory enum."""

    def test_category_values(self):
        """Test that all expected categories exist."""
        assert ToolCategory.FILESYSTEM == "filesystem"
        assert ToolCategory.GIT == "git"
        assert ToolCategory.SEARCH == "search"
        assert ToolCategory.WEB == "web"
        assert ToolCategory.SHELL == "shell"

    def test_category_from_string(self):
        """Test creating category from string value."""
        assert ToolCategory("filesystem") == ToolCategory.FILESYSTEM
        assert ToolCategory("git") == ToolCategory.GIT
        assert ToolCategory("search") == ToolCategory.SEARCH
        assert ToolCategory("web") == ToolCategory.WEB
        assert ToolCategory("shell") == ToolCategory.SHELL

    def test_category_invalid_string(self):
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError):
            ToolCategory("invalid")


@pytest.mark.asyncio
async def test_tool_decorator_with_category():
    """Test tool decorator with category parameter."""

    @tool(
        name="categorized_tool",
        description="A categorized tool",
        risk=ToolRisk.MEDIUM,
        category=ToolCategory.FILESYSTEM,
    )
    async def categorized_tool(path: str) -> str:
        return path

    definition: ToolDefinition = categorized_tool._tool_definition

    assert definition.name == "categorized_tool"
    assert definition.risk == ToolRisk.MEDIUM
    assert definition.category == ToolCategory.FILESYSTEM


@pytest.mark.asyncio
async def test_tool_decorator_default_category():
    """Test that default category is SHELL."""

    @tool(name="default_cat_tool", description="No explicit category")
    async def default_cat_tool(x: int) -> int:
        return x

    definition: ToolDefinition = default_cat_tool._tool_definition

    assert definition.category == ToolCategory.SHELL
