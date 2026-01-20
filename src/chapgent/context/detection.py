"""Project detection and gitignore filtering."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import sys
from collections.abc import Iterable
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

from chapgent.context.models import GitInfo, ProjectContext, ProjectType, TestFramework


class GitIgnoreFilter:
    """Filter file operations based on .gitignore patterns.

    Attributes:
        root: The project root directory.
        patterns: List of gitignore patterns to match against.
    """

    # Default patterns to always exclude
    DEFAULT_EXCLUDES = [
        ".git",
        ".git/**",
        "__pycache__",
        "__pycache__/**",
        "*.pyc",
        "node_modules",
        "node_modules/**",
        ".venv",
        ".venv/**",
        "venv",
        "venv/**",
        ".env",
        "*.egg-info",
        "*.egg-info/**",
        "dist",
        "dist/**",
        "build",
        "build/**",
        ".mypy_cache",
        ".mypy_cache/**",
        ".pytest_cache",
        ".pytest_cache/**",
        ".ruff_cache",
        ".ruff_cache/**",
        "*.so",
        "*.dylib",
        ".DS_Store",
        "Thumbs.db",
        "target",
        "target/**",
    ]

    def __init__(self, root: Path) -> None:
        """Initialize the filter with a project root.

        Args:
            root: The project root directory.
        """
        self.root = root
        self.patterns: list[str] = list(self.DEFAULT_EXCLUDES)
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        """Load patterns from .gitignore file if it exists."""
        gitignore_path = self.root / ".gitignore"
        if gitignore_path.is_file():
            content = gitignore_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                self.patterns.append(line)

    def is_ignored(self, path: Path) -> bool:
        """Check if a path should be ignored.

        Args:
            path: The path to check (can be absolute or relative).

        Returns:
            True if the path should be ignored.
        """
        # Make path relative to root for matching
        try:
            if path.is_absolute():
                rel_path = path.relative_to(self.root)
            else:
                rel_path = path
        except ValueError:
            # Path is not under root
            return False

        path_str = str(rel_path)
        path_parts = rel_path.parts

        for pattern in self.patterns:
            # Handle negation patterns (we skip them - full gitignore semantics is complex)
            if pattern.startswith("!"):
                continue

            # Remove leading slash (means root-relative in gitignore)
            check_pattern = pattern.lstrip("/")

            # Handle directory patterns (ending with /)
            # e.g., "secrets/" should match "secrets/key.pem"
            if check_pattern.endswith("/"):
                dir_pattern = check_pattern.rstrip("/")
                # Check if any path component matches the directory pattern
                for part in path_parts:
                    if fnmatch.fnmatch(part, dir_pattern):
                        return True
                continue

            # Check if pattern matches the full path
            if fnmatch.fnmatch(path_str, check_pattern):
                return True

            # Check if any parent directory matches
            for i, part in enumerate(path_parts):
                partial_path = "/".join(path_parts[: i + 1])
                if fnmatch.fnmatch(partial_path, check_pattern):
                    return True
                if fnmatch.fnmatch(part, check_pattern):
                    return True

        return False

    def filter_paths(self, paths: Iterable[Path]) -> list[Path]:
        """Filter out ignored paths.

        Args:
            paths: Iterable of paths to filter.

        Returns:
            List of paths that are not ignored.
        """
        return [p for p in paths if not self.is_ignored(p)]


async def _run_git_command(args: list[str], cwd: Path) -> str | None:
    """Run a git command and return stdout, or None on error."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
    except (OSError, FileNotFoundError):
        pass
    return None


async def _detect_git_info(path: Path) -> GitInfo | None:
    """Detect git repository information.

    Args:
        path: The path to check for git info.

    Returns:
        GitInfo if in a git repo, None otherwise.
    """
    # Check if this is a git repo
    git_dir = path / ".git"
    if not git_dir.exists():
        return None

    info = GitInfo()

    # Get current branch
    branch = await _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], path)
    if branch:
        info.branch = branch

    # Get remote URL
    remote = await _run_git_command(["config", "--get", "remote.origin.url"], path)
    if remote:
        info.remote = remote

    # Check for changes
    status = await _run_git_command(["status", "--porcelain"], path)
    if status is not None:
        info.has_changes = len(status) > 0

    # Get commit count
    count = await _run_git_command(["rev-list", "--count", "HEAD"], path)
    if count:
        try:
            info.commit_count = int(count)
        except ValueError:
            pass

    # Get last commit hash
    last_commit = await _run_git_command(["rev-parse", "--short", "HEAD"], path)
    if last_commit:
        info.last_commit = last_commit

    return info


