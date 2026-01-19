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

from pygent.tools.base import ToolCategory, ToolRisk, tool


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
    category=ToolCategory.SEARCH,
    read_only=True,
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


def _should_include_path(path: Path, base_path: Path) -> bool:
    """Check if a path should be included (not hidden or in common ignore dirs).

    Args:
        path: The path to check.
        base_path: The base directory (to get relative parts).

    Returns:
        True if the path should be included.
    """
    try:
        rel_path = path.relative_to(base_path)
        parts = rel_path.parts
    except ValueError:
        parts = path.parts

    return not any(
        part.startswith(".") or part in ("node_modules", "__pycache__", ".git", "venv", ".venv") for part in parts
    )


def _get_depth(path: Path, base_path: Path) -> int:
    """Calculate the depth of a path relative to base.

    Args:
        path: The path to measure.
        base_path: The base directory.

    Returns:
        Number of directory levels from base to path.
    """
    try:
        rel_path = path.relative_to(base_path)
        return len(rel_path.parts)
    except ValueError:
        return 0


@tool(
    name="find_files",
    description="Find files and directories matching a glob pattern. Returns a list of matching paths.",
    risk=ToolRisk.LOW,
    category=ToolCategory.SEARCH,
    read_only=True,
)
async def find_files(
    pattern: str,
    path: str = ".",
    max_depth: int | None = None,
    file_type: str | None = None,
) -> str:
    """Find files by name pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "test_*.py").
        path: Base directory to search (default: current directory).
        max_depth: Maximum directory depth to search.
        file_type: Filter by type ("file" or "directory").

    Returns:
        JSON array of matching paths relative to the search path.
    """
    search_path = Path(path)
    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    if not search_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    matches: list[str] = []

    for item in search_path.glob(pattern):
        # Skip hidden files and common ignore directories
        if not _should_include_path(item, search_path):
            continue

        # Check max_depth
        if max_depth is not None:
            depth = _get_depth(item, search_path)
            if depth > max_depth:
                continue

        # Check file_type filter
        if file_type == "file" and not item.is_file():
            continue
        if file_type == "directory" and not item.is_dir():
            continue

        # Store relative path for cleaner output
        try:
            rel_path = item.relative_to(search_path)
            matches.append(str(rel_path))
        except ValueError:
            matches.append(str(item))

    # Sort for consistent output
    matches.sort()

    if not matches:
        return json.dumps({"message": "No files found", "files": []})

    return json.dumps({"count": len(matches), "files": matches}, indent=2)


# Language-specific definition patterns
# These patterns capture common definition styles for each language
_DEFINITION_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [
        (r"^\s*def\s+{symbol}\s*\(", "function"),
        (r"^\s*async\s+def\s+{symbol}\s*\(", "async function"),
        (r"^\s*class\s+{symbol}\s*[\(:]", "class"),
        (r"^{symbol}\s*=\s*", "variable"),
        (r"^\s*{symbol}\s*:\s*\S+\s*=", "typed variable"),
    ],
    "javascript": [
        (r"^\s*function\s+{symbol}\s*\(", "function"),
        (r"^\s*async\s+function\s+{symbol}\s*\(", "async function"),
        (r"^\s*class\s+{symbol}\s*[\{{]", "class"),
        (r"^\s*class\s+{symbol}\s+extends\s+", "class"),
        (r"^\s*const\s+{symbol}\s*=", "const"),
        (r"^\s*let\s+{symbol}\s*=", "let"),
        (r"^\s*var\s+{symbol}\s*=", "var"),
        (r"^\s*export\s+(?:default\s+)?function\s+{symbol}\s*\(", "exported function"),
        (r"^\s*export\s+(?:default\s+)?class\s+{symbol}\s*", "exported class"),
        (r"^\s*export\s+const\s+{symbol}\s*=", "exported const"),
    ],
    "typescript": [
        (r"^\s*function\s+{symbol}\s*[<\(]", "function"),
        (r"^\s*async\s+function\s+{symbol}\s*[<\(]", "async function"),
        (r"^\s*class\s+{symbol}\s*[\{{<]", "class"),
        (r"^\s*class\s+{symbol}\s+extends\s+", "class"),
        (r"^\s*interface\s+{symbol}\s*[\{{<]", "interface"),
        (r"^\s*type\s+{symbol}\s*[<=]", "type"),
        (r"^\s*const\s+{symbol}\s*[=:]", "const"),
        (r"^\s*let\s+{symbol}\s*[=:]", "let"),
        (r"^\s*export\s+(?:default\s+)?function\s+{symbol}\s*", "exported function"),
        (r"^\s*export\s+(?:default\s+)?class\s+{symbol}\s*", "exported class"),
        (r"^\s*export\s+(?:default\s+)?interface\s+{symbol}\s*", "exported interface"),
        (r"^\s*export\s+(?:default\s+)?type\s+{symbol}\s*", "exported type"),
        (r"^\s*export\s+const\s+{symbol}\s*", "exported const"),
    ],
    "go": [
        (r"^\s*func\s+{symbol}\s*\(", "function"),
        (r"^\s*func\s+\([^)]+\)\s+{symbol}\s*\(", "method"),
        (r"^\s*type\s+{symbol}\s+struct\s*\{{", "struct"),
        (r"^\s*type\s+{symbol}\s+interface\s*\{{", "interface"),
        (r"^\s*type\s+{symbol}\s+", "type"),
        (r"^\s*var\s+{symbol}\s+", "var"),
        (r"^\s*const\s+{symbol}\s+", "const"),
    ],
    "rust": [
        (r"^\s*fn\s+{symbol}\s*[<\(]", "function"),
        (r"^\s*async\s+fn\s+{symbol}\s*[<\(]", "async function"),
        (r"^\s*pub\s+fn\s+{symbol}\s*[<\(]", "public function"),
        (r"^\s*pub\s+async\s+fn\s+{symbol}\s*[<\(]", "public async function"),
        (r"^\s*struct\s+{symbol}\s*[\{{<]", "struct"),
        (r"^\s*pub\s+struct\s+{symbol}\s*[\{{<]", "public struct"),
        (r"^\s*enum\s+{symbol}\s*[\{{<]", "enum"),
        (r"^\s*pub\s+enum\s+{symbol}\s*[\{{<]", "public enum"),
        (r"^\s*trait\s+{symbol}\s*[\{{<:]", "trait"),
        (r"^\s*pub\s+trait\s+{symbol}\s*[\{{<:]", "public trait"),
        (r"^\s*type\s+{symbol}\s*[<=]", "type alias"),
        (r"^\s*const\s+{symbol}\s*:", "const"),
        (r"^\s*static\s+{symbol}\s*:", "static"),
        (r"^\s*let\s+(?:mut\s+)?{symbol}\s*[=:]", "let binding"),
    ],
    "java": [
        (r"^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+{symbol}\s*\(", "method"),
        (r"^\s*(?:public|private|protected)?\s*class\s+{symbol}\s*", "class"),
        (r"^\s*(?:public|private|protected)?\s*interface\s+{symbol}\s*", "interface"),
        (r"^\s*(?:public|private|protected)?\s*enum\s+{symbol}\s*", "enum"),
    ],
    "c": [
        (r"^\s*\w+[\s\*]+{symbol}\s*\([^;]*$", "function"),
        (r"^\s*#define\s+{symbol}\s*", "macro"),
        (r"^\s*typedef\s+.*\s+{symbol}\s*;", "typedef"),
        (r"^\s*struct\s+{symbol}\s*\{{", "struct"),
        (r"^\s*enum\s+{symbol}\s*\{{", "enum"),
    ],
    "cpp": [
        (r"^\s*\w+[\s\*]+{symbol}\s*\([^;]*$", "function"),
        (r"^\s*class\s+{symbol}\s*[\{{:]", "class"),
        (r"^\s*struct\s+{symbol}\s*[\{{:]", "struct"),
        (r"^\s*namespace\s+{symbol}\s*\{{", "namespace"),
        (r"^\s*template\s*<[^>]*>\s*class\s+{symbol}", "template class"),
        (r"^\s*#define\s+{symbol}\s*", "macro"),
    ],
}

