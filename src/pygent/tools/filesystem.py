from __future__ import annotations

import json
from pathlib import Path

import aiofiles

from pygent.tools.base import ToolRisk, tool


@tool(
    name="read_file",
    description="Read the contents of a file at the given path",
    risk=ToolRisk.LOW,
)
async def read_file(path: str) -> str:
    """Read file contents.

    Args:
        path: Path to the file (absolute or relative to cwd).

    Returns:
        File contents as string.

    Raises:
        FileNotFoundError: If file doesn't exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Check if it's a file
    if not file_path.is_file():
        raise IsADirectoryError(f"Path is a directory: {path}")

    async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
        return await f.read()


@tool(
    name="list_files",
    description="List files and directories at the given path",
    risk=ToolRisk.LOW,
)
async def list_files(path: str = ".", recursive: bool = False) -> str:
    """List directory contents.

    Args:
        path: Directory path (default: current directory).
        recursive: If True, list recursively.

    Returns:
        JSON array of file/directory entries.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    entries = []

    if recursive:
        # Recursive listing
        for p in root.rglob("*"):
            entries.append(_path_to_entry(p, root))
    else:
        # Flat listing
        for p in root.iterdir():
            entries.append(_path_to_entry(p, root))

    return json.dumps(entries, indent=2)


def _path_to_entry(path: Path, root: Path) -> dict:
    """Convert a path to a dictionary entry."""
    stats = path.stat()
    return {
        "name": path.name,
        "path": str(path.relative_to(root)) if path != root else ".",
        "is_dir": path.is_dir(),
        "size": stats.st_size,
        "modified": stats.st_mtime,
    }


@tool(
    name="edit_file",
    description="Edit a file by replacing old_str with new_str",
    risk=ToolRisk.MEDIUM,
)
async def edit_file(path: str, old_str: str, new_str: str) -> str:
    """Edit file via string replacement.

    Args:
        path: Path to file.
        old_str: Exact string to find and replace.
        new_str: Replacement string.

    Returns:
        Success message or error description.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
        content = await f.read()

    if old_str not in content:
        raise ValueError(f"String not found in file: {old_str}")

    new_content = content.replace(old_str, new_str)

    async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
        await f.write(new_content)

    return f"Successfully replaced occurrences in {path}"