async def _detect_python_project(path: Path) -> ProjectContext | None:
    """Detect Python project details.

    Args:
        path: The project root path.

    Returns:
        ProjectContext if Python project detected, None otherwise.
    """
    pyproject_path = path / "pyproject.toml"
    setup_py_path = path / "setup.py"

    if not pyproject_path.exists() and not setup_py_path.exists():
        return None

    context = ProjectContext(
        type=ProjectType.PYTHON,
        root=str(path),
    )

    config_files: list[str] = []

    # Parse pyproject.toml if it exists
    if pyproject_path.exists():
        config_files.append("pyproject.toml")
        content = await asyncio.to_thread(lambda: pyproject_path.read_text(encoding="utf-8"))
        try:
            data = tomllib.loads(content)

            # Get project name and version
            project = data.get("project", {})
            context.name = project.get("name")
            context.version = project.get("version")

            # Get dependencies
            deps = project.get("dependencies", [])
            context.dependencies = deps[:50]  # Limit for sanity

            # Get scripts
            scripts = project.get("scripts", {})
            context.scripts = dict(list(scripts.items())[:20])

            # Detect test framework
            if "tool" in data:
                if "pytest" in data["tool"]:
                    context.test_framework = TestFramework.PYTEST

        except Exception:
            pass

    if setup_py_path.exists():
        config_files.append("setup.py")

    # Check for pytest.ini
    pytest_ini = path / "pytest.ini"
    if pytest_ini.exists():
        config_files.append("pytest.ini")
        context.test_framework = TestFramework.PYTEST

    # Check for setup.cfg
    setup_cfg = path / "setup.cfg"
    if setup_cfg.exists():
        config_files.append("setup.cfg")

    # Check for requirements.txt
    requirements_txt = path / "requirements.txt"
    if requirements_txt.exists():
        config_files.append("requirements.txt")
        if not context.dependencies:
            content = await asyncio.to_thread(lambda: requirements_txt.read_text(encoding="utf-8"))
            deps = [
                line.strip().split("==")[0].split(">=")[0].split("<=")[0]
                for line in content.splitlines()
                if line.strip() and not line.startswith("#")
            ]
            context.dependencies = deps[:50]

    # Default to pytest if we see tests/ directory with conftest.py
    if context.test_framework == TestFramework.UNKNOWN:
        conftest = path / "tests" / "conftest.py"
        if conftest.exists():
            context.test_framework = TestFramework.PYTEST

    context.config_files = config_files
    return context


async def _detect_node_project(path: Path) -> ProjectContext | None:
    """Detect Node.js project details.

    Args:
        path: The project root path.

    Returns:
        ProjectContext if Node project detected, None otherwise.
    """
    package_json_path = path / "package.json"

    if not package_json_path.exists():
        return None

    context = ProjectContext(
        type=ProjectType.NODE,
        root=str(path),
    )

    config_files = ["package.json"]

    content = await asyncio.to_thread(lambda: package_json_path.read_text(encoding="utf-8"))
    try:
        data = json.loads(content)

        context.name = data.get("name")
        context.version = data.get("version")

        # Get dependencies
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())
        context.dependencies = (deps + dev_deps)[:50]

        # Get scripts
        scripts = data.get("scripts", {})
        context.scripts = dict(list(scripts.items())[:20])

        # Detect test framework from dependencies
        all_deps = set(deps + dev_deps)
        if "vitest" in all_deps:
            context.test_framework = TestFramework.VITEST
        elif "jest" in all_deps:
            context.test_framework = TestFramework.JEST
        elif "mocha" in all_deps:
            context.test_framework = TestFramework.MOCHA

    except json.JSONDecodeError:
        pass

    # Check for common config files
    for config_file in [
        "tsconfig.json",
        "vite.config.ts",
        "vite.config.js",
        "jest.config.js",
        "jest.config.ts",
        "vitest.config.ts",
        ".eslintrc.json",
        ".eslintrc.js",
    ]:
        if (path / config_file).exists():
            config_files.append(config_file)

    context.config_files = config_files
    return context


