from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import aiofiles

from pygent.tools.base import ToolCategory, ToolRisk, tool


@tool(
    name="read_file",
    description="Read the contents of a file at the given path",
    risk=ToolRisk.LOW,
    category=ToolCategory.FILESYSTEM,
    read_only=True,
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

    async with aiofiles.open(file_path, encoding="utf-8") as f:
        return await f.read()


@tool(
    name="list_files",
    description="List files and directories at the given path",
    risk=ToolRisk.LOW,
    category=ToolCategory.FILESYSTEM,
    read_only=True,
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


def _path_to_entry(path: Path, root: Path) -> dict[str, Any]:
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
    category=ToolCategory.FILESYSTEM,
    cacheable=False,
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

    async with aiofiles.open(file_path, encoding="utf-8") as f:
        content = await f.read()

    if old_str not in content:
        raise ValueError(f"String not found in file: {old_str}")

    new_content = content.replace(old_str, new_str)

    async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
        await f.write(new_content)

    return f"Successfully replaced occurrences in {path}"


@tool(
    name="create_file",
    description="Create a new file with content",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.FILESYSTEM,
    cacheable=False,
)
async def create_file(path: str, content: str) -> str:
    """Create a new file.

    Args:
        path: Path for the new file.
        content: Initial file content.

    Returns:
        Success message.

    Raises:
        FileExistsError: If file already exists.
    """
    file_path = Path(path)

    if file_path.exists():
        raise FileExistsError(f"File already exists: {path}")

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
        await f.write(content)

    return f"Successfully created file: {path}"


@tool(
    name="delete_file",
    description="Delete a file",
    risk=ToolRisk.HIGH,
    category=ToolCategory.FILESYSTEM,
    cacheable=False,
)
async def delete_file(path: str) -> str:
    """Delete a file.

    Args:
        path: Path to file to delete.

    Returns:
        Confirmation message.

    Raises:
        FileNotFoundError: If file doesn't exist.
        IsADirectoryError: If path is a directory.

    Note:
        Directories are not deleted (use shell for rmdir).
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if file_path.is_dir():
        raise IsADirectoryError(f"Cannot delete directory with delete_file: {path}")

    await asyncio.to_thread(file_path.unlink)

    return f"Successfully deleted file: {path}"


@tool(
    name="move_file",
    description="Move or rename a file",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.FILESYSTEM,
    cacheable=False,
)
async def move_file(source: str, destination: str) -> str:
    """Move or rename a file.

    Args:
        source: Current file path.
        destination: New file path.

    Returns:
        Confirmation message.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        IsADirectoryError: If source is a directory.
        FileExistsError: If destination already exists.
    """
    src_path = Path(source)
    dst_path = Path(destination)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    if src_path.is_dir():
        raise IsADirectoryError(f"Cannot move directory with move_file: {source}")

    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    # Ensure parent directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(shutil.move, str(src_path), str(dst_path))

    return f"Successfully moved {source} to {destination}"


@tool(
    name="copy_file",
    description="Copy a file to a new location",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.FILESYSTEM,
    cacheable=False,
)
async def copy_file(source: str, destination: str) -> str:
    """Copy a file.

    Args:
        source: Source file path.
        destination: Destination file path.

    Returns:
        Confirmation message.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        IsADirectoryError: If source is a directory.
        FileExistsError: If destination already exists.
    """
    src_path = Path(source)
    dst_path = Path(destination)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    if src_path.is_dir():
        raise IsADirectoryError(f"Cannot copy directory with copy_file: {source}")

    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    # Ensure parent directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(shutil.copy2, str(src_path), str(dst_path))

    return f"Successfully copied {source} to {destination}"
