"""Tests for system prompt loading and template variable resolution."""

from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.config.prompt import (
    TEMPLATE_VARIABLES,
    PromptLoadError,
    build_full_system_prompt,
    get_effective_prompt,
    get_template_variables,
    load_prompt_file,
    resolve_template_variables,
)
from chapgent.config.settings import DEFAULT_SYSTEM_PROMPT, SystemPromptSettings
from chapgent.context.models import GitInfo, ProjectContext, ProjectType, TestFramework


class TestTemplateVariables:
    """Tests for TEMPLATE_VARIABLES constant."""

    def test_template_variables_contains_expected_keys(self) -> None:
        """Verify all expected template variables are defined."""
        expected = {"project_name", "project_type", "current_dir", "git_branch", "date", "os"}
        assert set(TEMPLATE_VARIABLES.keys()) == expected

    def test_template_variables_have_descriptions(self) -> None:
        """All template variables should have non-empty descriptions."""
        for name, desc in TEMPLATE_VARIABLES.items():
            assert desc, f"Variable {name} has empty description"
            assert isinstance(desc, str)


class TestGetTemplateVariables:
    """Tests for get_template_variables function."""

    def test_without_context_returns_defaults(self) -> None:
        """Without context, returns basic system info."""
        variables = get_template_variables()

        assert "current_dir" in variables
        assert "date" in variables
        assert "os" in variables
        assert "project_name" in variables
        assert "project_type" in variables
        assert "git_branch" in variables

        # Check types and values
        assert variables["os"] == platform.system()
        assert variables["project_type"] == "unknown"
        assert variables["git_branch"] == "N/A"

    def test_date_format(self) -> None:
        """Date should be in YYYY-MM-DD format."""
        variables = get_template_variables()
        date = variables["date"]

        # Verify format by parsing
        parsed = datetime.strptime(date, "%Y-%m-%d")
        assert parsed.date() == datetime.now().date()

    def test_with_project_context(self) -> None:
        """With context, returns project-specific values."""
        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/project",
            name="my-project",
            git_info=GitInfo(branch="main"),
        )

        variables = get_template_variables(context)

        assert variables["project_name"] == "my-project"
        assert variables["project_type"] == "python"
        assert variables["git_branch"] == "main"

    def test_with_context_no_name_uses_directory(self) -> None:
        """If project has no name, uses directory name."""
        context = ProjectContext(
            type=ProjectType.NODE,
            root="/path/to/my-app",
            name=None,
        )

        variables = get_template_variables(context)
        assert variables["project_name"] == "my-app"

    def test_with_context_no_git_info(self) -> None:
        """Without git info, branch is N/A."""
        context = ProjectContext(
            type=ProjectType.RUST,
            root="/project",
            git_info=None,
        )

        variables = get_template_variables(context)
        assert variables["git_branch"] == "N/A"

    def test_with_context_no_branch(self) -> None:
        """With git info but no branch, returns N/A."""
        context = ProjectContext(
            type=ProjectType.GO,
            root="/project",
            git_info=GitInfo(branch=None),
        )

        variables = get_template_variables(context)
        assert variables["git_branch"] == "N/A"


class TestResolveTemplateVariables:
    """Tests for resolve_template_variables function."""

    def test_resolves_known_variables(self) -> None:
        """Known template variables are replaced."""
        content = "Project: {project_name}, Type: {project_type}"
        variables = {"project_name": "test", "project_type": "python"}

        result = resolve_template_variables(content, variables)
        assert result == "Project: test, Type: python"

    def test_preserves_unknown_variables(self) -> None:
        """Unknown variables are left as-is."""
        content = "Known: {project_name}, Unknown: {foo}"
        variables = {"project_name": "test"}

        result = resolve_template_variables(content, variables)
        assert result == "Known: test, Unknown: {foo}"

    def test_with_context_populates_defaults(self) -> None:
        """Context provides default values for variables."""
        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/my-project",
            name="my-project",
        )
        content = "Working on {project_name} ({project_type})"

        result = resolve_template_variables(content, context=context)
        assert result == "Working on my-project (python)"

    def test_override_variables_take_precedence(self) -> None:
        """Explicit variables override context-derived ones."""
        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/original",
            name="original",
        )
        content = "{project_name}"
        variables = {"project_name": "overridden"}

        result = resolve_template_variables(content, variables, context)
        assert result == "overridden"

    def test_empty_content(self) -> None:
        """Empty content returns empty string."""
        result = resolve_template_variables("")
        assert result == ""

    def test_no_variables_in_content(self) -> None:
        """Content without variables is returned unchanged."""
        content = "Plain text without variables"
        result = resolve_template_variables(content)
        assert result == content


