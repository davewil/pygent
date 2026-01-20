"""Tests for system prompt building with project context."""

from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.context.models import GitInfo, ProjectContext, ProjectType, TestFramework
from chapgent.context.prompt import (
    _format_dependencies,
    _format_git_info,
    _format_scripts,
    _format_test_framework,
    _get_project_conventions,
    build_system_prompt,
)

# Helper function tests


class TestFormatDependencies:
    """Tests for _format_dependencies helper."""

    def test_empty_deps(self):
        """Test empty dependencies list."""
        result = _format_dependencies([])
        assert result == "None detected"

    def test_few_deps(self):
        """Test small number of dependencies."""
        result = _format_dependencies(["requests", "click", "pytest"])
        assert result == "requests, click, pytest"

    def test_many_deps_truncated(self):
        """Test dependencies list is truncated at limit."""
        deps = [f"pkg{i}" for i in range(15)]
        result = _format_dependencies(deps, limit=10)
        assert "pkg0" in result
        assert "pkg9" in result
        assert "(+5 more)" in result

    def test_custom_limit(self):
        """Test custom limit works."""
        deps = ["a", "b", "c", "d", "e"]
        result = _format_dependencies(deps, limit=3)
        assert result == "a, b, c (+2 more)"


class TestFormatScripts:
    """Tests for _format_scripts helper."""

    def test_empty_scripts(self):
        """Test empty scripts dict."""
        result = _format_scripts({})
        assert result == "None"

    def test_few_scripts(self):
        """Test small number of scripts."""
        scripts = {"test": "pytest", "lint": "ruff check"}
        result = _format_scripts(scripts)
        assert "test: pytest" in result
        assert "lint: ruff check" in result

    def test_many_scripts_truncated(self):
        """Test scripts dict is truncated at limit."""
        scripts = {f"script{i}": f"cmd{i}" for i in range(10)}
        result = _format_scripts(scripts, limit=5)
        assert "(+5 more)" in result


class TestFormatTestFramework:
    """Tests for _format_test_framework helper."""

    def test_unknown_framework(self):
        """Test unknown framework returns 'Unknown'."""
        result = _format_test_framework(TestFramework.UNKNOWN)
        assert result == "Unknown"

    def test_pytest_framework(self):
        """Test pytest formatting."""
        result = _format_test_framework(TestFramework.PYTEST)
        assert "pytest" in result
        assert "run with:" in result

    def test_jest_framework(self):
        """Test jest formatting."""
        result = _format_test_framework(TestFramework.JEST)
        assert "jest" in result
        assert "npm test" in result

    def test_go_test_framework(self):
        """Test go test formatting."""
        result = _format_test_framework(TestFramework.GO_TEST)
        assert "go test" in result

    def test_cargo_test_framework(self):
        """Test cargo test formatting."""
        result = _format_test_framework(TestFramework.CARGO_TEST)
        assert "cargo test" in result


class TestFormatGitInfo:
    """Tests for _format_git_info helper."""

    def test_no_git_info(self):
        """Test context without git info."""
        ctx = ProjectContext()
        result = _format_git_info(ctx)
        assert result == "Not a git repository"

    def test_with_branch(self):
        """Test git info with branch."""
        ctx = ProjectContext(git_info=GitInfo(branch="main"))
        result = _format_git_info(ctx)
        assert "Branch: main" in result

    def test_with_changes(self):
        """Test git info with uncommitted changes."""
        ctx = ProjectContext(git_info=GitInfo(has_changes=True))
        result = _format_git_info(ctx)
        assert "uncommitted changes" in result

    def test_clean_working_tree(self):
        """Test git info with clean working tree."""
        ctx = ProjectContext(git_info=GitInfo(has_changes=False, branch="main"))
        result = _format_git_info(ctx)
        assert "Clean working tree" in result

    def test_with_commit_count(self):
        """Test git info with commit count."""
        ctx = ProjectContext(git_info=GitInfo(commit_count=100))
        result = _format_git_info(ctx)
        assert "Commits: 100" in result


