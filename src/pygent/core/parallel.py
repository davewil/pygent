"""Parallel tool execution system for improved performance.

This module provides functionality for executing multiple tool calls in parallel
where safe, while ensuring sequential execution for write operations and
operations that affect the same resources.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pygent.core.agent import Agent
    from pygent.core.providers import ToolUseBlock
    from pygent.tools.base import ToolDefinition

# Note: read_only status is now determined by tool definition metadata (ToolDefinition.read_only)
# This is more maintainable than a hardcoded set, as new tools automatically get correct behavior.

# Arguments that typically contain file paths for conflict detection
PATH_ARGUMENTS: frozenset[str] = frozenset(
    {
        "path",
        "file_path",
        "source",
        "destination",
        "src",
        "dest",
        "directory",
        "dir",
    }
)


@dataclass
class ToolExecution:
    """Represents a tool call ready for execution.

    Attributes:
        tool_use: The tool use block from the LLM.
        tool_def: The tool definition from the registry.
        is_read_only: Whether this tool is read-only.
        affected_paths: Set of file paths this tool may affect.
    """

    tool_use: ToolUseBlock
    tool_def: ToolDefinition
    is_read_only: bool
    affected_paths: set[str]


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        tool_use_id: The ID of the tool use block.
        tool_name: Name of the executed tool.
        result: The result string from execution.
        is_error: Whether the execution resulted in an error.
        was_cached: Whether the result came from cache.
    """

    tool_use_id: str
    tool_name: str
    result: str
    is_error: bool
    was_cached: bool = False


@dataclass
class ExecutionBatch:
    """A batch of tool executions that can run together.

    Attributes:
        executions: List of tool executions in this batch.
        can_parallelize: Whether executions can run in parallel.
    """

    executions: list[ToolExecution]
    can_parallelize: bool


def is_read_only_tool(tool_def: ToolDefinition) -> bool:
    """Check if a tool is read-only and safe for parallel execution.

    Args:
        tool_def: The tool definition to check.

    Returns:
        True if the tool is read-only, False otherwise.
    """
    return tool_def.read_only


def extract_affected_paths(tool_name: str, args: dict[str, Any]) -> set[str]:
    """Extract file paths that a tool call may affect.

    Args:
        tool_name: Name of the tool.
        args: Arguments passed to the tool.

    Returns:
        Set of file paths that may be affected.
    """
    paths: set[str] = set()

    for arg_name in PATH_ARGUMENTS:
        if arg_name in args:
            value = args[arg_name]
            if isinstance(value, str) and value:
                paths.add(value)

    return paths


def paths_conflict(paths1: set[str], paths2: set[str]) -> bool:
    """Check if two sets of paths conflict (overlap or have parent-child relationship).

    Args:
        paths1: First set of paths.
        paths2: Second set of paths.

    Returns:
        True if paths conflict, False otherwise.
    """
    if not paths1 or not paths2:
        return False

    # Direct overlap
    if paths1 & paths2:
        return True

    # Check for parent-child relationships
    for p1 in paths1:
        for p2 in paths2:
            # Normalize paths by stripping trailing slashes
            p1_norm = p1.rstrip("/")
            p2_norm = p2.rstrip("/")

            # Check if one is a prefix of the other (parent-child relationship)
            if p1_norm.startswith(p2_norm + "/") or p2_norm.startswith(p1_norm + "/"):
                return True

    return False


def prepare_tool_execution(
    tool_use: ToolUseBlock,
    tool_def: ToolDefinition,
) -> ToolExecution:
    """Prepare a tool use block for execution with metadata.

    Args:
        tool_use: The tool use block from the LLM.
        tool_def: The tool definition from the registry.

    Returns:
        ToolExecution with computed metadata.
    """
    return ToolExecution(
        tool_use=tool_use,
        tool_def=tool_def,
        is_read_only=is_read_only_tool(tool_def),
        affected_paths=extract_affected_paths(tool_use.name, tool_use.input),
    )


def group_into_batches(executions: list[ToolExecution]) -> list[ExecutionBatch]:
    """Group tool executions into batches for execution.

    Safety rules:
    - Read-only operations can run in parallel with each other
    - Write operations run sequentially
    - Operations affecting the same paths run sequentially

    Args:
        executions: List of tool executions to group.

    Returns:
        List of execution batches.
    """
    if not executions:
        return []

    batches: list[ExecutionBatch] = []
    current_read_batch: list[ToolExecution] = []
    current_read_paths: set[str] = set()

    for exec_item in executions:
        if exec_item.is_read_only:
            # Check if this read conflicts with current read batch
            if paths_conflict(exec_item.affected_paths, current_read_paths):
                # Flush current batch and start new one
                if current_read_batch:
                    batches.append(
                        ExecutionBatch(
                            executions=current_read_batch,
                            can_parallelize=len(current_read_batch) > 1,
                        )
                    )
                current_read_batch = [exec_item]
                current_read_paths = exec_item.affected_paths.copy()
            else:
                # Add to current parallel batch
                current_read_batch.append(exec_item)
                current_read_paths.update(exec_item.affected_paths)
        else:
            # Write operation - flush current read batch first
            if current_read_batch:
                batches.append(
                    ExecutionBatch(
                        executions=current_read_batch,
                        can_parallelize=len(current_read_batch) > 1,
                    )
                )
                current_read_batch = []
                current_read_paths = set()

            # Add write as single-item sequential batch
            batches.append(
                ExecutionBatch(
                    executions=[exec_item],
                    can_parallelize=False,
                )
            )

    # Flush remaining read batch
    if current_read_batch:
        batches.append(
            ExecutionBatch(
                executions=current_read_batch,
                can_parallelize=len(current_read_batch) > 1,
            )
        )

    return batches


