"""Git tools for repository operations.

This module provides tools for interacting with git repositories,
including status, diff, log, branch management, and remote operations.
"""

from __future__ import annotations

import asyncio

from pygent.tools.base import ToolCategory, ToolRisk, tool


class GitError(Exception):
    """Exception raised when a git command fails."""

    pass


async def _run_git_command(
    *args: str,
    cwd: str | None = None,
) -> tuple[str, str, int]:
    """Run a git command asynchronously.

    Args:
        *args: Git command arguments (without 'git' prefix).
        cwd: Working directory for the command.

    Returns:
        Tuple of (stdout, stderr, return_code).
    """
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    return_code = process.returncode if process.returncode is not None else 1

    return stdout, stderr, return_code


async def _check_git_repo(cwd: str | None = None) -> None:
    """Check if the current directory is a git repository.

    Args:
        cwd: Working directory to check.

    Raises:
        GitError: If not inside a git repository.
    """
    _, stderr, return_code = await _run_git_command("rev-parse", "--git-dir", cwd=cwd)
    if return_code != 0:
        raise GitError("Not a git repository (or any parent up to mount point)")


@tool(
    name="git_status",
    description="Show the working tree status (modified, staged, untracked files)",
    risk=ToolRisk.LOW,
    category=ToolCategory.GIT,
    read_only=True,
)
async def git_status(cwd: str | None = None) -> str:
    """Get git repository status.

    Args:
        cwd: Working directory (default: current directory).

    Returns:
        Formatted status output showing staged changes, unstaged changes,
        untracked files, and current branch.

    Raises:
        GitError: If not in a git repository.
    """
    await _check_git_repo(cwd)

    stdout, stderr, return_code = await _run_git_command("status", cwd=cwd)

    if return_code != 0:
        raise GitError(f"git status failed: {stderr}")

    return stdout.strip()


@tool(
    name="git_diff",
    description="Show changes between commits, commit and working tree, etc.",
    risk=ToolRisk.LOW,
    category=ToolCategory.GIT,
    read_only=True,
)
async def git_diff(
    path: str | None = None,
    staged: bool = False,
    commit: str | None = None,
    cwd: str | None = None,
) -> str:
    """Show git diff.

    Args:
        path: Limit diff to specific file/directory.
        staged: If True, show staged changes (--cached).
        commit: Compare against specific commit.
        cwd: Working directory (default: current directory).

    Returns:
        Unified diff output.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    args: list[str] = ["diff"]

    if staged:
        args.append("--cached")

    if commit:
        args.append(commit)

    if path:
        args.append("--")
        args.append(path)

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git diff failed: {stderr}")

    return stdout.strip() if stdout.strip() else "No differences found."


@tool(
    name="git_log",
    description="Show commit history",
    risk=ToolRisk.LOW,
    category=ToolCategory.GIT,
    read_only=True,
)
async def git_log(
    count: int = 10,
    oneline: bool = True,
    path: str | None = None,
    cwd: str | None = None,
) -> str:
    """Show git commit history.

    Args:
        count: Number of commits to show (default: 10).
        oneline: If True, show compact format (default: True).
        path: Limit to commits affecting path.
        cwd: Working directory (default: current directory).

    Returns:
        Formatted commit history.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    args: list[str] = ["log", f"-{count}"]

    if oneline:
        args.append("--oneline")

    if path:
        args.append("--")
        args.append(path)

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git log failed: {stderr}")

    return stdout.strip() if stdout.strip() else "No commits found."


