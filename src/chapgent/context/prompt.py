"""System prompt building with project context injection."""

from __future__ import annotations

from chapgent.context.models import ProjectContext, ProjectType, TestFramework


def _format_dependencies(deps: list[str], limit: int = 10) -> str:
    """Format dependencies list for display.

    Args:
        deps: List of dependency names.
        limit: Maximum number to display.

    Returns:
        Formatted string of dependencies.
    """
    if not deps:
        return "None detected"
    if len(deps) <= limit:
        return ", ".join(deps)
    return ", ".join(deps[:limit]) + f" (+{len(deps) - limit} more)"


def _format_scripts(scripts: dict[str, str], limit: int = 5) -> str:
    """Format scripts dict for display.

    Args:
        scripts: Dictionary of script name to command.
        limit: Maximum number to display.

    Returns:
        Formatted string of scripts.
    """
    if not scripts:
        return "None"
    items = list(scripts.items())[:limit]
    lines = [f"  - {name}: {cmd}" for name, cmd in items]
    if len(scripts) > limit:
        lines.append(f"  (+{len(scripts) - limit} more)")
    return "\n".join(lines)


def _format_test_framework(framework: TestFramework) -> str:
    """Format test framework info.

    Args:
        framework: The detected test framework.

    Returns:
        Formatted string with test command hint.
    """
    if framework == TestFramework.UNKNOWN:
        return "Unknown"

    commands = {
        TestFramework.PYTEST: "pytest",
        TestFramework.UNITTEST: "python -m unittest",
        TestFramework.JEST: "npm test / npx jest",
        TestFramework.MOCHA: "npm test / npx mocha",
        TestFramework.VITEST: "npm test / npx vitest",
        TestFramework.GO_TEST: "go test ./...",
        TestFramework.CARGO_TEST: "cargo test",
    }

    cmd = commands.get(framework, str(framework.value))
    return f"{framework.value} (run with: {cmd})"


def _format_git_info(context: ProjectContext) -> str:
    """Format git information.

    Args:
        context: The project context.

    Returns:
        Formatted string of git info.
    """
    if context.git_info is None:
        return "Not a git repository"

    gi = context.git_info
    lines = []
    if gi.branch:
        lines.append(f"Branch: {gi.branch}")
    if gi.has_changes:
        lines.append("Status: Has uncommitted changes")
    else:
        lines.append("Status: Clean working tree")
    if gi.commit_count:
        lines.append(f"Commits: {gi.commit_count}")

    return "\n".join(lines) if lines else "Git repository detected"


def _get_project_conventions(project_type: ProjectType) -> str:
    """Get coding conventions for a project type.

    Args:
        project_type: The detected project type.

    Returns:
        String with coding conventions.
    """
    conventions = {
        ProjectType.PYTHON: """
- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Write docstrings in Google style format
- Use async/await for I/O operations
- Prefer pathlib.Path over os.path
- Use pytest for testing""",
        ProjectType.NODE: """
- Follow ESLint/Prettier configurations if present
- Use async/await for asynchronous code
- Prefer const over let, avoid var
- Use TypeScript types if tsconfig.json exists
- Follow the existing import style (ESM vs CommonJS)""",
        ProjectType.GO: """
- Follow Go formatting standards (gofmt)
- Use meaningful variable names
- Handle errors explicitly
- Use defer for cleanup operations
- Keep functions small and focused
- Use table-driven tests""",
        ProjectType.RUST: """
- Follow Rust formatting standards (rustfmt)
- Use Result for fallible operations
- Prefer references over ownership when possible
- Use clippy lints
- Write documentation comments with examples""",
    }
    return conventions.get(project_type, "- Follow existing code style and patterns")


def build_system_prompt(
    base_prompt: str,
    context: ProjectContext,
    user_overrides: str | None = None,
) -> str:
    """Build system prompt with project context.

    Injects project type, structure, available commands, and coding conventions
    into the base system prompt.

    Args:
        base_prompt: The base system prompt to enhance.
        context: The detected project context.
        user_overrides: Optional user customizations to append.

    Returns:
        Enhanced system prompt with project context.
    """
    # Build context section
    context_lines = [
        "",
        "## Project Context",
        "",
    ]

    # Project type
    if context.type != ProjectType.UNKNOWN:
        context_lines.append(f"**Project Type**: {context.type.value.title()}")
        if context.name:
            context_lines.append(f"**Project Name**: {context.name}")
        if context.version:
            context_lines.append(f"**Version**: {context.version}")
        context_lines.append("")

    # Working directory
    context_lines.append(f"**Working Directory**: {context.root}")
    context_lines.append("")

    # Dependencies (if any)
    if context.dependencies:
        context_lines.append(f"**Key Dependencies**: {_format_dependencies(context.dependencies)}")
        context_lines.append("")

    # Available scripts
    if context.scripts:
        context_lines.append("**Available Scripts**:")
        context_lines.append(_format_scripts(context.scripts))
        context_lines.append("")

    # Test framework
    context_lines.append(f"**Test Framework**: {_format_test_framework(context.test_framework)}")
    context_lines.append("")

    # Git info
    context_lines.append("**Git Status**:")
    context_lines.append(_format_git_info(context))
    context_lines.append("")

    # Config files
    if context.config_files:
        context_lines.append(f"**Config Files**: {', '.join(context.config_files)}")
        context_lines.append("")

    # Coding conventions
    context_lines.append("## Coding Conventions")
    context_lines.append(_get_project_conventions(context.type))
    context_lines.append("")

    # Combine everything
    sections = [base_prompt]
    sections.append("\n".join(context_lines))

    if user_overrides:
        sections.append("")
        sections.append("## User Customizations")
        sections.append(user_overrides)

    return "\n".join(sections)
