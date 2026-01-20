"""Tests for the parallel tool execution system."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.core.parallel import (
    PATH_ARGUMENTS,
    ExecutionBatch,
    ToolExecution,
    ToolResult,
    execute_batch,
    execute_single_tool,
    execute_tools_parallel,
    extract_affected_paths,
    get_parallel_stats,
    group_into_batches,
    is_read_only_tool,
    paths_conflict,
    prepare_tool_execution,
)
from chapgent.tools.base import ToolCategory, ToolDefinition, ToolRisk

# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class MockToolUseBlock:
    """Mock for ToolUseBlock from providers.

    This is a duck-typed mock that satisfies the ToolUseBlock interface
    for testing purposes.
    """

    id: str
    name: str
    input: dict[str, Any]


def make_tool_use(name: str, **kwargs: Any) -> Any:
    """Create a mock tool use block."""
    return MockToolUseBlock(id=f"{name}_id", name=name, input=kwargs)


def make_tool_def(
    name: str,
    risk: ToolRisk = ToolRisk.LOW,
    category: ToolCategory = ToolCategory.FILESYSTEM,
    return_value: str = "success",
    read_only: bool = False,
    cacheable: bool | None = None,
) -> ToolDefinition:
    """Create a mock tool definition."""
    # Default cacheable based on read_only if not explicitly set
    effective_cacheable = cacheable if cacheable is not None else read_only

    async def mock_func(**kwargs: Any) -> str:
        return return_value

    return ToolDefinition(
        name=name,
        description=f"Mock {name} tool",
        input_schema={"type": "object", "properties": {}},
        risk=risk,
        category=category,
        function=mock_func,
        read_only=read_only,
        cacheable=effective_cacheable,
    )


def make_mock_agent(
    allowed: bool = True,
    cached_result: str | None = None,
) -> MagicMock:
    """Create a mock agent with permissions and cache."""
    agent = MagicMock()

    # Mock permissions
    async def check_permission(**kwargs: Any) -> bool:
        return allowed

    agent.permissions = MagicMock()
    agent.permissions.check = check_permission

    # Mock cache (with cacheable parameter)
    async def cache_get(tool_name: str, args: dict[str, Any], cacheable: bool = True) -> str | None:
        if not cacheable:
            return None
        return cached_result

    async def cache_set(tool_name: str, args: dict[str, Any], result: str, cacheable: bool = True) -> None:
        pass

    agent.tool_cache = MagicMock()
    agent.tool_cache.get = cache_get
    agent.tool_cache.set = cache_set

    return agent


# =============================================================================
# Test Constants
# =============================================================================


class TestPathArguments:
    """Tests for PATH_ARGUMENTS constant."""

    def test_contains_common_path_args(self) -> None:
        """Should include common path argument names."""
        assert "path" in PATH_ARGUMENTS
        assert "file_path" in PATH_ARGUMENTS
        assert "source" in PATH_ARGUMENTS
        assert "destination" in PATH_ARGUMENTS
        assert "directory" in PATH_ARGUMENTS


# =============================================================================
# Test Helper Functions
# =============================================================================


class TestIsReadOnlyTool:
    """Tests for is_read_only_tool function."""

    def test_read_only_tool_is_read_only(self) -> None:
        """Tool with read_only=True should be identified as read-only."""
        tool_def = make_tool_def("read_file", read_only=True)
        assert is_read_only_tool(tool_def) is True

    def test_write_tool_is_not_read_only(self) -> None:
        """Tool with read_only=False should not be identified as read-only."""
        tool_def = make_tool_def("edit_file", read_only=False)
        assert is_read_only_tool(tool_def) is False

    def test_default_is_not_read_only(self) -> None:
        """Tool with default read_only should not be read-only."""
        tool_def = make_tool_def("unknown_tool")
        assert is_read_only_tool(tool_def) is False


class TestExtractAffectedPaths:
    """Tests for extract_affected_paths function."""

    def test_extracts_path_argument(self) -> None:
        """Should extract 'path' argument."""
        paths = extract_affected_paths("read_file", {"path": "/tmp/test.txt"})
        assert paths == {"/tmp/test.txt"}

    def test_extracts_file_path_argument(self) -> None:
        """Should extract 'file_path' argument."""
        paths = extract_affected_paths("edit_file", {"file_path": "/tmp/test.txt"})
        assert paths == {"/tmp/test.txt"}

    def test_extracts_multiple_path_arguments(self) -> None:
        """Should extract multiple path arguments."""
        paths = extract_affected_paths("move_file", {"source": "/tmp/a.txt", "destination": "/tmp/b.txt"})
        assert paths == {"/tmp/a.txt", "/tmp/b.txt"}

    def test_ignores_empty_paths(self) -> None:
        """Should ignore empty path values."""
        paths = extract_affected_paths("read_file", {"path": ""})
        assert paths == set()

    def test_ignores_non_path_arguments(self) -> None:
        """Should ignore non-path arguments."""
        paths = extract_affected_paths("grep_search", {"pattern": "test", "path": "/tmp"})
        assert paths == {"/tmp"}

    def test_handles_no_path_arguments(self) -> None:
        """Should return empty set when no path arguments."""
        paths = extract_affected_paths("shell", {"command": "ls"})
        assert paths == set()


class TestPathsConflict:
    """Tests for paths_conflict function."""

    def test_empty_paths_no_conflict(self) -> None:
        """Empty path sets should not conflict."""
        assert paths_conflict(set(), set()) is False
        assert paths_conflict({"/tmp/a.txt"}, set()) is False
        assert paths_conflict(set(), {"/tmp/a.txt"}) is False

    def test_same_paths_conflict(self) -> None:
        """Identical paths should conflict."""
        assert paths_conflict({"/tmp/a.txt"}, {"/tmp/a.txt"}) is True

    def test_overlapping_paths_conflict(self) -> None:
        """Overlapping paths should conflict."""
        assert paths_conflict({"/tmp/a.txt", "/tmp/b.txt"}, {"/tmp/b.txt"}) is True

    def test_parent_child_paths_conflict(self) -> None:
        """Parent-child relationships should conflict."""
        assert paths_conflict({"/tmp"}, {"/tmp/a.txt"}) is True
        assert paths_conflict({"/tmp/a.txt"}, {"/tmp"}) is True

    def test_disjoint_paths_no_conflict(self) -> None:
        """Completely disjoint paths should not conflict."""
        assert paths_conflict({"/tmp/a.txt"}, {"/var/b.txt"}) is False

    def test_sibling_paths_no_conflict(self) -> None:
        """Sibling paths should not conflict."""
        assert paths_conflict({"/tmp/a"}, {"/tmp/b"}) is False

    def test_handles_trailing_slashes(self) -> None:
        """Should handle trailing slashes correctly."""
        assert paths_conflict({"/tmp/"}, {"/tmp/a.txt"}) is True
        assert paths_conflict({"/tmp/a/"}, {"/tmp/a/b.txt"}) is True


# =============================================================================
# Test Data Classes
# =============================================================================


class TestToolExecution:
    """Tests for ToolExecution dataclass."""

    def test_creation(self) -> None:
        """Should create ToolExecution with all fields."""
        tool_use = make_tool_use("read_file", path="/tmp/test.txt")
        tool_def = make_tool_def("read_file")

        exec_item = ToolExecution(
            tool_use=tool_use,
            tool_def=tool_def,
            is_read_only=True,
            affected_paths={"/tmp/test.txt"},
        )

        assert exec_item.tool_use.name == "read_file"
        assert exec_item.is_read_only is True
        assert "/tmp/test.txt" in exec_item.affected_paths


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_creation_success(self) -> None:
        """Should create successful ToolResult."""
        result = ToolResult(
            tool_use_id="test_id",
            tool_name="read_file",
            result="file contents",
            is_error=False,
        )

        assert result.tool_use_id == "test_id"
        assert result.is_error is False
        assert result.was_cached is False

    def test_creation_error(self) -> None:
        """Should create error ToolResult."""
        result = ToolResult(
            tool_use_id="test_id",
            tool_name="read_file",
            result="Error: File not found",
            is_error=True,
        )

        assert result.is_error is True

    def test_cached_flag(self) -> None:
        """Should track cached results."""
        result = ToolResult(
            tool_use_id="test_id",
            tool_name="read_file",
            result="cached content",
            is_error=False,
            was_cached=True,
        )

        assert result.was_cached is True


class TestExecutionBatch:
    """Tests for ExecutionBatch dataclass."""

    def test_parallel_batch(self) -> None:
        """Should create parallelizable batch."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/a.txt"},
        )
        exec2 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/b.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/b.txt"},
        )

        batch = ExecutionBatch(executions=[exec1, exec2], can_parallelize=True)

        assert len(batch.executions) == 2
        assert batch.can_parallelize is True

    def test_sequential_batch(self) -> None:
        """Should create sequential batch."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("edit_file", file_path="/tmp/a.txt"),
            tool_def=make_tool_def("edit_file"),
            is_read_only=False,
            affected_paths={"/tmp/a.txt"},
        )

        batch = ExecutionBatch(executions=[exec1], can_parallelize=False)

        assert batch.can_parallelize is False


# =============================================================================
# Test Prepare Tool Execution
# =============================================================================


class TestPrepareToolExecution:
    """Tests for prepare_tool_execution function."""

    def test_prepares_read_only_tool(self) -> None:
        """Should identify read-only tools."""
        tool_use = make_tool_use("read_file", path="/tmp/test.txt")
        tool_def = make_tool_def("read_file", read_only=True)

        exec_item = prepare_tool_execution(tool_use, tool_def)

        assert exec_item.is_read_only is True
        assert exec_item.affected_paths == {"/tmp/test.txt"}

    def test_prepares_write_tool(self) -> None:
        """Should identify write tools."""
        tool_use = make_tool_use("edit_file", file_path="/tmp/test.txt")
        tool_def = make_tool_def("edit_file", read_only=False)

        exec_item = prepare_tool_execution(tool_use, tool_def)

        assert exec_item.is_read_only is False


# =============================================================================
# Test Group Into Batches
# =============================================================================


class TestGroupIntoBatches:
    """Tests for group_into_batches function."""

    def test_empty_list(self) -> None:
        """Should handle empty list."""
        batches = group_into_batches([])
        assert batches == []

    def test_single_read_only(self) -> None:
        """Single read-only should create one non-parallel batch."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/a.txt"},
        )

        batches = group_into_batches([exec1])

        assert len(batches) == 1
        assert len(batches[0].executions) == 1
        assert batches[0].can_parallelize is False  # Single item

    def test_multiple_read_only_parallel(self) -> None:
        """Multiple non-conflicting read-only should be parallelized."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/a.txt"},
        )
        exec2 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/b.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/b.txt"},
        )

        batches = group_into_batches([exec1, exec2])

        assert len(batches) == 1
        assert len(batches[0].executions) == 2
        assert batches[0].can_parallelize is True

    def test_conflicting_read_only_sequential(self) -> None:
        """Conflicting read-only should be in separate batches."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/dir/a.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/dir"},
        )
        exec2 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/dir/b.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/dir/b.txt"},
        )

        batches = group_into_batches([exec1, exec2])

        # First batch has exec1, second has exec2 (conflict detected)
        assert len(batches) == 2

    def test_write_tool_creates_separate_batch(self) -> None:
        """Write tool should create its own sequential batch."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/a.txt"},
        )
        exec2 = ToolExecution(
            tool_use=make_tool_use("edit_file", file_path="/tmp/b.txt"),
            tool_def=make_tool_def("edit_file"),
            is_read_only=False,
            affected_paths={"/tmp/b.txt"},
        )
        exec3 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/c.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/c.txt"},
        )

        batches = group_into_batches([exec1, exec2, exec3])

        # Batch 1: exec1 (read), Batch 2: exec2 (write), Batch 3: exec3 (read)
        assert len(batches) == 3
        assert batches[0].executions[0].tool_use.name == "read_file"
        assert batches[0].can_parallelize is False  # Single item
        assert batches[1].executions[0].tool_use.name == "edit_file"
        assert batches[1].can_parallelize is False
        assert batches[2].executions[0].tool_use.name == "read_file"

    def test_multiple_reads_then_write(self) -> None:
        """Multiple reads followed by write should batch correctly."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
            tool_def=make_tool_def("read_file"),
            is_read_only=True,
            affected_paths={"/tmp/a.txt"},
        )
        exec2 = ToolExecution(
            tool_use=make_tool_use("grep_search", path="/tmp/b.txt"),
            tool_def=make_tool_def("grep_search"),
            is_read_only=True,
            affected_paths={"/tmp/b.txt"},
        )
        exec3 = ToolExecution(
            tool_use=make_tool_use("edit_file", file_path="/tmp/c.txt"),
            tool_def=make_tool_def("edit_file"),
            is_read_only=False,
            affected_paths={"/tmp/c.txt"},
        )

        batches = group_into_batches([exec1, exec2, exec3])

        # Batch 1: exec1 + exec2 (parallel reads), Batch 2: exec3 (write)
        assert len(batches) == 2
        assert len(batches[0].executions) == 2
        assert batches[0].can_parallelize is True
        assert batches[1].can_parallelize is False


