"""Tests for UX CLI commands (help, setup)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from pygent.cli import cli


class TestHelpCommand:
    """Tests for 'pygent help' command."""

    def test_help_no_args_lists_topics(self) -> None:
        """'pygent help' should list all topics."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help"])

        assert result.exit_code == 0
        assert "Help Topics" in result.output
        assert "tools" in result.output
        assert "config" in result.output
        assert "shortcuts" in result.output

    def test_help_tools_topic(self) -> None:
        """'pygent help tools' should show tools help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "tools"])

        assert result.exit_code == 0
        assert "Tools" in result.output or "tools" in result.output
        assert "read_file" in result.output or "FILESYSTEM" in result.output

    def test_help_config_topic(self) -> None:
        """'pygent help config' should show config help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "config"])

        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_help_shortcuts_topic(self) -> None:
        """'pygent help shortcuts' should show shortcuts help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "shortcuts"])

        assert result.exit_code == 0
        assert "Ctrl" in result.output or "ctrl" in result.output

    def test_help_permissions_topic(self) -> None:
        """'pygent help permissions' should show permissions help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "permissions"])

        assert result.exit_code == 0
        assert "permission" in result.output.lower() or "risk" in result.output.lower()

    def test_help_sessions_topic(self) -> None:
        """'pygent help sessions' should show sessions help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "sessions"])

        assert result.exit_code == 0
        assert "session" in result.output.lower()

    def test_help_prompts_topic(self) -> None:
        """'pygent help prompts' should show prompts help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "prompts"])

        assert result.exit_code == 0
        assert "prompt" in result.output.lower()

    def test_help_quickstart_topic(self) -> None:
        """'pygent help quickstart' should show quickstart guide."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "quickstart"])

        assert result.exit_code == 0
        assert "start" in result.output.lower() or "chat" in result.output.lower()

    def test_help_troubleshooting_topic(self) -> None:
        """'pygent help troubleshooting' should show troubleshooting guide."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "troubleshooting"])

        assert result.exit_code == 0
        assert "issue" in result.output.lower() or "error" in result.output.lower()

    def test_help_invalid_topic(self) -> None:
        """'pygent help invalid' should show error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "nonexistent_topic"])

        assert result.exit_code != 0
        assert "Unknown help topic" in result.output or "Error" in result.output

    def test_help_case_insensitive(self) -> None:
        """Help topics should be case-insensitive."""
        runner = CliRunner()

        result1 = runner.invoke(cli, ["help", "TOOLS"])
        result2 = runner.invoke(cli, ["help", "Tools"])
        result3 = runner.invoke(cli, ["help", "tools"])

        # All should succeed
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert result3.exit_code == 0


class TestSetupCommand:
    """Tests for 'pygent setup' command."""

    def test_setup_shows_welcome(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'pygent setup' should show welcome message."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["setup"], input="n\nn\n")

        assert result.exit_code == 0
        assert "Welcome" in result.output or "welcome" in result.output

    def test_setup_already_configured(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """'pygent setup' should detect already configured state."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        # Create config file
        config_path = tmp_path / ".config" / "pygent" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("[llm]\nmodel = 'test'")

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["setup"])

        assert result.exit_code == 0
        assert "already set up" in result.output or "configured" in result.output.lower()

    def test_setup_asks_about_api_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'pygent setup' should ask about API key when missing."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            # Decline API key setup
            result = runner.invoke(cli, ["setup"], input="n\nn\n")

        assert result.exit_code == 0
        # Should ask about API key
        assert "API" in result.output

    def test_setup_creates_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'pygent setup' should offer to create config file."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            # Accept config creation
            result = runner.invoke(cli, ["setup"], input="y\n")

        assert result.exit_code == 0
        # Config should be created
        config_path = tmp_path / ".config" / "pygent" / "config.toml"
        assert config_path.exists()

    def test_setup_validates_api_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'pygent setup' should validate API key format."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            # Enter a short/invalid key and decline to continue
            result = runner.invoke(cli, ["setup"], input="y\nabc\nn\n")

        assert result.exit_code == 0
        # Should show warning about short key
        assert "Warning" in result.output or "short" in result.output.lower() or "cancelled" in result.output.lower()


class TestHelpCommandOutput:
    """Tests for help command output formatting."""

    def test_help_output_has_separators(self) -> None:
        """Help output should have visual separators."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", "tools"])

        assert result.exit_code == 0
        assert "=" in result.output or "-" in result.output

    def test_help_list_is_formatted(self) -> None:
        """Help topic list should be nicely formatted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help"])

        assert result.exit_code == 0
        # Should have consistent spacing
        lines = result.output.strip().split("\n")
        # Should have multiple lines
        assert len(lines) > 5


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))))
    @settings(max_examples=30)
    def test_help_with_random_topic(self, topic: str) -> None:
        """'pygent help' should handle random topic names gracefully."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", topic])

        # Should either succeed or fail with helpful error
        assert isinstance(result.output, str)
        if result.exit_code != 0:
            assert "Unknown" in result.output or "Error" in result.output


class TestEdgeCases:
    """Edge case tests."""

    def test_help_empty_topic(self) -> None:
        """'pygent help \"\"' should handle empty string."""
        runner = CliRunner()
        result = runner.invoke(cli, ["help", ""])

        # Should fail gracefully
        assert result.exit_code != 0

    def test_setup_noninteractive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'pygent setup' should work with automatic 'no' responses."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["setup"], input="n\nn\n")

        assert result.exit_code == 0


class TestIntegration:
    """Integration tests."""

    def test_help_then_setup_flow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test running help then setup."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        runner = CliRunner()

        # First check help
        help_result = runner.invoke(cli, ["help", "quickstart"])
        assert help_result.exit_code == 0

        # Then run setup
        with patch.object(Path, "home", return_value=tmp_path):
            setup_result = runner.invoke(cli, ["setup"], input="n\nn\n")

        assert setup_result.exit_code == 0

    def test_all_help_topics_work(self) -> None:
        """All documented help topics should work."""
        from pygent.ux.help import get_topic_names

        runner = CliRunner()

        for topic in get_topic_names():
            result = runner.invoke(cli, ["help", topic])
            assert result.exit_code == 0, f"Help topic '{topic}' failed"
            assert len(result.output) > 100, f"Help topic '{topic}' has too little content"