@tool(
    name="git_branch",
    description="List, create, or delete branches",
    risk=ToolRisk.LOW,
    category=ToolCategory.GIT,
    read_only=True,
)
async def git_branch(
    name: str | None = None,
    delete: bool = False,
    list_all: bool = False,
    cwd: str | None = None,
) -> str:
    """Manage branches.

    Args:
        name: Branch name (for create/delete).
        delete: If True, delete the branch.
        list_all: If True, list remote branches too.
        cwd: Working directory (default: current directory).

    Returns:
        Branch list or operation result.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    args: list[str] = ["branch"]

    if delete and name:
        args.append("-d")
        args.append(name)
    elif name:
        # Create new branch
        args.append(name)
    elif list_all:
        args.append("-a")

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git branch failed: {stderr}")

    return stdout.strip() if stdout.strip() else "No branches found."


# Write tools


@tool(
    name="git_add",
    description="Stage files for commit",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.GIT,
    cacheable=False,
)
async def git_add(
    paths: list[str],
    cwd: str | None = None,
) -> str:
    """Stage files for commit.

    Args:
        paths: List of file paths to stage.
        cwd: Working directory (default: current directory).

    Returns:
        Confirmation message.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    if not paths:
        raise GitError("No paths provided to stage")

    args: list[str] = ["add"] + paths

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git add failed: {stderr}")

    return f"Successfully staged: {', '.join(paths)}"


@tool(
    name="git_commit",
    description="Create a new commit with staged changes",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.GIT,
    cacheable=False,
)
async def git_commit(
    message: str,
    cwd: str | None = None,
) -> str:
    """Create a commit.

    Args:
        message: Commit message.
        cwd: Working directory (default: current directory).

    Returns:
        Commit hash and summary.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    if not message:
        raise GitError("Commit message cannot be empty")

    stdout, stderr, return_code = await _run_git_command("commit", "-m", message, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git commit failed: {stderr}")

    return stdout.strip()


@tool(
    name="git_checkout",
    description="Switch branches or restore files",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.GIT,
    cacheable=False,
)
async def git_checkout(
    branch: str | None = None,
    create: bool = False,
    paths: list[str] | None = None,
    cwd: str | None = None,
) -> str:
    """Checkout branch or restore files.

    Args:
        branch: Branch name to checkout.
        create: If True, create new branch (-b).
        paths: Restore specific files from HEAD.
        cwd: Working directory (default: current directory).

    Returns:
        Status message.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    args: list[str] = ["checkout"]

    if branch:
        if create:
            args.append("-b")
        args.append(branch)
    elif paths:
        args.append("--")
        args.extend(paths)
    else:
        raise GitError("Must specify either branch or paths to checkout")

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git checkout failed: {stderr}")

    # checkout often outputs to stderr for success messages
    output = stdout.strip() or stderr.strip()
    return output if output else f"Switched to branch '{branch}'" if branch else "Files restored."


# Remote tools


@tool(
    name="git_push",
    description="Push commits to remote repository",
    risk=ToolRisk.HIGH,
    category=ToolCategory.GIT,
    cacheable=False,
)
async def git_push(
    remote: str = "origin",
    branch: str | None = None,
    set_upstream: bool = False,
    cwd: str | None = None,
) -> str:
    """Push to remote.

    Args:
        remote: Remote name (default: origin).
        branch: Branch to push (default: current).
        set_upstream: If True, set upstream (-u).
        cwd: Working directory (default: current directory).

    Returns:
        Push result output.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    args: list[str] = ["push"]

    if set_upstream:
        args.append("-u")

    args.append(remote)

    if branch:
        args.append(branch)

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git push failed: {stderr}")

    # Push often outputs to stderr
    output = stdout.strip() or stderr.strip()
    return output if output else f"Successfully pushed to {remote}"


@tool(
    name="git_pull",
    description="Fetch and integrate changes from remote",
    risk=ToolRisk.MEDIUM,
    category=ToolCategory.GIT,
    cacheable=False,
)
async def git_pull(
    remote: str = "origin",
    branch: str | None = None,
    cwd: str | None = None,
) -> str:
    """Pull from remote.

    Args:
        remote: Remote name (default: origin).
        branch: Branch to pull.
        cwd: Working directory (default: current directory).

    Returns:
        Pull result output.

    Raises:
        GitError: If not in a git repository or command fails.
    """
    await _check_git_repo(cwd)

    args: list[str] = ["pull", remote]

    if branch:
        args.append(branch)

    stdout, stderr, return_code = await _run_git_command(*args, cwd=cwd)

    if return_code != 0:
        raise GitError(f"git pull failed: {stderr}")

    return stdout.strip() if stdout.strip() else "Already up to date."