# =============================================================================
# Test Execute Single Tool
# =============================================================================


class TestExecuteSingleTool:
    """Tests for execute_single_tool function."""

    @pytest.mark.asyncio
    async def test_successful_execution(self) -> None:
        """Should execute tool and return result."""
        tool_use = make_tool_use("read_file", path="/tmp/test.txt")
        tool_def = make_tool_def("read_file", return_value="file contents")
        exec_item = ToolExecution(
            tool_use=tool_use,
            tool_def=tool_def,
            is_read_only=True,
            affected_paths={"/tmp/test.txt"},
        )
        agent = make_mock_agent(allowed=True)

        result = await execute_single_tool(exec_item, agent)

        assert result.result == "file contents"
        assert result.is_error is False
        assert result.was_cached is False

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        """Should return error when permission denied."""
        tool_use = make_tool_use("edit_file", file_path="/tmp/test.txt")
        tool_def = make_tool_def("edit_file")
        exec_item = ToolExecution(
            tool_use=tool_use,
            tool_def=tool_def,
            is_read_only=False,
            affected_paths={"/tmp/test.txt"},
        )
        agent = make_mock_agent(allowed=False)

        result = await execute_single_tool(exec_item, agent)

        assert "Permission denied" in result.result
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_cached_result(self) -> None:
        """Should return cached result when available."""
        tool_use = make_tool_use("read_file", path="/tmp/test.txt")
        tool_def = make_tool_def("read_file", read_only=True, cacheable=True)
        exec_item = ToolExecution(
            tool_use=tool_use,
            tool_def=tool_def,
            is_read_only=True,
            affected_paths={"/tmp/test.txt"},
        )
        agent = make_mock_agent(allowed=True, cached_result="cached content")

        result = await execute_single_tool(exec_item, agent)

        assert result.result == "cached content"
        assert result.was_cached is True

    @pytest.mark.asyncio
    async def test_execution_error(self) -> None:
        """Should handle execution errors."""
        tool_use = make_tool_use("read_file", path="/tmp/test.txt")

        async def failing_func(**kwargs: Any) -> str:
            raise FileNotFoundError("File not found")

        tool_def = ToolDefinition(
            name="read_file",
            description="Read a file",
            input_schema={"type": "object", "properties": {}},
            risk=ToolRisk.LOW,
            category=ToolCategory.FILESYSTEM,
            function=failing_func,
        )
        exec_item = ToolExecution(
            tool_use=tool_use,
            tool_def=tool_def,
            is_read_only=True,
            affected_paths={"/tmp/test.txt"},
        )
        agent = make_mock_agent(allowed=True)

        result = await execute_single_tool(exec_item, agent)

        assert "Error" in result.result
        assert "File not found" in result.result
        assert result.is_error is True


