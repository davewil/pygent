"""Tests for project detection and gitignore filtering."""

import json
import string
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chapgent.context.detection import (
    GitIgnoreFilter,
    _detect_git_info,
    _detect_go_project,
    _detect_node_project,
    _detect_python_project,
    _detect_rust_project,
    detect_project_context,
)
from chapgent.context.models import ProjectType, TestFramework

# GitIgnoreFilter tests


class TestGitIgnoreFilter:
    """Tests for GitIgnoreFilter class."""

    def test_default_excludes(self, tmp_path: Path):
        """Test default exclusion patterns."""
        filter_ = GitIgnoreFilter(tmp_path)

        # These should be ignored by default
        assert filter_.is_ignored(tmp_path / ".git" / "config")
        assert filter_.is_ignored(tmp_path / "__pycache__" / "module.pyc")
        assert filter_.is_ignored(tmp_path / "node_modules" / "express")
        assert filter_.is_ignored(tmp_path / ".venv" / "bin" / "python")
        assert filter_.is_ignored(tmp_path / "venv" / "lib")
        assert filter_.is_ignored(tmp_path / "dist" / "bundle.js")
        assert filter_.is_ignored(tmp_path / "build" / "output")
        assert filter_.is_ignored(tmp_path / ".mypy_cache")
        assert filter_.is_ignored(tmp_path / ".pytest_cache")

    def test_pyc_files_ignored(self, tmp_path: Path):
        """Test .pyc files are ignored."""
        filter_ = GitIgnoreFilter(tmp_path)
        assert filter_.is_ignored(tmp_path / "module.pyc")
        assert filter_.is_ignored(tmp_path / "src" / "module.pyc")

    def test_normal_files_not_ignored(self, tmp_path: Path):
        """Test normal files are not ignored."""
        filter_ = GitIgnoreFilter(tmp_path)
        assert not filter_.is_ignored(tmp_path / "src" / "main.py")
        assert not filter_.is_ignored(tmp_path / "README.md")
        assert not filter_.is_ignored(tmp_path / "package.json")

    def test_loads_gitignore_file(self, tmp_path: Path):
        """Test loading patterns from .gitignore."""
        (tmp_path / ".gitignore").write_text("*.log\nsecrets/\n", encoding="utf-8")
        filter_ = GitIgnoreFilter(tmp_path)

        assert filter_.is_ignored(tmp_path / "debug.log")
        assert filter_.is_ignored(tmp_path / "secrets" / "key.pem")

    def test_gitignore_comments_ignored(self, tmp_path: Path):
        """Test comments in .gitignore are ignored."""
        (tmp_path / ".gitignore").write_text("# Comment\n*.tmp\n", encoding="utf-8")
        filter_ = GitIgnoreFilter(tmp_path)

        assert filter_.is_ignored(tmp_path / "file.tmp")
        # "Comment" should not be a pattern
        assert not filter_.is_ignored(tmp_path / "Comment")

    def test_gitignore_empty_lines_ignored(self, tmp_path: Path):
        """Test empty lines in .gitignore are ignored."""
        (tmp_path / ".gitignore").write_text("*.tmp\n\n*.log\n", encoding="utf-8")
        filter_ = GitIgnoreFilter(tmp_path)

        assert filter_.is_ignored(tmp_path / "file.tmp")
        assert filter_.is_ignored(tmp_path / "file.log")

    def test_filter_paths(self, tmp_path: Path):
        """Test filtering a list of paths."""
        filter_ = GitIgnoreFilter(tmp_path)
        paths = [
            tmp_path / "src" / "main.py",
            tmp_path / "__pycache__" / "main.cpython-311.pyc",
            tmp_path / "tests" / "test_main.py",
            tmp_path / ".git" / "config",
        ]

        filtered = filter_.filter_paths(paths)
        assert len(filtered) == 2
        assert tmp_path / "src" / "main.py" in filtered
        assert tmp_path / "tests" / "test_main.py" in filtered

    def test_relative_path_handling(self, tmp_path: Path):
        """Test is_ignored works with relative paths."""
        filter_ = GitIgnoreFilter(tmp_path)
        assert filter_.is_ignored(Path("__pycache__"))
        assert filter_.is_ignored(Path("node_modules/package"))
        assert not filter_.is_ignored(Path("src/main.py"))

    def test_path_outside_root(self, tmp_path: Path):
        """Test paths outside root are not ignored."""
        filter_ = GitIgnoreFilter(tmp_path)
        other_path = tmp_path.parent / "other_project" / ".git"
        assert not filter_.is_ignored(other_path)


