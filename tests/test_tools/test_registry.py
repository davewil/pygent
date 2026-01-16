from hypothesis import given
from hypothesis import strategies as st

from pygent.tools.base import ToolDefinition, ToolRisk
from pygent.tools.registry import ToolRegistry


def create_dummy_tool(name: str) -> ToolDefinition:
    async def dummy_func():
        pass

    return ToolDefinition(
        name=name,
        description="A dummy tool",
        input_schema={"type": "object"},
        risk=ToolRisk.LOW,
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