# =============================================================================
# Test Execute Batch
# =============================================================================


class TestExecuteBatch:
    """Tests for execute_batch function."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        """Should execute parallel batch concurrently."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
            tool_def=make_tool_def("read_file", return_value="a"),
            is_read_only=True,
            affected_paths={"/tmp/a.txt"},
        )
        exec2 = ToolExecution(
            tool_use=make_tool_use("read_file", path="/tmp/b.txt"),
            tool_def=make_tool_def("read_file", return_value="b"),
            is_read_only=True,
            affected_paths={"/tmp/b.txt"},
        )
        batch = ExecutionBatch(executions=[exec1, exec2], can_parallelize=True)
        agent = make_mock_agent(allowed=True)

        results = await execute_batch(batch, agent)

        assert len(results) == 2
        # Results should be in order
        assert results[0].result == "a"
        assert results[1].result == "b"

    @pytest.mark.asyncio
    async def test_sequential_execution(self) -> None:
        """Should execute sequential batch in order."""
        exec1 = ToolExecution(
            tool_use=make_tool_use("edit_file", file_path="/tmp/a.txt"),
            tool_def=make_tool_def("edit_file", return_value="edited"),
            is_read_only=False,
            affected_paths={"/tmp/a.txt"},
        )
        batch = ExecutionBatch(executions=[exec1], can_parallelize=False)
        agent = make_mock_agent(allowed=True)

        results = await execute_batch(batch, agent)

        assert len(results) == 1
        assert results[0].result == "edited"


