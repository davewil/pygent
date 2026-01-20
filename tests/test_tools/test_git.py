"""Tests for git tools.

This module contains comprehensive unit tests and property-based tests
for the git tools in chapgent.tools.git.
"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.tools.git import (
    GitError,
    _check_git_repo,
    _run_git_command,
    git_add,
    git_branch,
    git_checkout,
    git_commit,
    git_diff,
    git_log,
    git_pull,
    git_push,
    git_status,
)

# Fixtures


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    # Create initial file and commit
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True, check=True)
    return repo


@pytest.fixture
def non_git_dir(tmp_path: Path) -> Path:
    """Create a temporary directory that is NOT a git repository."""
    non_git = tmp_path / "not_a_repo"
    non_git.mkdir()
    return non_git


# Helper function tests


@pytest.mark.asyncio
async def test_run_git_command_success(git_repo: Path) -> None:
    """Test running a git command that succeeds."""
    stdout, stderr, return_code = await _run_git_command("status", cwd=str(git_repo))

    assert return_code == 0
    assert "branch" in stdout.lower() or "On branch" in stdout


@pytest.mark.asyncio
async def test_run_git_command_failure(non_git_dir: Path) -> None:
    """Test running a git command that fails."""
    stdout, stderr, return_code = await _run_git_command("status", cwd=str(non_git_dir))

    assert return_code != 0
    assert stderr or not stdout  # Error case


@pytest.mark.asyncio
async def test_check_git_repo_success(git_repo: Path) -> None:
    """Test check_git_repo in a valid git repo."""
    # Should not raise
    await _check_git_repo(cwd=str(git_repo))


@pytest.mark.asyncio
async def test_check_git_repo_failure(non_git_dir: Path) -> None:
    """Test check_git_repo outside a git repo."""
    with pytest.raises(GitError, match="Not a git repository"):
        await _check_git_repo(cwd=str(non_git_dir))


# git_status tests


@pytest.mark.asyncio
async def test_git_status_clean(git_repo: Path) -> None:
    """Test git_status on a clean repository."""
    result = await git_status(cwd=str(git_repo))

    assert "nothing to commit" in result.lower() or "working tree clean" in result.lower()


@pytest.mark.asyncio
async def test_git_status_with_changes(git_repo: Path) -> None:
    """Test git_status with modified files."""
    # Modify existing file
    (git_repo / "README.md").write_text("# Modified\n")

    result = await git_status(cwd=str(git_repo))

    assert "modified" in result.lower() or "Changes not staged" in result


@pytest.mark.asyncio
async def test_git_status_with_untracked(git_repo: Path) -> None:
    """Test git_status with untracked files."""
    (git_repo / "new_file.txt").write_text("New content\n")

    result = await git_status(cwd=str(git_repo))

    assert "untracked" in result.lower() or "new_file.txt" in result


@pytest.mark.asyncio
async def test_git_status_not_a_repo(non_git_dir: Path) -> None:
    """Test git_status outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_status(cwd=str(non_git_dir))


# git_diff tests


@pytest.mark.asyncio
async def test_git_diff_no_changes(git_repo: Path) -> None:
    """Test git_diff with no changes."""
    result = await git_diff(cwd=str(git_repo))

    assert result == "No differences found."


@pytest.mark.asyncio
async def test_git_diff_with_changes(git_repo: Path) -> None:
    """Test git_diff with unstaged changes."""
    (git_repo / "README.md").write_text("# Modified Content\n")

    result = await git_diff(cwd=str(git_repo))

    assert "Modified Content" in result or "diff" in result.lower()


@pytest.mark.asyncio
async def test_git_diff_staged(git_repo: Path) -> None:
    """Test git_diff with staged changes (--cached)."""
    (git_repo / "README.md").write_text("# Staged Content\n")
    subprocess.run(["git", "add", "README.md"], cwd=git_repo, capture_output=True, check=True)

    result = await git_diff(staged=True, cwd=str(git_repo))

    assert "Staged Content" in result or "diff" in result.lower()


@pytest.mark.asyncio
async def test_git_diff_specific_path(git_repo: Path) -> None:
    """Test git_diff limited to specific path."""
    (git_repo / "README.md").write_text("# Modified\n")
    (git_repo / "other.txt").write_text("Other\n")
    subprocess.run(["git", "add", "other.txt"], cwd=git_repo, capture_output=True, check=True)

    result = await git_diff(path="README.md", cwd=str(git_repo))

    # Should only show README.md changes
    assert "other.txt" not in result


