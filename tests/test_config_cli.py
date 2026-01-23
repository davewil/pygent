"""Tests for the config CLI commands.

Note: Helper function tests (convert_value, format_toml_value, etc.)
have been moved to test_config_writer.py. This file focuses on CLI behavior.
"""

import sys
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.cli import cli
from chapgent.config.writer import (
    format_toml_value,
)


class TestConfigPathCommand:
    """Tests for 'config path' command."""

    def test_shows_user_config_path(self, tmp_path, monkeypatch):
        """Test displays user config path."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "path"])

        assert result.exit_code == 0
        assert "User config:" in result.output
        assert "config.toml" in result.output

    def test_shows_project_config_path(self, tmp_path, monkeypatch):
        """Test displays project config path."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "path"])

        assert result.exit_code == 0
        assert "Project config:" in result.output
        assert ".chapgent" in result.output

    def test_shows_exists_status(self, tmp_path, monkeypatch):
        """Test shows [exists] when config files exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create user config
        user_config = tmp_path / ".config" / "chapgent" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("[llm]\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "path"])

        assert "[exists]" in result.output

    def test_shows_not_found_status(self, tmp_path, monkeypatch):
        """Test shows [not found] when config files don't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "path"])

        assert "[not found]" in result.output

    def test_shows_priority_info(self):
        """Test shows priority information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "path"])

        assert result.exit_code == 0
        assert "Priority" in result.output
        assert "Environment variables" in result.output


class TestConfigInitCommand:
    """Tests for 'config init' command."""

    def test_creates_user_config(self, tmp_path, monkeypatch):
        """Test creates user config file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "init"])

        assert result.exit_code == 0
        assert "Created user config" in result.output

        user_config = tmp_path / ".config" / "chapgent" / "config.toml"
        assert user_config.exists()

    def test_creates_project_config_with_flag(self, tmp_path, monkeypatch):
        """Test --project flag creates project config."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "init", "--project"])

        assert result.exit_code == 0
        assert "Created project config" in result.output

        project_config = tmp_path / ".chapgent" / "config.toml"
        assert project_config.exists()

    def test_fails_if_exists_without_force(self, tmp_path, monkeypatch):
        """Test fails if config already exists."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create existing config
        user_config = tmp_path / ".config" / "chapgent" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("existing content")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "init"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_force_overwrites_existing(self, tmp_path, monkeypatch):
        """Test --force overwrites existing config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create existing config
        user_config = tmp_path / ".config" / "chapgent" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("old content")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "init", "--force"])

        assert result.exit_code == 0
        assert "Created user config" in result.output

        # Should have new default content
        content = user_config.read_text()
        assert "old content" not in content
        assert "[llm]" in content


class TestConfigEditCommand:
    """Tests for 'config edit' command."""

    def test_opens_editor(self, tmp_path, monkeypatch):
        """Test opens editor with config file."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("EDITOR", "echo")  # echo will just print the path

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "edit"])

        assert result.exit_code == 0

    def test_creates_config_if_not_exists(self, tmp_path, monkeypatch):
        """Test creates config file before editing."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("EDITOR", "echo")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "edit"])

        assert result.exit_code == 0
        assert "Created" in result.output

        user_config = tmp_path / ".config" / "chapgent" / "config.toml"
        assert user_config.exists()

    def test_project_flag_edits_project_config(self, tmp_path, monkeypatch):
        """Test --project flag edits project config."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EDITOR", "echo")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "edit", "--project"])

        assert result.exit_code == 0

        project_config = tmp_path / ".chapgent" / "config.toml"
        assert project_config.exists()

    def test_editor_not_found_error(self, tmp_path, monkeypatch):
        """Test error when editor not found."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("EDITOR", "nonexistent_editor_12345")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "edit"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_uses_visual_fallback(self, tmp_path, monkeypatch):
        """Test falls back to VISUAL if EDITOR not set."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("EDITOR", raising=False)
        monkeypatch.setenv("VISUAL", "echo")

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "edit"])

        assert result.exit_code == 0


class TestConfigSetCommand:
    """Tests for 'config set' command."""

    def test_sets_string_value(self, tmp_path, monkeypatch):
        """Test setting a string value."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "llm.model", "claude-3-5-haiku"])

        assert result.exit_code == 0
        assert "Set llm.model = claude-3-5-haiku" in result.output

        # Verify file was created and has correct value
        config_path = tmp_path / ".config" / "chapgent" / "config.toml"
        assert config_path.exists()

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        assert data["llm"]["model"] == "claude-3-5-haiku"

    def test_sets_integer_value(self, tmp_path, monkeypatch):
        """Test setting an integer value."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "llm.max_output_tokens", "8192"])

        assert result.exit_code == 0
        assert "Set llm.max_output_tokens = 8192" in result.output

    def test_sets_boolean_value(self, tmp_path, monkeypatch):
        """Test setting a boolean value."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "tui.show_tool_panel", "false"])

        assert result.exit_code == 0
        assert "Set tui.show_tool_panel = False" in result.output

    def test_invalid_key_fails(self, tmp_path, monkeypatch):
        """Test invalid config key fails with error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "invalid.key", "value"])

        assert result.exit_code == 1
        assert "Invalid config key" in result.output

    def test_project_flag_sets_project_config(self, tmp_path, monkeypatch):
        """Test --project flag sets in project config."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "llm.model", "test", "--project"])

        assert result.exit_code == 0
        assert "project config" in result.output

        project_config = tmp_path / ".chapgent" / "config.toml"
        assert project_config.exists()

    def test_preserves_existing_values(self, tmp_path, monkeypatch):
        """Test setting value preserves other existing values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create existing config
        config_path = tmp_path / ".config" / "chapgent" / "config.toml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text('[llm]\nmodel = "existing"\n')

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "llm.max_output_tokens", "8192"])

        assert result.exit_code == 0

        # Read back and verify both values exist
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        assert data["llm"]["model"] == "existing"
        assert data["llm"]["max_output_tokens"] == 8192