# =============================================================================
# Test Execute Tools Parallel
# =============================================================================


class TestExecuteToolsParallel:
    """Tests for execute_tools_parallel function."""

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        """Should handle empty tool calls."""
        agent = make_mock_agent()

        results = await execute_tools_parallel([], agent)

        assert results == []

    @pytest.mark.asyncio
    async def test_single_tool(self) -> None:
        """Should execute single tool."""
        tool_use = make_tool_use("read_file", path="/tmp/test.txt")
        tool_def = make_tool_def("read_file", return_value="content")
        agent = make_mock_agent(allowed=True)

        results = await execute_tools_parallel([(tool_use, tool_def)], agent)

        assert len(results) == 1
        assert results[0].result == "content"

    @pytest.mark.asyncio
    async def test_parallel_reads(self) -> None:
        """Should execute parallel reads concurrently."""
        tool_use1 = make_tool_use("read_file", path="/tmp/a.txt")
        tool_def1 = make_tool_def("read_file", return_value="a")
        tool_use2 = make_tool_use("read_file", path="/tmp/b.txt")
        tool_def2 = make_tool_def("read_file", return_value="b")
        agent = make_mock_agent(allowed=True)

        results = await execute_tools_parallel([(tool_use1, tool_def1), (tool_use2, tool_def2)], agent)

        assert len(results) == 2
        assert results[0].result == "a"
        assert results[1].result == "b"

    @pytest.mark.asyncio
    async def test_mixed_read_write(self) -> None:
        """Should handle mixed read/write operations."""
        tool_use1 = make_tool_use("read_file", path="/tmp/a.txt")
        tool_def1 = make_tool_def("read_file", return_value="a")
        tool_use2 = make_tool_use("edit_file", file_path="/tmp/b.txt")
        tool_def2 = make_tool_def("edit_file", return_value="edited")
        tool_use3 = make_tool_use("read_file", path="/tmp/c.txt")
        tool_def3 = make_tool_def("read_file", return_value="c")
        agent = make_mock_agent(allowed=True)

        results = await execute_tools_parallel(
            [(tool_use1, tool_def1), (tool_use2, tool_def2), (tool_use3, tool_def3)],
            agent,
        )

        assert len(results) == 3
        assert results[0].result == "a"
        assert results[1].result == "edited"
        assert results[2].result == "c"

    @pytest.mark.asyncio
    async def test_preserves_order(self) -> None:
        """Should preserve order of results."""
        tools = []
        for i in range(5):
            tool_use = make_tool_use("read_file", path=f"/tmp/file{i}.txt")
            tool_def = make_tool_def("read_file", return_value=f"content_{i}")
            tools.append((tool_use, tool_def))

        agent = make_mock_agent(allowed=True)
        results = await execute_tools_parallel(tools, agent)

        for i, result in enumerate(results):
            assert result.result == f"content_{i}"