@pytest.mark.asyncio
async def test_git_diff_with_commit(git_repo: Path) -> None:
    """Test git_diff against a specific commit."""
    (git_repo / "README.md").write_text("# New Content\n")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=git_repo, capture_output=True, check=True)

    result = await git_diff(commit="HEAD~1", cwd=str(git_repo))

    assert "New Content" in result or "diff" in result.lower()


@pytest.mark.asyncio
async def test_git_diff_not_a_repo(non_git_dir: Path) -> None:
    """Test git_diff outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_diff(cwd=str(non_git_dir))


# git_log tests


@pytest.mark.asyncio
async def test_git_log_basic(git_repo: Path) -> None:
    """Test basic git_log."""
    result = await git_log(cwd=str(git_repo))

    assert "Initial commit" in result


@pytest.mark.asyncio
async def test_git_log_count(git_repo: Path) -> None:
    """Test git_log with count parameter."""
    # Add more commits
    for i in range(5):
        (git_repo / f"file{i}.txt").write_text(f"Content {i}\n")
        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", f"Commit {i}"], cwd=git_repo, capture_output=True, check=True)

    result = await git_log(count=2, cwd=str(git_repo))
    lines = [line for line in result.split("\n") if line.strip()]

    assert len(lines) == 2


@pytest.mark.asyncio
async def test_git_log_not_oneline(git_repo: Path) -> None:
    """Test git_log with oneline=False."""
    result = await git_log(oneline=False, cwd=str(git_repo))

    assert "Author:" in result or "Date:" in result or "commit" in result.lower()


@pytest.mark.asyncio
async def test_git_log_path_filter(git_repo: Path) -> None:
    """Test git_log filtered by path."""
    (git_repo / "tracked.txt").write_text("Tracked\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Add tracked"], cwd=git_repo, capture_output=True, check=True)

    result = await git_log(path="tracked.txt", cwd=str(git_repo))

    assert "Add tracked" in result
    assert "Initial commit" not in result


@pytest.mark.asyncio
async def test_git_log_not_a_repo(non_git_dir: Path) -> None:
    """Test git_log outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_log(cwd=str(non_git_dir))


# git_branch tests


@pytest.mark.asyncio
async def test_git_branch_list(git_repo: Path) -> None:
    """Test listing branches."""
    result = await git_branch(cwd=str(git_repo))

    assert "master" in result or "main" in result


@pytest.mark.asyncio
async def test_git_branch_create(git_repo: Path) -> None:
    """Test creating a new branch."""
    await git_branch(name="feature-branch", cwd=str(git_repo))

    # Verify branch was created
    list_result = await git_branch(cwd=str(git_repo))
    assert "feature-branch" in list_result


@pytest.mark.asyncio
async def test_git_branch_delete(git_repo: Path) -> None:
    """Test deleting a branch."""
    # Create branch first
    await git_branch(name="to-delete", cwd=str(git_repo))

    # Delete it
    await git_branch(name="to-delete", delete=True, cwd=str(git_repo))

    # Verify branch is gone
    list_result = await git_branch(cwd=str(git_repo))
    assert "to-delete" not in list_result


@pytest.mark.asyncio
async def test_git_branch_list_all(git_repo: Path) -> None:
    """Test listing all branches including remotes."""
    result = await git_branch(list_all=True, cwd=str(git_repo))

    # Should work even without remotes
    assert "master" in result or "main" in result


@pytest.mark.asyncio
async def test_git_branch_not_a_repo(non_git_dir: Path) -> None:
    """Test git_branch outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_branch(cwd=str(non_git_dir))


# git_add tests


@pytest.mark.asyncio
async def test_git_add_single_file(git_repo: Path) -> None:
    """Test staging a single file."""
    (git_repo / "new.txt").write_text("New content\n")

    result = await git_add(paths=["new.txt"], cwd=str(git_repo))

    assert "Successfully staged" in result
    assert "new.txt" in result

    # Verify file is staged
    status = await git_status(cwd=str(git_repo))
    assert "new.txt" in status and "new file" in status.lower()


@pytest.mark.asyncio
async def test_git_add_multiple_files(git_repo: Path) -> None:
    """Test staging multiple files."""
    (git_repo / "file1.txt").write_text("Content 1\n")
    (git_repo / "file2.txt").write_text("Content 2\n")

    result = await git_add(paths=["file1.txt", "file2.txt"], cwd=str(git_repo))

    assert "Successfully staged" in result
    assert "file1.txt" in result
    assert "file2.txt" in result


@pytest.mark.asyncio
async def test_git_add_empty_paths(git_repo: Path) -> None:
    """Test git_add with empty paths list."""
    with pytest.raises(GitError, match="No paths provided"):
        await git_add(paths=[], cwd=str(git_repo))


@pytest.mark.asyncio
async def test_git_add_not_a_repo(non_git_dir: Path) -> None:
    """Test git_add outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_add(paths=["file.txt"], cwd=str(non_git_dir))