class TestConfigShowCommand:
    """Tests for 'config show' command."""

    @patch("chapgent.cli.config.load_config")
    def test_shows_all_settings(self, mock_load_config):
        """Test shows all configuration settings."""
        from chapgent.config.settings import Settings

        mock_load_config.return_value = Settings()

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "LLM" in result.output
        assert "Permissions" in result.output
        assert "TUI" in result.output

    @patch("chapgent.cli.config.load_config")
    def test_shows_custom_values(self, mock_load_config):
        """Test shows custom configuration values."""
        from chapgent.config.settings import LLMSettings, Settings

        mock_load_config.return_value = Settings(llm=LLMSettings(model="custom-model", max_output_tokens=8192))

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "custom-model" in result.output
        assert "8192" in result.output


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(alphabet=st.characters(codec="utf-8", categories=["L", "N", "P", "S"]), min_size=0, max_size=50))
    @settings(max_examples=50)
    def test_format_toml_value_roundtrip(self, value):
        """Test formatting then parsing gives back original value."""
        formatted = format_toml_value(value)

        # Should be a valid TOML string
        assert formatted.startswith('"')
        assert formatted.endswith('"')

        # The value should be recoverable (basic check)
        # Unquote and unescape
        inner = formatted[1:-1]
        unescaped = inner.replace('\\"', '"').replace("\\\\", "\\")
        assert unescaped == value

    @given(st.integers(min_value=0, max_value=100000))
    def test_format_toml_value_integer(self, value):
        """Test integer formatting."""
        formatted = format_toml_value(value)
        assert formatted == str(value)

    @given(st.booleans())
    def test_format_toml_value_boolean(self, value):
        """Test boolean formatting."""
        formatted = format_toml_value(value)
        assert formatted == ("true" if value else "false")


class TestEdgeCases:
    """Edge case tests."""

    def test_set_empty_string_value(self, tmp_path, monkeypatch):
        """Test setting an empty string value."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "llm.model", ""])

        assert result.exit_code == 0

    def test_set_value_with_spaces(self, tmp_path, monkeypatch):
        """Test setting a value containing spaces."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "system_prompt.content", "hello world"])

        assert result.exit_code == 0
        assert "hello world" in result.output

    def test_set_value_with_special_chars(self, tmp_path, monkeypatch):
        """Test setting a value with special characters."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "system_prompt.content", "path/to/file"])

        assert result.exit_code == 0

    def test_config_help_shows_all_subcommands(self):
        """Test config --help lists all subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "show" in result.output
        assert "path" in result.output
        assert "edit" in result.output
        assert "init" in result.output
        assert "set" in result.output

    def test_config_set_help_shows_examples(self):
        """Test 'config set --help' shows usage examples."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "--help"])

        assert result.exit_code == 0
        assert "KEY" in result.output
        assert "VALUE" in result.output


class TestIntegration:
    """Integration tests for config CLI commands."""

    def test_init_then_set_then_show(self, tmp_path, monkeypatch):
        """Test full workflow: init, set value, show config."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()

        # Init
        result = runner.invoke(cli, ["config", "init"])
        assert result.exit_code == 0

        # Set value
        result = runner.invoke(cli, ["config", "set", "llm.model", "test-model"])
        assert result.exit_code == 0

        # Show
        with patch("chapgent.cli.config.load_config") as mock_load:
            from chapgent.config.settings import LLMSettings, Settings

            mock_load.return_value = Settings(llm=LLMSettings(model="test-model"))
            result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "test-model" in result.output

    def test_multiple_sets_accumulate(self, tmp_path, monkeypatch):
        """Test multiple set commands accumulate values."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        runner = CliRunner()

        # Set multiple values
        runner.invoke(cli, ["config", "set", "llm.model", "model1"])
        runner.invoke(cli, ["config", "set", "llm.max_output_tokens", "8192"])
        runner.invoke(cli, ["config", "set", "tui.theme", "dark"])

        # Read back
        config_path = tmp_path / ".config" / "chapgent" / "config.toml"

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        assert data["llm"]["model"] == "model1"
        assert data["llm"]["max_output_tokens"] == 8192
        assert data["tui"]["theme"] == "dark"