class TestLoadPromptFile:
    """Tests for load_prompt_file function."""

    def test_loads_existing_file(self, tmp_path: Path) -> None:
        """Successfully loads content from existing file."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Custom prompt content")

        result = load_prompt_file(str(prompt_file))
        assert result == "Custom prompt content"

    def test_expands_home_directory(self, tmp_path: Path) -> None:
        """Expands ~ to home directory."""
        # Create a file in a temp directory that we'll pretend is home
        prompt_file = tmp_path / ".config" / "chapgent" / "prompt.md"
        prompt_file.parent.mkdir(parents=True)
        prompt_file.write_text("Home prompt")

        # Use the full path with ~ substitution
        with patch.object(Path, "expanduser", lambda self: Path(str(self).replace("~", str(tmp_path)))):
            result = load_prompt_file("~/.config/chapgent/prompt.md")
            assert result == "Home prompt"

    def test_raises_for_nonexistent_file(self) -> None:
        """Raises PromptLoadError for missing file."""
        with pytest.raises(PromptLoadError) as exc_info:
            load_prompt_file("/nonexistent/path/prompt.md")

        assert "not found" in str(exc_info.value)

    def test_raises_for_directory(self, tmp_path: Path) -> None:
        """Raises PromptLoadError when path is a directory."""
        with pytest.raises(PromptLoadError) as exc_info:
            load_prompt_file(str(tmp_path))

        assert "not a file" in str(exc_info.value)

    def test_handles_utf8_content(self, tmp_path: Path) -> None:
        """Correctly reads UTF-8 encoded content."""
        prompt_file = tmp_path / "prompt.md"
        content = "Unicode: \u4e2d\u6587 \U0001f600 \xe9\xe8\xe0"
        prompt_file.write_text(content, encoding="utf-8")

        result = load_prompt_file(str(prompt_file))
        assert result == content

    def test_raises_for_read_error(self, tmp_path: Path) -> None:
        """Raises PromptLoadError when file cannot be read."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("content")

        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            with pytest.raises(PromptLoadError) as exc_info:
                load_prompt_file(str(prompt_file))

            assert "Cannot read" in str(exc_info.value)


class TestGetEffectivePrompt:
    """Tests for get_effective_prompt function."""

    def test_default_settings_returns_base_prompt(self) -> None:
        """With default settings, returns DEFAULT_SYSTEM_PROMPT."""
        settings = SystemPromptSettings()
        result = get_effective_prompt(settings)
        assert result == DEFAULT_SYSTEM_PROMPT

    def test_content_in_append_mode(self) -> None:
        """Content is appended to base prompt in append mode."""
        settings = SystemPromptSettings(
            content="Custom addition",
            mode="append",
        )
        result = get_effective_prompt(settings)

        assert result.startswith(DEFAULT_SYSTEM_PROMPT)
        assert "Custom addition" in result

    def test_content_in_replace_mode(self) -> None:
        """Content replaces base prompt in replace mode."""
        settings = SystemPromptSettings(
            content="Completely custom prompt",
            mode="replace",
        )
        result = get_effective_prompt(settings)

        assert result == "Completely custom prompt"
        assert DEFAULT_SYSTEM_PROMPT not in result

    def test_file_loading(self, tmp_path: Path) -> None:
        """Loads prompt from file when specified."""
        prompt_file = tmp_path / "custom.md"
        prompt_file.write_text("File-based prompt")

        settings = SystemPromptSettings(
            file=str(prompt_file),
            mode="replace",
        )
        result = get_effective_prompt(settings)

        assert result == "File-based prompt"

    def test_file_in_append_mode(self, tmp_path: Path) -> None:
        """File content is appended in append mode."""
        prompt_file = tmp_path / "custom.md"
        prompt_file.write_text("From file")

        settings = SystemPromptSettings(
            file=str(prompt_file),
            mode="append",
        )
        result = get_effective_prompt(settings)

        assert result.startswith(DEFAULT_SYSTEM_PROMPT)
        assert "From file" in result

    def test_file_takes_precedence_over_content(self, tmp_path: Path) -> None:
        """When both file and content are set, file wins."""
        prompt_file = tmp_path / "custom.md"
        prompt_file.write_text("File content")

        settings = SystemPromptSettings(
            file=str(prompt_file),
            content="Content field",
            mode="replace",
        )
        result = get_effective_prompt(settings)

        assert result == "File content"
        assert "Content field" not in result

    def test_append_field_added_to_result(self) -> None:
        """Append field is added after content/base prompt."""
        settings = SystemPromptSettings(
            content="Main content",
            append="Additional info",
            mode="replace",
        )
        result = get_effective_prompt(settings)

        assert "Main content" in result
        assert "Additional info" in result
        assert result.index("Main content") < result.index("Additional info")

    def test_append_combined_with_file(self, tmp_path: Path) -> None:
        """Append works with file-based prompts."""
        prompt_file = tmp_path / "base.md"
        prompt_file.write_text("Base from file")

        settings = SystemPromptSettings(
            file=str(prompt_file),
            append="Extra context",
            mode="replace",
        )
        result = get_effective_prompt(settings)

        assert "Base from file" in result
        assert "Extra context" in result

    def test_template_variables_resolved(self) -> None:
        """Template variables in content are resolved."""
        settings = SystemPromptSettings(
            content="Project: {project_name}, OS: {os}",
            mode="replace",
        )

        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/test",
            name="test-project",
        )

        result = get_effective_prompt(settings, context)

        assert "test-project" in result
        assert platform.system() in result
        assert "{project_name}" not in result

    def test_additional_variables_applied(self) -> None:
        """Additional variables can be passed for resolution."""
        settings = SystemPromptSettings(
            content="Custom: {custom_var}",
            mode="replace",
        )

        result = get_effective_prompt(settings, additional_variables={"custom_var": "my_value"})

        assert result == "Custom: my_value"

    def test_raises_for_missing_file(self) -> None:
        """Raises PromptLoadError when file doesn't exist."""
        settings = SystemPromptSettings(
            file="/nonexistent/prompt.md",
        )

        with pytest.raises(PromptLoadError):
            get_effective_prompt(settings)


