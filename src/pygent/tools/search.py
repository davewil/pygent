"""Search tools for finding files and code patterns.

This module provides tools for searching file contents using regex patterns
and finding files matching glob patterns.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

from pygent.tools.base import ToolRisk, tool


def _is_ripgrep_available() -> bool:
    """Check if ripgrep (rg) is available on the system."""
    return shutil.which("rg") is not None


async def _grep_with_ripgrep(
    pattern: str,
    path: str,
    file_pattern: str | None,
    ignore_case: bool,
    context_lines: int,
    max_results: int,
) -> list[dict[str, str | int]]:
    """Execute grep search using ripgrep."""
    cmd = ["rg", "--json", "--max-count", str(max_results)]

    if ignore_case:
        cmd.append("--ignore-case")

    if context_lines > 0:
        cmd.extend(["--context", str(context_lines)])

    if file_pattern:
        cmd.extend(["--glob", file_pattern])

    cmd.extend([pattern, path])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError:
        # ripgrep not found
        return []

    results: list[dict[str, str | int]] = []
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            if data.get("type") == "match":
                match_data = data.get("data", {})
                submatches = match_data.get("submatches", [])
                match_text = submatches[0].get("match", {}).get("text", "") if submatches else ""
                results.append(
                    {
                        "file": match_data.get("path", {}).get("text", ""),
                        "line": match_data.get("line_number", 0),
                        "content": match_data.get("lines", {}).get("text", "").rstrip("\n"),
                        "match": match_text,
                    }
                )
                if len(results) >= max_results:
                    break
        except json.JSONDecodeError:
            continue

    return results


async def _grep_with_python(
    pattern: str,
    path: str,
    file_pattern: str | None,
    ignore_case: bool,
    context_lines: int,
    max_results: int,
) -> list[dict[str, str | int]]:
    """Execute grep search using pure Python."""
    search_path = Path(path)
    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}") from e

    results: list[dict[str, str | int]] = []

    # Collect files to search
    if search_path.is_file():
        files = [search_path]
    else:
        if file_pattern:
            files = list(search_path.rglob(file_pattern))
        else:
            files = [f for f in search_path.rglob("*") if f.is_file()]

    # Filter out hidden and common ignore patterns
    def should_include(f: Path) -> bool:
        parts = f.parts
        return not any(
            part.startswith(".") or part in ("node_modules", "__pycache__", ".git", "venv", ".venv") for part in parts
        )

    files = [f for f in files if should_include(f)]

    for file_path in files:
        if len(results) >= max_results:
            break

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            for line_num, line in enumerate(lines, start=1):
                if len(results) >= max_results:
                    break

                match = regex.search(line)
                if match:
                    results.append(
                        {
                            "file": str(file_path),
                            "line": line_num,
                            "content": line,
                            "match": match.group(0),
                        }
                    )

        except (OSError, UnicodeDecodeError):
            # Skip files that can't be read
            continue

    return results


@tool(
    name="grep_search",
    description="Search for patterns in files using regex. Returns matching lines with file path and line number.",
    risk=ToolRisk.LOW,
)
async def grep_search(
    pattern: str,
    path: str = ".",
    file_pattern: str | None = None,
    ignore_case: bool = False,
    context_lines: int = 0,
    max_results: int = 100,
) -> str:
    """Search file contents with regex.

    Args:
        pattern: Regex pattern to search for.
        path: Directory to search in (default: current directory).
        file_pattern: Glob pattern to filter files (e.g., "*.py").
        ignore_case: Case-insensitive search.
        context_lines: Lines of context around matches.
        max_results: Maximum number of matches to return.

    Returns:
        JSON array of matches with file, line, content, and match fields.
    """
    if _is_ripgrep_available():
        results = await _grep_with_ripgrep(pattern, path, file_pattern, ignore_case, context_lines, max_results)
    else:
        results = await _grep_with_python(pattern, path, file_pattern, ignore_case, context_lines, max_results)

    if not results:
        return json.dumps({"message": "No matches found", "results": []})

    return json.dumps({"count": len(results), "results": results}, indent=2)