# =============================================================================
# Test Get Parallel Stats
# =============================================================================


class TestGetParallelStats:
    """Tests for get_parallel_stats function."""

    def test_empty_executions(self) -> None:
        """Should return zero stats for empty list."""
        stats = get_parallel_stats([])

        assert stats["total"] == 0
        assert stats["read_only"] == 0
        assert stats["write"] == 0
        assert stats["batches"] == 0
        assert stats["max_parallel"] == 0

    def test_all_read_only(self) -> None:
        """Should report stats for all read-only tools."""
        executions = [
            ToolExecution(
                tool_use=make_tool_use("read_file", path=f"/tmp/file{i}.txt"),
                tool_def=make_tool_def("read_file"),
                is_read_only=True,
                affected_paths={f"/tmp/file{i}.txt"},
            )
            for i in range(3)
        ]

        stats = get_parallel_stats(executions)

        assert stats["total"] == 3
        assert stats["read_only"] == 3
        assert stats["write"] == 0
        assert stats["batches"] == 1
        assert stats["max_parallel"] == 3

    def test_mixed_tools(self) -> None:
        """Should report stats for mixed tools."""
        executions = [
            ToolExecution(
                tool_use=make_tool_use("read_file", path="/tmp/a.txt"),
                tool_def=make_tool_def("read_file"),
                is_read_only=True,
                affected_paths={"/tmp/a.txt"},
            ),
            ToolExecution(
                tool_use=make_tool_use("edit_file", file_path="/tmp/b.txt"),
                tool_def=make_tool_def("edit_file"),
                is_read_only=False,
                affected_paths={"/tmp/b.txt"},
            ),
            ToolExecution(
                tool_use=make_tool_use("read_file", path="/tmp/c.txt"),
                tool_def=make_tool_def("read_file"),
                is_read_only=True,
                affected_paths={"/tmp/c.txt"},
            ),
        ]

        stats = get_parallel_stats(executions)

        assert stats["total"] == 3
        assert stats["read_only"] == 2
        assert stats["write"] == 1
        assert stats["batches"] == 3  # read, write, read


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(
        paths1=st.lists(st.text(min_size=1, max_size=50), max_size=5),
        paths2=st.lists(st.text(min_size=1, max_size=50), max_size=5),
    )
    @settings(max_examples=100)
    def test_paths_conflict_symmetric(self, paths1: list[str], paths2: list[str]) -> None:
        """Path conflict should be symmetric."""
        set1 = set(paths1)
        set2 = set(paths2)

        assert paths_conflict(set1, set2) == paths_conflict(set2, set1)

    @given(paths=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5))
    @settings(max_examples=50)
    def test_paths_conflict_with_self(self, paths: list[str]) -> None:
        """Non-empty path set should conflict with itself."""
        path_set = set(paths)
        if path_set:  # Non-empty
            assert paths_conflict(path_set, path_set) is True

    @given(read_only=st.booleans())
    @settings(max_examples=10)
    def test_read_only_flag_respected(self, read_only: bool) -> None:
        """Tool read_only flag should be respected by is_read_only_tool."""
        tool_def = make_tool_def("test_tool", read_only=read_only)
        assert is_read_only_tool(tool_def) is read_only

    @given(
        args=st.fixed_dictionaries(
            {"path": st.text(min_size=1, max_size=50)},
            optional={"other": st.text(max_size=20)},
        )
    )
    @settings(max_examples=50)
    def test_extract_paths_includes_path_arg(self, args: dict[str, str]) -> None:
        """Should always extract 'path' argument when present."""
        paths = extract_affected_paths("some_tool", args)
        if args.get("path"):
            assert args["path"] in paths


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for parallel execution."""

    @pytest.mark.asyncio
    async def test_full_workflow_parallel_reads(self) -> None:
        """Test full workflow with parallel reads."""
        # Create multiple read tools
        tools = []
        for i in range(3):
            tool_use = make_tool_use("read_file", path=f"/tmp/file{i}.txt")
            tool_def = make_tool_def("read_file", return_value=f"content_{i}", read_only=True)
            tools.append((tool_use, tool_def))

        agent = make_mock_agent(allowed=True)
        results = await execute_tools_parallel(tools, agent)

        # All should succeed
        assert all(not r.is_error for r in results)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_full_workflow_with_permission_denied(self) -> None:
        """Test workflow where some tools are denied."""
        tool_use1 = make_tool_use("read_file", path="/tmp/a.txt")
        tool_def1 = make_tool_def("read_file", return_value="a")
        tool_use2 = make_tool_use("edit_file", file_path="/tmp/b.txt")
        tool_def2 = make_tool_def("edit_file")

        agent = make_mock_agent(allowed=False)
        results = await execute_tools_parallel([(tool_use1, tool_def1), (tool_use2, tool_def2)], agent)

        # All should be permission denied
        assert all(r.is_error for r in results)
        assert all("Permission denied" in r.result for r in results)

    @pytest.mark.asyncio
    async def test_parallel_execution_timing(self) -> None:
        """Test that parallel execution is actually parallel."""
        import time

        sleep_time = 0.05  # 50ms

        async def slow_func(**kwargs: Any) -> str:
            await asyncio.sleep(sleep_time)
            return "done"

        tools = []
        for i in range(3):
            tool_use = make_tool_use("read_file", path=f"/tmp/file{i}.txt")
            tool_def = ToolDefinition(
                name="read_file",
                description="Read a file",
                input_schema={"type": "object", "properties": {}},
                risk=ToolRisk.LOW,
                category=ToolCategory.FILESYSTEM,
                function=slow_func,
                read_only=True,
                cacheable=True,
            )
            tools.append((tool_use, tool_def))

        agent = make_mock_agent(allowed=True)

        start = time.time()
        results = await execute_tools_parallel(tools, agent)
        elapsed = time.time() - start

        # If parallel, should take ~sleep_time, not 3x sleep_time
        # Allow some overhead
        assert elapsed < sleep_time * 2
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_sequential_write_execution(self) -> None:
        """Test that write operations execute sequentially."""
        execution_order: list[int] = []

        def make_tracking_func(idx: int) -> Any:
            """Factory to create tracking function with captured index."""

            async def func(**kwargs: Any) -> str:
                execution_order.append(idx)
                return f"result_{idx}"

            return func

        tools = []
        for i in range(3):
            tool_use = make_tool_use("edit_file", file_path=f"/tmp/file{i}.txt")

            tool_def = ToolDefinition(
                name="edit_file",
                description="Edit a file",
                input_schema={"type": "object", "properties": {}},
                risk=ToolRisk.MEDIUM,
                category=ToolCategory.FILESYSTEM,
                function=make_tracking_func(i),
            )
            tools.append((tool_use, tool_def))

        agent = make_mock_agent(allowed=True)
        results = await execute_tools_parallel(tools, agent)

        # Write operations should execute in order
        assert execution_order == [0, 1, 2]
        assert len(results) == 3