async def _detect_go_project(path: Path) -> ProjectContext | None:
    """Detect Go project details.

    Args:
        path: The project root path.

    Returns:
        ProjectContext if Go project detected, None otherwise.
    """
    go_mod_path = path / "go.mod"

    if not go_mod_path.exists():
        return None

    context = ProjectContext(
        type=ProjectType.GO,
        root=str(path),
        test_framework=TestFramework.GO_TEST,
    )

    config_files = ["go.mod"]

    content = await asyncio.to_thread(lambda: go_mod_path.read_text(encoding="utf-8"))
    lines = content.splitlines()

    # Parse module name from first line
    for line in lines:
        line = line.strip()
        if line.startswith("module "):
            module_name = line[7:].strip()
            # Extract short name from module path
            context.name = module_name.split("/")[-1]
            break

    # Parse require statements for dependencies
    deps: list[str] = []
    in_require_block = False
    for line in lines:
        line = line.strip()
        if line == "require (":
            in_require_block = True
            continue
        if line == ")":
            in_require_block = False
            continue
        if in_require_block and line:
            # Extract module name (first part before space)
            parts = line.split()
            if parts:
                deps.append(parts[0])
        elif line.startswith("require "):
            # Single require statement
            parts = line[8:].strip().split()
            if parts:
                deps.append(parts[0])

    context.dependencies = deps[:50]

    # Add common scripts
    context.scripts = {
        "build": "go build ./...",
        "test": "go test ./...",
        "run": "go run .",
    }

    # Check for go.sum
    if (path / "go.sum").exists():
        config_files.append("go.sum")

    context.config_files = config_files
    return context


async def _detect_rust_project(path: Path) -> ProjectContext | None:
    """Detect Rust project details.

    Args:
        path: The project root path.

    Returns:
        ProjectContext if Rust project detected, None otherwise.
    """
    cargo_toml_path = path / "Cargo.toml"

    if not cargo_toml_path.exists():
        return None

    context = ProjectContext(
        type=ProjectType.RUST,
        root=str(path),
        test_framework=TestFramework.CARGO_TEST,
    )

    config_files = ["Cargo.toml"]

    content = await asyncio.to_thread(lambda: cargo_toml_path.read_text(encoding="utf-8"))
    try:
        data = tomllib.loads(content)

        # Get package info
        package = data.get("package", {})
        context.name = package.get("name")
        context.version = package.get("version")

        # Get dependencies
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("dev-dependencies", {}).keys())
        context.dependencies = (deps + dev_deps)[:50]

        # Add common scripts
        context.scripts = {
            "build": "cargo build",
            "test": "cargo test",
            "run": "cargo run",
            "check": "cargo check",
            "clippy": "cargo clippy",
        }

    except Exception:
        pass

    # Check for Cargo.lock
    if (path / "Cargo.lock").exists():
        config_files.append("Cargo.lock")

    context.config_files = config_files
    return context


async def detect_project_context(path: Path | None = None) -> ProjectContext:
    """Detect project type and gather context.

    Checks for various project markers in the following order:
    - pyproject.toml, setup.py -> Python
    - package.json -> Node.js
    - go.mod -> Go
    - Cargo.toml -> Rust

    Args:
        path: The directory to analyze. Defaults to current working directory.

    Returns:
        ProjectContext with detected project information.
    """
    if path is None:
        path = Path.cwd()

    path = path.resolve()

    # Try each project type detector in order
    detectors = [
        _detect_python_project,
        _detect_node_project,
        _detect_go_project,
        _detect_rust_project,
    ]

    for detector in detectors:
        context = await detector(path)
        if context is not None:
            # Add git info
            context.git_info = await _detect_git_info(path)
            return context

    # Return unknown project type
    return ProjectContext(
        type=ProjectType.UNKNOWN,
        root=str(path),
        git_info=await _detect_git_info(path),
    )