# Python project detection tests


class TestDetectPythonProject:
    """Tests for Python project detection."""

    @pytest.mark.asyncio
    async def test_pyproject_toml_detection(self, tmp_path: Path):
        """Test detection via pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "myproject"
version = "1.2.3"
dependencies = ["requests>=2.0", "click"]

[project.scripts]
myapp = "myproject.cli:main"

[tool.pytest]
testpaths = ["tests"]
""",
            encoding="utf-8",
        )

        ctx = await _detect_python_project(tmp_path)
        assert ctx is not None
        assert ctx.type == ProjectType.PYTHON
        assert ctx.name == "myproject"
        assert ctx.version == "1.2.3"
        assert "requests>=2.0" in ctx.dependencies
        assert "click" in ctx.dependencies
        assert ctx.test_framework == TestFramework.PYTEST
        assert "pyproject.toml" in ctx.config_files

    @pytest.mark.asyncio
    async def test_setup_py_detection(self, tmp_path: Path):
        """Test detection via setup.py."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()", encoding="utf-8")

        ctx = await _detect_python_project(tmp_path)
        assert ctx is not None
        assert ctx.type == ProjectType.PYTHON
        assert "setup.py" in ctx.config_files

    @pytest.mark.asyncio
    async def test_pytest_ini_detection(self, tmp_path: Path):
        """Test pytest detection via pytest.ini."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")
        (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

        ctx = await _detect_python_project(tmp_path)
        assert ctx is not None
        assert ctx.test_framework == TestFramework.PYTEST
        assert "pytest.ini" in ctx.config_files

    @pytest.mark.asyncio
    async def test_requirements_txt_dependencies(self, tmp_path: Path):
        """Test reading dependencies from requirements.txt."""
        (tmp_path / "setup.py").write_text("# setup", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text(
            "requests==2.28.0\nflask>=2.0\n# comment\npytest",
            encoding="utf-8",
        )

        ctx = await _detect_python_project(tmp_path)
        assert ctx is not None
        assert "requests" in ctx.dependencies
        assert "flask" in ctx.dependencies
        assert "pytest" in ctx.dependencies

    @pytest.mark.asyncio
    async def test_conftest_pytest_detection(self, tmp_path: Path):
        """Test pytest detection via tests/conftest.py."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "conftest.py").write_text("import pytest", encoding="utf-8")

        ctx = await _detect_python_project(tmp_path)
        assert ctx is not None
        assert ctx.test_framework == TestFramework.PYTEST

    @pytest.mark.asyncio
    async def test_no_python_project(self, tmp_path: Path):
        """Test returns None when not a Python project."""
        ctx = await _detect_python_project(tmp_path)
        assert ctx is None


# Node.js project detection tests


class TestDetectNodeProject:
    """Tests for Node.js project detection."""

    @pytest.mark.asyncio
    async def test_package_json_detection(self, tmp_path: Path):
        """Test detection via package.json."""
        (tmp_path / "package.json").write_text(
            json.dumps(
                {
                    "name": "myapp",
                    "version": "2.0.0",
                    "dependencies": {"express": "^4.18.0"},
                    "devDependencies": {"jest": "^29.0.0"},
                    "scripts": {"test": "jest", "start": "node index.js"},
                }
            ),
            encoding="utf-8",
        )

        ctx = await _detect_node_project(tmp_path)
        assert ctx is not None
        assert ctx.type == ProjectType.NODE
        assert ctx.name == "myapp"
        assert ctx.version == "2.0.0"
        assert "express" in ctx.dependencies
        assert "jest" in ctx.dependencies
        assert ctx.test_framework == TestFramework.JEST
        assert "package.json" in ctx.config_files

    @pytest.mark.asyncio
    async def test_vitest_detection(self, tmp_path: Path):
        """Test vitest framework detection."""
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"vitest": "^0.34.0"}}),
            encoding="utf-8",
        )

        ctx = await _detect_node_project(tmp_path)
        assert ctx is not None
        assert ctx.test_framework == TestFramework.VITEST

    @pytest.mark.asyncio
    async def test_mocha_detection(self, tmp_path: Path):
        """Test mocha framework detection."""
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"mocha": "^10.0.0"}}),
            encoding="utf-8",
        )

        ctx = await _detect_node_project(tmp_path)
        assert ctx is not None
        assert ctx.test_framework == TestFramework.MOCHA

    @pytest.mark.asyncio
    async def test_config_file_detection(self, tmp_path: Path):
        """Test detection of common config files."""
        (tmp_path / "package.json").write_text('{"name": "app"}', encoding="utf-8")
        (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
        (tmp_path / "jest.config.js").write_text("module.exports = {}", encoding="utf-8")

        ctx = await _detect_node_project(tmp_path)
        assert ctx is not None
        assert "tsconfig.json" in ctx.config_files
        assert "jest.config.js" in ctx.config_files

    @pytest.mark.asyncio
    async def test_invalid_package_json(self, tmp_path: Path):
        """Test handling of invalid package.json."""
        (tmp_path / "package.json").write_text("not valid json", encoding="utf-8")

        ctx = await _detect_node_project(tmp_path)
        assert ctx is not None
        assert ctx.type == ProjectType.NODE
        assert ctx.name is None

    @pytest.mark.asyncio
    async def test_no_node_project(self, tmp_path: Path):
        """Test returns None when not a Node project."""
        ctx = await _detect_node_project(tmp_path)
        assert ctx is None


# Go project detection tests


class TestDetectGoProject:
    """Tests for Go project detection."""

    @pytest.mark.asyncio
    async def test_go_mod_detection(self, tmp_path: Path):
        """Test detection via go.mod."""
        (tmp_path / "go.mod").write_text(
            """module github.com/user/myproject

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/stretchr/testify v1.8.4
)
""",
            encoding="utf-8",
        )

        ctx = await _detect_go_project(tmp_path)
        assert ctx is not None
        assert ctx.type == ProjectType.GO
        assert ctx.name == "myproject"
        assert ctx.test_framework == TestFramework.GO_TEST
        assert "github.com/gin-gonic/gin" in ctx.dependencies
        assert "go.mod" in ctx.config_files

    @pytest.mark.asyncio
    async def test_go_mod_with_single_require(self, tmp_path: Path):
        """Test go.mod with single-line require."""
        (tmp_path / "go.mod").write_text(
            """module myapp

require github.com/pkg/errors v0.9.1
""",
            encoding="utf-8",
        )

        ctx = await _detect_go_project(tmp_path)
        assert ctx is not None
        assert ctx.name == "myapp"
        assert "github.com/pkg/errors" in ctx.dependencies

    @pytest.mark.asyncio
    async def test_go_sum_detection(self, tmp_path: Path):
        """Test go.sum is added to config files."""
        (tmp_path / "go.mod").write_text("module myapp", encoding="utf-8")
        (tmp_path / "go.sum").write_text("hash", encoding="utf-8")

        ctx = await _detect_go_project(tmp_path)
        assert ctx is not None
        assert "go.sum" in ctx.config_files

    @pytest.mark.asyncio
    async def test_go_scripts(self, tmp_path: Path):
        """Test Go project has common scripts."""
        (tmp_path / "go.mod").write_text("module myapp", encoding="utf-8")

        ctx = await _detect_go_project(tmp_path)
        assert ctx is not None
        assert "build" in ctx.scripts
        assert "test" in ctx.scripts
        assert "run" in ctx.scripts

    @pytest.mark.asyncio
    async def test_no_go_project(self, tmp_path: Path):
        """Test returns None when not a Go project."""
        ctx = await _detect_go_project(tmp_path)
        assert ctx is None


# Rust project detection tests


class TestDetectRustProject:
    """Tests for Rust project detection."""

    @pytest.mark.asyncio
    async def test_cargo_toml_detection(self, tmp_path: Path):
        """Test detection via Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text(
            """
[package]
name = "myrust"
version = "0.1.0"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
""",
            encoding="utf-8",
        )

        ctx = await _detect_rust_project(tmp_path)
        assert ctx is not None
        assert ctx.type == ProjectType.RUST
        assert ctx.name == "myrust"
        assert ctx.version == "0.1.0"
        assert ctx.test_framework == TestFramework.CARGO_TEST
        assert "serde" in ctx.dependencies
        assert "tokio" in ctx.dependencies
        assert "criterion" in ctx.dependencies
        assert "Cargo.toml" in ctx.config_files

    @pytest.mark.asyncio
    async def test_cargo_lock_detection(self, tmp_path: Path):
        """Test Cargo.lock is added to config files."""
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'app'", encoding="utf-8")
        (tmp_path / "Cargo.lock").write_text("# lock file", encoding="utf-8")

        ctx = await _detect_rust_project(tmp_path)
        assert ctx is not None
        assert "Cargo.lock" in ctx.config_files

    @pytest.mark.asyncio
    async def test_rust_scripts(self, tmp_path: Path):
        """Test Rust project has common scripts."""
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'app'", encoding="utf-8")

        ctx = await _detect_rust_project(tmp_path)
        assert ctx is not None
        assert "build" in ctx.scripts
        assert "test" in ctx.scripts
        assert "run" in ctx.scripts
        assert "clippy" in ctx.scripts

    @pytest.mark.asyncio
    async def test_no_rust_project(self, tmp_path: Path):
        """Test returns None when not a Rust project."""
        ctx = await _detect_rust_project(tmp_path)
        assert ctx is None


# Git info detection tests


class TestDetectGitInfo:
    """Tests for git info detection."""

    @pytest.mark.asyncio
    async def test_no_git_repo(self, tmp_path: Path):
        """Test returns None when not in git repo."""
        info = await _detect_git_info(tmp_path)
        assert info is None

    @pytest.mark.asyncio
    async def test_git_repo_detection(self, tmp_path: Path):
        """Test detection of git repository."""
        # Create a .git directory (minimal simulation)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Mock git commands
        async def mock_run_git(*args, **kwargs):
            cmd = args[0][0] if args[0] else None
            if cmd == "rev-parse" and args[0][1] == "--abbrev-ref":
                return "main"
            if cmd == "config":
                return "https://github.com/user/repo.git"
            if cmd == "status":
                return ""
            if cmd == "rev-list":
                return "42"
            if cmd == "rev-parse" and args[0][1] == "--short":
                return "abc1234"
            return None

        with patch("chapgent.context.detection._run_git_command", side_effect=mock_run_git):
            info = await _detect_git_info(tmp_path)

        assert info is not None
        assert info.branch == "main"
        assert info.remote == "https://github.com/user/repo.git"
        assert info.has_changes is False
        assert info.commit_count == 42
        assert info.last_commit == "abc1234"

    @pytest.mark.asyncio
    async def test_git_with_changes(self, tmp_path: Path):
        """Test detecting uncommitted changes."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        async def mock_run_git(args, cwd):
            if args[0] == "status":
                return " M modified.txt"
            return None

        with patch("chapgent.context.detection._run_git_command", side_effect=mock_run_git):
            info = await _detect_git_info(tmp_path)

        assert info is not None
        assert info.has_changes is True


# Main detect_project_context tests


class TestDetectProjectContext:
    """Tests for the main detect_project_context function."""

    @pytest.mark.asyncio
    async def test_detects_python_project(self, tmp_path: Path):
        """Test detecting Python project."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'mypy'", encoding="utf-8")

        ctx = await detect_project_context(tmp_path)
        assert ctx.type == ProjectType.PYTHON
        assert str(tmp_path) in ctx.root

    @pytest.mark.asyncio
    async def test_detects_node_project(self, tmp_path: Path):
        """Test detecting Node project."""
        (tmp_path / "package.json").write_text('{"name": "mynode"}', encoding="utf-8")

        ctx = await detect_project_context(tmp_path)
        assert ctx.type == ProjectType.NODE

    @pytest.mark.asyncio
    async def test_detects_go_project(self, tmp_path: Path):
        """Test detecting Go project."""
        (tmp_path / "go.mod").write_text("module mygo", encoding="utf-8")

        ctx = await detect_project_context(tmp_path)
        assert ctx.type == ProjectType.GO

    @pytest.mark.asyncio
    async def test_detects_rust_project(self, tmp_path: Path):
        """Test detecting Rust project."""
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'myrust'", encoding="utf-8")

        ctx = await detect_project_context(tmp_path)
        assert ctx.type == ProjectType.RUST

    @pytest.mark.asyncio
    async def test_unknown_project(self, tmp_path: Path):
        """Test unknown project type."""
        ctx = await detect_project_context(tmp_path)
        assert ctx.type == ProjectType.UNKNOWN

    @pytest.mark.asyncio
    async def test_python_takes_precedence(self, tmp_path: Path):
        """Test Python detection takes precedence over Node."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'mypy'", encoding="utf-8")
        (tmp_path / "package.json").write_text('{"name": "mynode"}', encoding="utf-8")

        ctx = await detect_project_context(tmp_path)
        assert ctx.type == ProjectType.PYTHON

    @pytest.mark.asyncio
    async def test_default_path(self, tmp_path: Path, monkeypatch):
        """Test using default current working directory."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        ctx = await detect_project_context()
        assert ctx.type == ProjectType.PYTHON

    @pytest.mark.asyncio
    async def test_includes_git_info(self, tmp_path: Path):
        """Test git info is included."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")
        (tmp_path / ".git").mkdir()

        with patch("chapgent.context.detection._detect_git_info") as mock_git:
            from chapgent.context.models import GitInfo

            mock_git.return_value = GitInfo(branch="main")
            ctx = await detect_project_context(tmp_path)

        assert ctx.git_info is not None
        assert ctx.git_info.branch == "main"


# Property-based tests


@given(
    patterns=st.lists(
        st.text(min_size=1, max_size=20, alphabet=string.ascii_letters + string.digits + "._-").filter(
            lambda x: x.strip() and not x.startswith("#")
        ),
        min_size=0,
        max_size=5,
    )
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_gitignore_filter_loads_patterns(patterns: list[str], tmp_path: Path):
    """Property test for gitignore pattern loading."""
    # Create unique subdir to avoid test pollution
    test_dir = tmp_path / str(uuid.uuid4())
    test_dir.mkdir(parents=True)

    content = "\n".join(patterns)
    (test_dir / ".gitignore").write_text(content, encoding="utf-8")

    filter_ = GitIgnoreFilter(test_dir)

    # All patterns should be loaded (plus defaults)
    for pattern in patterns:
        assert pattern in filter_.patterns


@given(
    project_name=st.text(min_size=1, max_size=30, alphabet=string.ascii_letters + string.digits).filter(
        lambda x: x.strip()
    ),
    version=st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True),
)
@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
@pytest.mark.asyncio
async def test_python_project_detection_property(project_name: str, version: str, tmp_path: Path):
    """Property test for Python project detection."""
    test_dir = tmp_path / str(uuid.uuid4())
    test_dir.mkdir(parents=True)

    (test_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{project_name.strip()}"\nversion = "{version}"',
        encoding="utf-8",
    )

    ctx = await detect_project_context(test_dir)
    assert ctx.type == ProjectType.PYTHON
    assert ctx.name == project_name.strip()
    assert ctx.version == version


@given(
    deps=st.lists(
        st.text(min_size=1, max_size=20, alphabet=string.ascii_letters + string.digits + "_-").filter(
            lambda x: x.strip() and x[0].isalpha()
        ),
        min_size=0,
        max_size=5,
    )
)
@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
@pytest.mark.asyncio
async def test_node_project_deps_property(deps: list[str], tmp_path: Path):
    """Property test for Node.js dependency detection."""
    test_dir = tmp_path / str(uuid.uuid4())
    test_dir.mkdir(parents=True)

    deps_dict = {d: "^1.0.0" for d in deps}
    (test_dir / "package.json").write_text(
        json.dumps({"name": "test", "dependencies": deps_dict}),
        encoding="utf-8",
    )

    ctx = await detect_project_context(test_dir)
    assert ctx.type == ProjectType.NODE
    for dep in deps:
        assert dep in ctx.dependencies