class TestBuildFullSystemPrompt:
    """Tests for build_full_system_prompt function."""

    def test_without_context_returns_effective_prompt(self) -> None:
        """Without context, returns effective prompt without injection."""
        settings = SystemPromptSettings(
            content="My prompt",
            mode="replace",
        )

        result = build_full_system_prompt(settings)
        assert result == "My prompt"

    def test_with_context_injects_project_info(self) -> None:
        """With context, injects project information."""
        settings = SystemPromptSettings()
        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/my-project",
            name="my-project",
            version="1.0.0",
            dependencies=["click", "pytest"],
            test_framework=TestFramework.PYTEST,
        )

        result = build_full_system_prompt(settings, context)

        assert "Project Context" in result
        assert "Python" in result
        assert "my-project" in result
        assert "1.0.0" in result
        assert "click" in result or "pytest" in result

    def test_combines_customization_with_context(self) -> None:
        """User customization and context injection work together."""
        settings = SystemPromptSettings(
            append="Always write tests first (TDD).",
        )
        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/test",
            name="test",
        )

        result = build_full_system_prompt(settings, context)

        # Has base prompt
        assert "coding assistant" in result.lower() or "helpful" in result.lower()
        # Has user customization
        assert "TDD" in result
        # Has context
        assert "Project Context" in result

    def test_template_variables_resolved_before_context(self) -> None:
        """Template variables are resolved in the base prompt."""
        settings = SystemPromptSettings(
            content="Working on {project_name}",
            mode="replace",
        )
        context = ProjectContext(
            type=ProjectType.NODE,
            root="/my-app",
            name="my-app",
        )

        result = build_full_system_prompt(settings, context)

        assert "Working on my-app" in result
        assert "{project_name}" not in result


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50)
    def test_resolve_preserves_non_variable_text(self, text: str) -> None:
        """Text without {} is preserved unchanged."""
        # Remove any accidental braces
        clean_text = text.replace("{", "").replace("}", "")
        result = resolve_template_variables(clean_text)
        assert result == clean_text

    @given(
        st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=50)
    def test_custom_variable_resolution(self, var_name: str, var_value: str) -> None:
        """Custom variables are correctly resolved."""
        content = f"Value: {{{var_name}}}"
        variables = {var_name: var_value}

        result = resolve_template_variables(content, variables)
        assert result == f"Value: {var_value}"

    @given(st.sampled_from(["replace", "append"]))
    @settings(max_examples=10)
    def test_mode_affects_output(self, mode: str) -> None:
        """Mode setting changes how content is combined."""
        prompt_settings = SystemPromptSettings(
            content="Custom",
            mode=mode,  # type: ignore
        )
        result = get_effective_prompt(prompt_settings)

        if mode == "replace":
            assert result == "Custom"
        else:
            assert DEFAULT_SYSTEM_PROMPT in result
            assert "Custom" in result

    @given(
        content=st.text(min_size=1, max_size=100),
        append_text=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=30)
    def test_append_always_at_end(self, content: str, append_text: str) -> None:
        """Append text always comes after content."""
        # Filter out problematic characters
        content = content.replace("{", "").replace("}", "")
        append_text = append_text.replace("{", "").replace("}", "")

        if not content.strip() or not append_text.strip():
            return  # Skip empty strings

        # Skip if content and append are the same (they'd be at same position)
        if content == append_text:
            return

        prompt_settings = SystemPromptSettings(
            content=content,
            append=append_text,
            mode="replace",
        )
        result = get_effective_prompt(prompt_settings)

        # Both should be present
        assert content in result
        assert append_text in result

        # Append should come after content (use rfind for append to handle substrings)
        content_pos = result.find(content)
        append_pos = result.rfind(append_text)
        assert content_pos <= append_pos


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_content_string(self) -> None:
        """Empty content string uses defaults."""
        prompt_settings = SystemPromptSettings(content="")
        result = get_effective_prompt(prompt_settings)
        # Empty string is falsy, so base prompt is used
        assert result == DEFAULT_SYSTEM_PROMPT

    def test_whitespace_only_content(self) -> None:
        """Whitespace-only content is preserved in replace mode."""
        prompt_settings = SystemPromptSettings(
            content="   ",
            mode="replace",
        )
        result = get_effective_prompt(prompt_settings)
        assert result == "   "

    def test_newlines_in_content(self) -> None:
        """Multi-line content is preserved."""
        prompt_settings = SystemPromptSettings(
            content="Line 1\nLine 2\n\nLine 4",
            mode="replace",
        )
        result = get_effective_prompt(prompt_settings)
        assert result == "Line 1\nLine 2\n\nLine 4"

    def test_nested_braces(self) -> None:
        """Nested braces are handled correctly."""
        content = "{{not_a_variable}} and {project_name}"
        variables = {"project_name": "test"}

        result = resolve_template_variables(content, variables)
        # {{ should remain as is since we don't do Python format() escaping
        assert "{{not_a_variable}}" in result
        assert "test" in result

    def test_special_characters_in_file(self, tmp_path: Path) -> None:
        """File with special characters is loaded correctly."""
        prompt_file = tmp_path / "special.md"
        content = "Special: `code` *bold* _italic_ <html> $var"
        prompt_file.write_text(content)

        result = load_prompt_file(str(prompt_file))
        assert result == content

    def test_very_long_prompt(self) -> None:
        """Very long prompts are handled correctly."""
        long_content = "A" * 10000
        prompt_settings = SystemPromptSettings(
            content=long_content,
            mode="replace",
        )
        result = get_effective_prompt(prompt_settings)
        assert result == long_content
        assert len(result) == 10000


