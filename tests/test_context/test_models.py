"""Tests for context models."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.context.models import (
    GitInfo,
    ProjectContext,
    ProjectType,
    TestFramework,
)

# Enum tests (consolidated)


class TestEnums:
    """Tests for TestFramework and ProjectType enums."""

    @pytest.mark.parametrize(
        "enum_cls,value,expected",
        [
            (TestFramework, "pytest", TestFramework.PYTEST),
            (TestFramework, "unittest", TestFramework.UNITTEST),
            (TestFramework, "jest", TestFramework.JEST),
            (TestFramework, "mocha", TestFramework.MOCHA),
            (TestFramework, "vitest", TestFramework.VITEST),
            (TestFramework, "go test", TestFramework.GO_TEST),
            (TestFramework, "cargo test", TestFramework.CARGO_TEST),
            (TestFramework, "unknown", TestFramework.UNKNOWN),
            (ProjectType, "python", ProjectType.PYTHON),
            (ProjectType, "node", ProjectType.NODE),
            (ProjectType, "go", ProjectType.GO),
            (ProjectType, "rust", ProjectType.RUST),
            (ProjectType, "unknown", ProjectType.UNKNOWN),
        ],
    )
    def test_enum_values_and_from_string(self, enum_cls, value: str, expected):
        """Test enum values and construction from string."""
        assert expected.value == value
        assert enum_cls(value) == expected

    @pytest.mark.parametrize("enum_cls", [TestFramework, ProjectType])
    def test_invalid_enum_raises_error(self, enum_cls):
        """Test invalid enum value raises ValueError."""
        with pytest.raises(ValueError):
            enum_cls("invalid_value")


# GitInfo model tests (consolidated)


class TestGitInfo:
    """Tests for GitInfo model."""

    def test_defaults_and_explicit_values(self):
        """Test GitInfo with defaults and explicit values."""
        default = GitInfo()
        assert (default.branch, default.remote, default.has_changes, default.commit_count, default.last_commit) == (
            None,
            None,
            False,
            0,
            None,
        )
        explicit = GitInfo(
            branch="main",
            remote="https://github.com/user/repo.git",
            has_changes=True,
            commit_count=42,
            last_commit="abc123",
        )
        assert (
            explicit.branch,
            explicit.remote,
            explicit.has_changes,
            explicit.commit_count,
            explicit.last_commit,
        ) == ("main", "https://github.com/user/repo.git", True, 42, "abc123")

    def test_serialization_roundtrip(self):
        """Test GitInfo JSON serialization roundtrip."""
        info = GitInfo(branch="main", has_changes=True)
        data = info.model_dump()
        info2 = GitInfo.model_validate(data)
        assert (info2.branch, info2.has_changes) == ("main", True)


# ProjectContext model tests


def test_project_context_defaults():
    """Test ProjectContext default values."""
    ctx = ProjectContext()
    assert ctx.type == ProjectType.UNKNOWN
    assert ctx.root == "."
    assert ctx.name is None
    assert ctx.version is None
    assert ctx.dependencies == []
    assert ctx.scripts == {}
    assert ctx.test_framework == TestFramework.UNKNOWN
    assert ctx.git_info is None
    assert ctx.config_files == []


def test_project_context_with_values():
    """Test ProjectContext with explicit values."""
    ctx = ProjectContext(
        type=ProjectType.PYTHON,
        root="/home/user/project",
        name="myproject",
        version="1.0.0",
        dependencies=["requests", "pytest"],
        scripts={"test": "pytest", "lint": "ruff check"},
        test_framework=TestFramework.PYTEST,
        git_info=GitInfo(branch="main"),
        config_files=["pyproject.toml", "setup.cfg"],
    )
    assert ctx.type == ProjectType.PYTHON
    assert ctx.root == "/home/user/project"
    assert ctx.name == "myproject"
    assert ctx.version == "1.0.0"
    assert ctx.dependencies == ["requests", "pytest"]
    assert ctx.scripts == {"test": "pytest", "lint": "ruff check"}
    assert ctx.test_framework == TestFramework.PYTEST
    assert ctx.git_info is not None
    assert ctx.git_info.branch == "main"
    assert ctx.config_files == ["pyproject.toml", "setup.cfg"]


def test_project_context_root_path_property():
    """Test ProjectContext.root_path property returns Path object."""
    import sys

    # Use platform-appropriate absolute path
    if sys.platform == "win32":
        test_path = "C:\\Users\\user\\project"
    else:
        test_path = "/home/user/project"

    ctx = ProjectContext(root=test_path)
    path = ctx.root_path
    # Path separators differ between platforms, so just check the parts
    assert path.parts[-1] == "project"
    assert "user" in path.parts or "Users" in path.parts
    assert path.is_absolute()


def test_project_context_serialization():
    """Test ProjectContext JSON serialization."""
    ctx = ProjectContext(
        type=ProjectType.NODE,
        root="/app",
        name="webapp",
        dependencies=["express"],
        git_info=GitInfo(branch="develop"),
    )
    data = ctx.model_dump()
    assert data["type"] == "node"
    assert data["root"] == "/app"
    assert data["name"] == "webapp"
    assert data["git_info"]["branch"] == "develop"

    # Can reconstruct from dict
    ctx2 = ProjectContext.model_validate(data)
    assert ctx2.type == ProjectType.NODE
    assert ctx2.git_info is not None
    assert ctx2.git_info.branch == "develop"


def test_project_context_json_round_trip():
    """Test ProjectContext survives JSON round trip."""
    ctx = ProjectContext(
        type=ProjectType.RUST,
        root="/projects/myrust",
        name="myrust",
        version="0.1.0",
        test_framework=TestFramework.CARGO_TEST,
    )
    json_str = ctx.model_dump_json()
    ctx2 = ProjectContext.model_validate_json(json_str)

    assert ctx2.type == ctx.type
    assert ctx2.root == ctx.root
    assert ctx2.name == ctx.name
    assert ctx2.version == ctx.version
    assert ctx2.test_framework == ctx.test_framework


# Property-based tests


@given(
    name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
    version=st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True),
)
@settings(max_examples=20)
def test_project_context_properties(name: str, version: str):
    """Property test for ProjectContext serialization."""
    ctx = ProjectContext(
        type=ProjectType.PYTHON,
        name=name.strip(),
        version=version,
    )
    data = ctx.model_dump()
    ctx2 = ProjectContext.model_validate(data)
    assert ctx2.name == ctx.name
    assert ctx2.version == ctx.version


@given(
    branch=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
    commit_count=st.integers(min_value=0, max_value=100000),
)
@settings(max_examples=20)
def test_git_info_properties(branch: str, commit_count: int):
    """Property test for GitInfo serialization."""
    info = GitInfo(branch=branch.strip(), commit_count=commit_count)
    data = info.model_dump()
    info2 = GitInfo.model_validate(data)
    assert info2.branch == info.branch
    assert info2.commit_count == info.commit_count