# git_commit tests


@pytest.mark.asyncio
async def test_git_commit_basic(git_repo: Path) -> None:
    """Test creating a basic commit."""
    (git_repo / "new.txt").write_text("New content\n")
    subprocess.run(["git", "add", "new.txt"], cwd=git_repo, capture_output=True, check=True)

    result = await git_commit(message="Add new file", cwd=str(git_repo))

    assert "Add new file" in result or "file changed" in result.lower() or "insertion" in result.lower()


@pytest.mark.asyncio
async def test_git_commit_empty_message(git_repo: Path) -> None:
    """Test git_commit with empty message."""
    with pytest.raises(GitError, match="Commit message cannot be empty"):
        await git_commit(message="", cwd=str(git_repo))


@pytest.mark.asyncio
async def test_git_commit_nothing_staged(git_repo: Path) -> None:
    """Test git_commit with nothing staged."""
    with pytest.raises(GitError, match="git commit failed"):
        await git_commit(message="Empty commit", cwd=str(git_repo))


@pytest.mark.asyncio
async def test_git_commit_not_a_repo(non_git_dir: Path) -> None:
    """Test git_commit outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_commit(message="Test", cwd=str(non_git_dir))


# git_checkout tests


@pytest.mark.asyncio
async def test_git_checkout_branch(git_repo: Path) -> None:
    """Test checking out an existing branch."""
    # Create a branch first
    subprocess.run(["git", "branch", "feature"], cwd=git_repo, capture_output=True, check=True)

    result = await git_checkout(branch="feature", cwd=str(git_repo))

    assert "feature" in result.lower() or "switched" in result.lower()


@pytest.mark.asyncio
async def test_git_checkout_create_branch(git_repo: Path) -> None:
    """Test creating and checking out a new branch."""
    result = await git_checkout(branch="new-feature", create=True, cwd=str(git_repo))

    assert "new-feature" in result.lower() or "switched" in result.lower()

    # Verify we're on the new branch
    branch_result = await git_branch(cwd=str(git_repo))
    assert "new-feature" in branch_result


@pytest.mark.asyncio
async def test_git_checkout_restore_file(git_repo: Path) -> None:
    """Test restoring a file from HEAD."""
    # Modify a file
    (git_repo / "README.md").write_text("Modified content\n")

    # Verify file is modified
    diff_before = await git_diff(cwd=str(git_repo))
    assert "Modified content" in diff_before

    # Restore it
    await git_checkout(paths=["README.md"], cwd=str(git_repo))

    # Verify file is restored
    diff_after = await git_diff(cwd=str(git_repo))
    assert diff_after == "No differences found."


@pytest.mark.asyncio
async def test_git_checkout_no_args(git_repo: Path) -> None:
    """Test git_checkout with no branch or paths."""
    with pytest.raises(GitError, match="Must specify either branch or paths"):
        await git_checkout(cwd=str(git_repo))


@pytest.mark.asyncio
async def test_git_checkout_not_a_repo(non_git_dir: Path) -> None:
    """Test git_checkout outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_checkout(branch="main", cwd=str(non_git_dir))


# git_push tests (mocked since we don't have a real remote)


@pytest.mark.asyncio
async def test_git_push_mocked() -> None:
    """Test git_push with mocked subprocess."""
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"Everything up-to-date\n", b""))
    mock_process.returncode = 0

    with patch("chapgent.tools.git._run_git_command") as mock_run:
        # First call checks if it's a git repo
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("Everything up-to-date", "", 0),  # git push
        ]

        result = await git_push()

        assert "Everything up-to-date" in result or "Successfully pushed" in result


@pytest.mark.asyncio
async def test_git_push_with_options() -> None:
    """Test git_push with set_upstream and branch options."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("Branch 'feature' set up to track", "", 0),  # git push
        ]

        await git_push(remote="origin", branch="feature", set_upstream=True)

        # Verify the command was called with correct args
        calls = mock_run.call_args_list
        assert calls[1][0] == ("push", "-u", "origin", "feature")


@pytest.mark.asyncio
async def test_git_push_failure() -> None:
    """Test git_push when push fails."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("", "fatal: No configured push destination.", 128),  # git push
        ]

        with pytest.raises(GitError, match="git push failed"):
            await git_push()


@pytest.mark.asyncio
async def test_git_push_not_a_repo(non_git_dir: Path) -> None:
    """Test git_push outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_push(cwd=str(non_git_dir))


# git_pull tests (mocked since we don't have a real remote)


@pytest.mark.asyncio
async def test_git_pull_mocked() -> None:
    """Test git_pull with mocked subprocess."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("Already up to date.", "", 0),  # git pull
        ]

        result = await git_pull()

        assert "Already up to date" in result


