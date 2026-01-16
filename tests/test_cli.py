from datetime import datetime
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from pygent.cli import cli
from pygent.session.models import SessionSummary


def test_cli_structure():
    """Test that the CLI has the expected structure."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Pygent - AI-powered coding agent" in result.output
    assert "chat" in result.output
    assert "sessions" in result.output
    assert "resume" in result.output
    assert "config" in result.output


@patch("pygent.cli.PygentApp")
@patch("pygent.cli.Agent")
@patch("pygent.cli.LLMProvider")
@patch("pygent.cli.ToolRegistry")
@patch("pygent.cli.SessionStorage")
@patch("pygent.cli.PermissionManager")
def test_cli_chat_startup(mock_permissions, mock_storage, mock_registry, mock_provider, mock_agent, mock_app):
    """Test that the chat command initializes components and starts the app."""
    runner = CliRunner()

    # Run the chat command
    result = runner.invoke(cli, ["chat"])

    if result.exit_code != 0:
        print(result.output)

    assert result.exit_code == 0

    # Verify initialization
    mock_provider.assert_called()
    mock_registry.assert_called()
    mock_storage.assert_called()
    mock_permissions.assert_called()

    # Verify Agent initialization
    mock_agent.assert_called()

    # Verify App initialization and run
    mock_app.assert_called()
    mock_app.return_value.run.assert_called()


class TestSessionsCommand:
    """Tests for the sessions CLI command."""

    @patch("pygent.cli.SessionStorage")
    def test_sessions_empty(self, mock_storage_class):
        """Test sessions command when no sessions exist."""
        mock_storage = mock_storage_class.return_value
        mock_storage.list_sessions = AsyncMock(return_value=[])

        runner = CliRunner()
        result = runner.invoke(cli, ["sessions"])

        assert result.exit_code == 0
        assert "No sessions found" in result.output

    @patch("pygent.cli.SessionStorage")
    def test_sessions_list(self, mock_storage_class):
        """Test sessions command lists sessions with proper formatting."""
        mock_storage = mock_storage_class.return_value
        mock_storage.list_sessions = AsyncMock(
            return_value=[
                SessionSummary(
                    id="abc123",
                    created_at=datetime(2026, 1, 16, 10, 0, 0),
                    updated_at=datetime(2026, 1, 16, 12, 0, 0),
                    message_count=5,
                    working_directory="/home/user/project",
                    metadata={},
                ),
                SessionSummary(
                    id="def456",
                    created_at=datetime(2026, 1, 15, 9, 0, 0),
                    updated_at=datetime(2026, 1, 15, 11, 0, 0),
                    message_count=10,
                    working_directory="/home/user/other",
                    metadata={},
                ),
            ]
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["sessions"])

        assert result.exit_code == 0
        assert "abc123" in result.output
        assert "def456" in result.output
        assert "5" in result.output  # message count
        assert "10" in result.output  # message count


class TestResumeCommand:
    """Tests for the resume CLI command."""

    @patch("pygent.cli.PygentApp")
    @patch("pygent.cli.Agent")
    @patch("pygent.cli.LLMProvider")
    @patch("pygent.cli.ToolRegistry")
    @patch("pygent.cli.SessionStorage")
    @patch("pygent.cli.PermissionManager")
    def test_resume_session_found(
        self, mock_permissions, mock_storage_class, mock_registry, mock_provider, mock_agent, mock_app
    ):
        """Test resume command when session exists."""
        from pygent.session.models import Session

        mock_storage = mock_storage_class.return_value
        mock_storage.load = AsyncMock(
            return_value=Session(
                id="abc123",
                working_directory="/home/user/project",
                messages=[],
                tool_history=[],
            )
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "abc123"])

        assert result.exit_code == 0
        mock_storage.load.assert_called_with("abc123")
        mock_app.return_value.run.assert_called()

    @patch("pygent.cli.SessionStorage")
    def test_resume_session_not_found(self, mock_storage_class):
        """Test resume command when session doesn't exist."""
        mock_storage = mock_storage_class.return_value
        mock_storage.load = AsyncMock(return_value=None)

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestConfigCommand:
    """Tests for the config CLI command."""

    @patch("pygent.cli.load_config")
    def test_config_show(self, mock_load_config):
        """Test config command displays current configuration."""
        from pygent.config.settings import Settings

        mock_load_config.return_value = Settings()

        runner = CliRunner()
        result = runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        # Should show config keys
        assert "llm" in result.output.lower() or "model" in result.output.lower()


@patch("pygent.cli.PygentApp")
@patch("pygent.cli.Agent")
@patch("pygent.cli.LLMProvider")
@patch("pygent.cli.ToolRegistry")
@patch("pygent.cli.SessionStorage")
@patch("pygent.cli.PermissionManager")
def test_cli_resume_not_found_raises(
    mock_permissions, mock_storage_class, mock_registry, mock_provider, mock_agent, mock_app
):
    """Test resume command when session doesn't exist raises ClickException."""
    mock_storage = mock_storage_class.return_value
    mock_storage.load = AsyncMock(return_value=None)

    runner = CliRunner()
    result = runner.invoke(cli, ["resume", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