# File extension to language mapping
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
}


def _get_language_from_path(file_path: Path) -> str | None:
    """Detect language from file extension.

    Args:
        file_path: Path to the file.

    Returns:
        Language name or None if unknown.
    """
    suffix = file_path.suffix.lower()
    return _EXTENSION_TO_LANGUAGE.get(suffix)


def _compile_patterns_for_symbol(symbol: str, language: str) -> list[tuple[re.Pattern[str], str]]:
    """Compile regex patterns for a symbol in a given language.

    Args:
        symbol: The symbol name to search for.
        language: The programming language.

    Returns:
        List of (compiled_pattern, definition_type) tuples.
    """
    patterns = _DEFINITION_PATTERNS.get(language, [])
    compiled = []
    escaped_symbol = re.escape(symbol)
    for pattern_template, def_type in patterns:
        pattern_str = pattern_template.format(symbol=escaped_symbol)
        try:
            compiled.append((re.compile(pattern_str, re.MULTILINE), def_type))
        except re.error:
            continue
    return compiled


@tool(
    name="find_definition",
    description="Find where a symbol (function, class, variable) is defined in the codebase",
    risk=ToolRisk.LOW,
    category=ToolCategory.SEARCH,
    read_only=True,
)
async def find_definition(
    symbol: str,
    path: str = ".",
    language: str | None = None,
) -> str:
    """Find symbol definition.

    Args:
        symbol: Name of function, class, or variable to find.
        path: Directory to search in (default: current directory).
        language: Programming language hint (e.g., "python", "javascript").
            If not provided, language is detected from file extensions.

    Returns:
        JSON array of definition locations with file, line, type, and context.
    """
    search_path = Path(path)
    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    results: list[dict[str, str | int]] = []

    # Collect files to search
    if search_path.is_file():
        files = [search_path]
    else:
        files = [f for f in search_path.rglob("*") if f.is_file()]

    # Filter out hidden and common ignore patterns
    files = [f for f in files if _should_include_path(f, search_path)]

    for file_path in files:
        # Determine language for this file
        file_lang = language or _get_language_from_path(file_path)
        if not file_lang:
            continue

        # Get patterns for this language
        patterns = _compile_patterns_for_symbol(symbol, file_lang)
        if not patterns:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            for line_num, line in enumerate(lines, start=1):
                for pattern, def_type in patterns:
                    if pattern.match(line):
                        results.append(
                            {
                                "file": str(file_path),
                                "line": line_num,
                                "type": def_type,
                                "context": line.strip(),
                            }
                        )
                        break  # Only report first matching pattern per line

        except (OSError, UnicodeDecodeError):
            continue

    if not results:
        return json.dumps({"message": f"No definitions found for '{symbol}'", "definitions": []})

    return json.dumps({"count": len(results), "definitions": results}, indent=2)