class TestGetProjectConventions:
    """Tests for _get_project_conventions helper."""

    def test_python_conventions(self):
        """Test Python project conventions."""
        result = _get_project_conventions(ProjectType.PYTHON)
        assert "PEP 8" in result
        assert "type hints" in result
        assert "docstrings" in result

    def test_node_conventions(self):
        """Test Node.js project conventions."""
        result = _get_project_conventions(ProjectType.NODE)
        assert "const" in result
        assert "async/await" in result

    def test_go_conventions(self):
        """Test Go project conventions."""
        result = _get_project_conventions(ProjectType.GO)
        assert "gofmt" in result
        assert "errors" in result

    def test_rust_conventions(self):
        """Test Rust project conventions."""
        result = _get_project_conventions(ProjectType.RUST)
        assert "rustfmt" in result
        assert "clippy" in result

    def test_unknown_conventions(self):
        """Test unknown project type conventions."""
        result = _get_project_conventions(ProjectType.UNKNOWN)
        assert "existing code style" in result


# build_system_prompt tests


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_minimal_context(self):
        """Test with minimal context."""
        ctx = ProjectContext()
        result = build_system_prompt("You are a helpful assistant.", ctx)

        assert "You are a helpful assistant." in result
        assert "Project Context" in result
        assert "Working Directory" in result

    def test_python_project_context(self):
        """Test with full Python project context."""
        ctx = ProjectContext(
            type=ProjectType.PYTHON,
            root="/home/user/myproject",
            name="myproject",
            version="1.0.0",
            dependencies=["requests", "click"],
            scripts={"test": "pytest", "lint": "ruff check"},
            test_framework=TestFramework.PYTEST,
            git_info=GitInfo(branch="main", has_changes=False),
            config_files=["pyproject.toml"],
        )
        result = build_system_prompt("Base prompt.", ctx)

        assert "Base prompt." in result
        assert "Project Type**: Python" in result
        assert "Project Name**: myproject" in result
        assert "Version**: 1.0.0" in result
        assert "requests" in result
        assert "test: pytest" in result
        assert "pytest" in result
        assert "Branch: main" in result
        assert "pyproject.toml" in result
        assert "PEP 8" in result  # Python conventions

    def test_node_project_context(self):
        """Test with Node.js project context."""
        ctx = ProjectContext(
            type=ProjectType.NODE,
            name="webapp",
            test_framework=TestFramework.JEST,
        )
        result = build_system_prompt("Base.", ctx)

        assert "Node" in result
        assert "webapp" in result
        assert "jest" in result

    def test_user_overrides_appended(self):
        """Test user overrides are appended."""
        ctx = ProjectContext()
        result = build_system_prompt(
            "Base prompt.",
            ctx,
            user_overrides="Always use tabs for indentation.",
        )

        assert "Base prompt." in result
        assert "User Customizations" in result
        assert "Always use tabs for indentation." in result

    def test_no_config_files_section_when_empty(self):
        """Test config files section not shown when empty."""
        ctx = ProjectContext(config_files=[])
        result = build_system_prompt("Base.", ctx)

        # Should not have config files line (only appears when non-empty)
        assert "Config Files**:" not in result

    def test_dependencies_shown_when_present(self):
        """Test dependencies are shown when present."""
        ctx = ProjectContext(dependencies=["dep1", "dep2"])
        result = build_system_prompt("Base.", ctx)

        assert "Key Dependencies" in result
        assert "dep1" in result

    def test_scripts_shown_when_present(self):
        """Test scripts are shown when present."""
        ctx = ProjectContext(scripts={"build": "npm run build"})
        result = build_system_prompt("Base.", ctx)

        assert "Available Scripts" in result
        assert "build: npm run build" in result


# Property-based tests


@given(
    base_prompt=st.text(min_size=1, max_size=100),
    project_name=st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
)
@settings(max_examples=20)
def test_build_system_prompt_preserves_base(base_prompt: str, project_name: str):
    """Property test: base prompt is always preserved."""
    ctx = ProjectContext(name=project_name.strip())
    result = build_system_prompt(base_prompt, ctx)
    assert base_prompt in result


@given(deps=st.lists(st.text(min_size=1, max_size=20).filter(lambda x: x.strip()), min_size=1, max_size=5))
@settings(max_examples=20)
def test_build_system_prompt_includes_deps(deps: list[str]):
    """Property test: dependencies are included in output."""
    clean_deps = [d.strip() for d in deps]
    ctx = ProjectContext(dependencies=clean_deps)
    result = build_system_prompt("Base.", ctx)

    # At least the first dependency should be visible
    assert clean_deps[0] in result


@given(user_override=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))
@settings(max_examples=20)
def test_build_system_prompt_includes_overrides(user_override: str):
    """Property test: user overrides are included when provided."""
    ctx = ProjectContext()
    result = build_system_prompt("Base.", ctx, user_overrides=user_override)
    assert user_override in result
    assert "User Customizations" in result