async def execute_single_tool(
    execution: ToolExecution,
    agent: Agent,
) -> ToolResult:
    """Execute a single tool with permission checking and caching.

    Args:
        execution: The tool execution to run.
        agent: The agent providing permissions and caching.

    Returns:
        ToolResult with the execution outcome.
    """
    tool_use = execution.tool_use
    tool_def = execution.tool_def

    # Check permissions
    allowed = await agent.permissions.check(
        tool_name=tool_use.name,
        risk=tool_def.risk,
        args=tool_use.input,
    )

    if not allowed:
        return ToolResult(
            tool_use_id=tool_use.id,
            tool_name=tool_use.name,
            result="Error: Permission denied by user.",
            is_error=True,
        )

    # Check cache first (only for cacheable tools)
    cached_result = await agent.tool_cache.get(tool_use.name, tool_use.input, cacheable=tool_def.cacheable)
    if cached_result is not None:
        return ToolResult(
            tool_use_id=tool_use.id,
            tool_name=tool_use.name,
            result=cached_result,
            is_error=False,
            was_cached=True,
        )

    # Execute the tool
    try:
        output = await tool_def.function(**tool_use.input)
        result = str(output)

        # Cache the result (only for cacheable tools)
        await agent.tool_cache.set(tool_use.name, tool_use.input, result, cacheable=tool_def.cacheable)

        return ToolResult(
            tool_use_id=tool_use.id,
            tool_name=tool_use.name,
            result=result,
            is_error=False,
        )

    except Exception as e:
        return ToolResult(
            tool_use_id=tool_use.id,
            tool_name=tool_use.name,
            result=f"Error execution tool: {e!s}",
            is_error=True,
        )


async def execute_batch(
    batch: ExecutionBatch,
    agent: Agent,
) -> list[ToolResult]:
    """Execute a batch of tools, potentially in parallel.

    Args:
        batch: The execution batch.
        agent: The agent providing permissions and caching.

    Returns:
        List of tool results in the same order as the batch executions.
    """
    if batch.can_parallelize and len(batch.executions) > 1:
        # Execute in parallel
        tasks = [execute_single_tool(exec_item, agent) for exec_item in batch.executions]
        return list(await asyncio.gather(*tasks))
    else:
        # Execute sequentially
        results: list[ToolResult] = []
        for exec_item in batch.executions:
            result = await execute_single_tool(exec_item, agent)
            results.append(result)
        return results


async def execute_tools_parallel(
    tool_calls: list[tuple[ToolUseBlock, ToolDefinition]],
    agent: Agent,
) -> list[ToolResult]:
    """Execute multiple tool calls with parallel execution where safe.

    Safety rules:
    - Read operations can run in parallel
    - Write operations run sequentially
    - Same-file operations run sequentially

    Args:
        tool_calls: List of (tool_use, tool_def) tuples to execute.
        agent: The agent providing permissions, tools, and caching.

    Returns:
        List of tool results in the same order as input tool_calls.
    """
    if not tool_calls:
        return []

    # Prepare executions
    executions = [prepare_tool_execution(tu, td) for tu, td in tool_calls]

    # Group into batches
    batches = group_into_batches(executions)

    # Execute batches sequentially, items within parallelizable batches in parallel
    results: list[ToolResult] = []
    for batch in batches:
        batch_results = await execute_batch(batch, agent)
        results.extend(batch_results)

    return results


def get_parallel_stats(executions: list[ToolExecution]) -> dict[str, Any]:
    """Get statistics about parallelization potential.

    Args:
        executions: List of tool executions.

    Returns:
        Dictionary with parallelization statistics.
    """
    if not executions:
        return {
            "total": 0,
            "read_only": 0,
            "write": 0,
            "batches": 0,
            "max_parallel": 0,
        }

    batches = group_into_batches(executions)
    max_parallel = max((len(b.executions) for b in batches if b.can_parallelize), default=1)

    return {
        "total": len(executions),
        "read_only": sum(1 for e in executions if e.is_read_only),
        "write": sum(1 for e in executions if not e.is_read_only),
        "batches": len(batches),
        "max_parallel": max_parallel,
    }
