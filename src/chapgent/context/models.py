"""Data models for project context awareness."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class TestFramework(str, Enum):
    """Supported test frameworks."""

    __test__ = False  # Prevent pytest from collecting this as a test class

    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    MOCHA = "mocha"
    VITEST = "vitest"
    GO_TEST = "go test"
    CARGO_TEST = "cargo test"
    UNKNOWN = "unknown"


class ProjectType(str, Enum):
    """Supported project types."""

    PYTHON = "python"
    NODE = "node"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class GitInfo(BaseModel):
    """Git repository information.

    Attributes:
        branch: Current branch name.
        remote: Remote repository URL.
        has_changes: Whether there are uncommitted changes.
        commit_count: Number of commits in the repo.
        last_commit: Hash of the most recent commit.
    """

    branch: str | None = None
    remote: str | None = None
    has_changes: bool = False
    commit_count: int = 0
    last_commit: str | None = None


class ProjectContext(BaseModel):
    """Detected project information.

    Attributes:
        type: Project type (python, node, go, rust, etc.)
        root: Project root directory (stored as string for JSON serialization).
        name: Project name.
        version: Project version.
        dependencies: List of dependencies.
        scripts: Available scripts/commands.
        test_framework: Detected test framework.
        git_info: Git repository info.
        config_files: Relevant config files found (stored as strings).
    """

    type: ProjectType = ProjectType.UNKNOWN
    root: str = Field(default=".")
    name: str | None = None
    version: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    scripts: dict[str, str] = Field(default_factory=dict)
    test_framework: TestFramework = TestFramework.UNKNOWN
    git_info: GitInfo | None = None
    config_files: list[str] = Field(default_factory=list)

    @property
    def root_path(self) -> Path:
        """Get root as Path object."""
        return Path(self.root)
