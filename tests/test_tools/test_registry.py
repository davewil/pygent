from hypothesis import given
from hypothesis import strategies as st

from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk
from chapgent.tools.registry import ToolRegistry


def create_dummy_tool(
    name: str,
    category: ToolCategory = ToolCategory.SHELL,
    risk: ToolRisk = ToolRisk.LOW,
) -> ToolDefinition:
    async def dummy_func() -> None:
        pass

    return ToolDefinition(
        name=name,
        description="A dummy tool",
        input_schema={"type": "object"},
        risk=risk,
        category=category,
        function=dummy_func,
    )


def test_register_and_get():
    registry = ToolRegistry()
    tool = create_dummy_tool("test_tool")

    registry.register(tool)
    retrieved = registry.get("test_tool")

    assert retrieved is tool
    assert retrieved.name == "test_tool"


def test_get_nonexistent():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_register_overwrite():
    registry = ToolRegistry()
    tool1 = create_dummy_tool("test_tool")
    tool2 = create_dummy_tool("test_tool")  # Same name
    tool2.description = "Updated description"

    registry.register(tool1)
    registry.register(tool2)

    retrieved = registry.get("test_tool")
    assert retrieved is tool2
    assert retrieved.description == "Updated description"


def test_list_definitions():
    registry = ToolRegistry()
    tool1 = create_dummy_tool("tool1")
    tool2 = create_dummy_tool("tool2")

    registry.register(tool1)
    registry.register(tool2)

    defs = registry.list_definitions()
    assert len(defs) == 2

    # Verify structure suitable for LLM
    names = sorted([d["name"] for d in defs])
    assert names == ["tool1", "tool2"]

    assert "description" in defs[0]
    assert "input_schema" in defs[0]


@given(st.text(min_size=1))
def test_hypothesis_register_retrieve(name):
    # Property: For any valid name, if we register a tool with that name,
    # we should be able to retrieve it back.
    registry = ToolRegistry()
    tool = create_dummy_tool(name)
    registry.register(tool)

    assert registry.get(name) is tool


class TestRegistryCategories:
    """Tests for registry category methods."""

    def test_list_all(self):
        """Test listing all registered tools."""
        registry = ToolRegistry()
        tool1 = create_dummy_tool("tool1", ToolCategory.FILESYSTEM)
        tool2 = create_dummy_tool("tool2", ToolCategory.GIT)

        registry.register(tool1)
        registry.register(tool2)

        all_tools = registry.list_all()
        assert len(all_tools) == 2
        assert tool1 in all_tools
        assert tool2 in all_tools

    def test_list_by_category(self):
        """Test filtering tools by category."""
        registry = ToolRegistry()
        fs_tool1 = create_dummy_tool("fs1", ToolCategory.FILESYSTEM)
        fs_tool2 = create_dummy_tool("fs2", ToolCategory.FILESYSTEM)
        git_tool = create_dummy_tool("git1", ToolCategory.GIT)

        registry.register(fs_tool1)
        registry.register(fs_tool2)
        registry.register(git_tool)

        fs_tools = registry.list_by_category(ToolCategory.FILESYSTEM)
        assert len(fs_tools) == 2
        assert fs_tool1 in fs_tools
        assert fs_tool2 in fs_tools
        assert git_tool not in fs_tools

        git_tools = registry.list_by_category(ToolCategory.GIT)
        assert len(git_tools) == 1
        assert git_tool in git_tools

    def test_list_by_category_empty(self):
        """Test filtering by category with no matches."""
        registry = ToolRegistry()
        tool = create_dummy_tool("tool1", ToolCategory.FILESYSTEM)
        registry.register(tool)

        web_tools = registry.list_by_category(ToolCategory.WEB)
        assert len(web_tools) == 0

    def test_get_categories(self):
        """Test getting list of registered categories."""
        registry = ToolRegistry()
        registry.register(create_dummy_tool("fs1", ToolCategory.FILESYSTEM))
        registry.register(create_dummy_tool("git1", ToolCategory.GIT))
        registry.register(create_dummy_tool("git2", ToolCategory.GIT))

        categories = registry.get_categories()
        assert len(categories) == 2
        assert ToolCategory.FILESYSTEM in categories
        assert ToolCategory.GIT in categories
        assert ToolCategory.WEB not in categories

    def test_get_categories_sorted(self):
        """Test that categories are returned sorted by value."""
        registry = ToolRegistry()
        # Register in non-alphabetical order
        registry.register(create_dummy_tool("web1", ToolCategory.WEB))
        registry.register(create_dummy_tool("fs1", ToolCategory.FILESYSTEM))
        registry.register(create_dummy_tool("shell1", ToolCategory.SHELL))

        categories = registry.get_categories()
        # Should be sorted: filesystem, shell, web
        assert categories == [ToolCategory.FILESYSTEM, ToolCategory.SHELL, ToolCategory.WEB]

    def test_get_categories_empty_registry(self):
        """Test get_categories on empty registry."""
        registry = ToolRegistry()
        assert registry.get_categories() == []