@pytest.mark.asyncio
async def test_git_pull_with_branch() -> None:
    """Test git_pull with specific branch."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("Updating abc123..def456", "", 0),  # git pull
        ]

        await git_pull(remote="upstream", branch="main")

        # Verify the command was called with correct args
        calls = mock_run.call_args_list
        assert calls[1][0] == ("pull", "upstream", "main")


@pytest.mark.asyncio
async def test_git_pull_failure() -> None:
    """Test git_pull when pull fails."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("", "fatal: couldn't find remote ref", 128),  # git pull
        ]

        with pytest.raises(GitError, match="git pull failed"):
            await git_pull()


@pytest.mark.asyncio
async def test_git_pull_not_a_repo(non_git_dir: Path) -> None:
    """Test git_pull outside a git repository."""
    with pytest.raises(GitError, match="Not a git repository"):
        await git_pull(cwd=str(non_git_dir))


# Property-based tests


@given(st.text(min_size=1, max_size=50).filter(lambda x: x.strip() and "\n" not in x and "\x00" not in x))
@settings(max_examples=20)
@pytest.mark.asyncio
async def test_git_commit_message_handling(message: str) -> None:
    """Property: Any valid commit message should be passed correctly to git."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            (f"[main abc123] {message}", "", 0),  # git commit
        ]

        await git_commit(message=message)

        # Verify message was passed to git commit
        calls = mock_run.call_args_list
        assert calls[1][0] == ("commit", "-m", message)


@given(st.integers(min_value=1, max_value=100))
@settings(max_examples=20)
@pytest.mark.asyncio
async def test_git_log_count_parameter(count: int) -> None:
    """Property: git_log count should be correctly passed to git."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("abc123 Commit message\n" * min(count, 5), "", 0),  # git log
        ]

        await git_log(count=count)

        # Verify count was passed to git log
        calls = mock_run.call_args_list
        assert f"-{count}" in calls[1][0]


@given(st.text(min_size=1, max_size=30).filter(lambda x: x.isalnum() or x.replace("-", "").replace("_", "").isalnum()))
@settings(max_examples=20)
@pytest.mark.asyncio
async def test_git_branch_name_handling(branch_name: str) -> None:
    """Property: Branch names should be correctly passed to git commands."""
    if not branch_name.strip():
        return

    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("", "", 0),  # git branch
        ]

        await git_branch(name=branch_name)

        # Verify branch name was passed correctly
        calls = mock_run.call_args_list
        assert branch_name in calls[1][0]


@given(st.lists(st.from_regex(r"[a-z][a-z0-9_]{0,19}", fullmatch=True), min_size=1, max_size=5))
@settings(max_examples=20)
@pytest.mark.asyncio
async def test_git_add_paths_handling(paths: list[str]) -> None:
    """Property: File paths should be correctly passed to git add."""
    with patch("chapgent.tools.git._run_git_command") as mock_run:
        mock_run.side_effect = [
            (".", "", 0),  # _check_git_repo
            ("", "", 0),  # git add
        ]

        await git_add(paths=paths)

        # Verify all paths were included in the command
        calls = mock_run.call_args_list
        add_args = calls[1][0]
        assert add_args[0] == "add"
        for path in paths:
            assert path in add_args


# Integration test with real git repo


@pytest.mark.asyncio
async def test_full_workflow(git_repo: Path) -> None:
    """Integration test: full git workflow."""
    # 1. Check status (clean)
    status = await git_status(cwd=str(git_repo))
    assert "nothing to commit" in status.lower() or "working tree clean" in status.lower()

    # 2. Create a new file
    (git_repo / "feature.py").write_text("def hello():\n    print('hello')\n")

    # 3. Check status (untracked)
    status = await git_status(cwd=str(git_repo))
    assert "feature.py" in status

    # 4. Add the file
    await git_add(paths=["feature.py"], cwd=str(git_repo))

    # 5. Check diff (staged)
    diff = await git_diff(staged=True, cwd=str(git_repo))
    assert "hello" in diff

    # 6. Commit
    commit_result = await git_commit(message="Add feature", cwd=str(git_repo))
    assert "Add feature" in commit_result or "file changed" in commit_result.lower()

    # 7. Check log
    log = await git_log(count=1, cwd=str(git_repo))
    assert "Add feature" in log

    # 8. Create and switch to branch
    await git_checkout(branch="feature-branch", create=True, cwd=str(git_repo))

    # 9. Verify on new branch
    branches = await git_branch(cwd=str(git_repo))
    assert "feature-branch" in branches