class TestDefaultSystemPrompt:
    """Tests for DEFAULT_SYSTEM_PROMPT constant."""

    def test_default_prompt_is_non_empty(self) -> None:
        """Default prompt should be non-empty."""
        assert DEFAULT_SYSTEM_PROMPT
        assert len(DEFAULT_SYSTEM_PROMPT) > 50

    def test_default_prompt_mentions_coding(self) -> None:
        """Default prompt should mention coding/assistant role."""
        lower = DEFAULT_SYSTEM_PROMPT.lower()
        assert "coding" in lower or "code" in lower
        assert "assistant" in lower or "help" in lower

    def test_default_prompt_is_string(self) -> None:
        """Default prompt should be a string."""
        assert isinstance(DEFAULT_SYSTEM_PROMPT, str)


class TestIntegration:
    """Integration tests for the complete prompt flow."""

    def test_full_flow_with_file_and_context(self, tmp_path: Path) -> None:
        """Complete flow with file, context, and template variables."""
        # Create prompt file
        prompt_file = tmp_path / "custom.md"
        prompt_file.write_text("Working on {project_name} ({project_type})\nBranch: {git_branch}")

        prompt_settings = SystemPromptSettings(
            file=str(prompt_file),
            append="Remember to write tests!",
            mode="replace",
        )

        context = ProjectContext(
            type=ProjectType.PYTHON,
            root="/my-project",
            name="my-project",
            git_info=GitInfo(branch="feature/test"),
            test_framework=TestFramework.PYTEST,
        )

        result = build_full_system_prompt(prompt_settings, context)

        # Template variables resolved
        assert "my-project" in result
        assert "python" in result
        assert "feature/test" in result

        # Append added
        assert "Remember to write tests!" in result

        # Context injected
        assert "Project Context" in result

    def test_default_settings_with_context(self) -> None:
        """Default settings still get context injection."""
        prompt_settings = SystemPromptSettings()
        context = ProjectContext(
            type=ProjectType.NODE,
            root="/frontend",
            name="frontend",
            dependencies=["react", "typescript"],
        )

        result = build_full_system_prompt(prompt_settings, context)

        # Base prompt present
        assert DEFAULT_SYSTEM_PROMPT in result

        # Context injected
        assert "Node" in result
        assert "frontend" in result
