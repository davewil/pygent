from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from chapgent.cli import cli
from chapgent.session.models import SessionSummary


def test_cli_structure():
    """Test that the CLI has the expected structure."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Chapgent - AI-powered coding agent" in result.output
    assert "chat" in result.output
    assert "sessions" in result.output
    assert "resume" in result.output
    assert "config" in result.output


@patch("chapgent.cli.bootstrap.ChapgentApp")
@patch("chapgent.cli.bootstrap.Agent")
@patch("chapgent.cli.bootstrap.LLMProvider")
@patch("chapgent.cli.bootstrap.ToolRegistry")
@patch("chapgent.cli.bootstrap.SessionStorage")
@patch("chapgent.cli.bootstrap.PermissionManager")
@patch("chapgent.cli.bootstrap.load_config")
def test_cli_chat_startup(
    mock_load_config, mock_permissions, mock_storage, mock_registry, mock_provider, mock_agent, mock_app
):
    """Test that the chat command initializes components and starts the app."""
    from chapgent.config.settings import LLMSettings, Settings

    # Mock config with API key to pass validation
    mock_load_config.return_value = Settings(llm=LLMSettings(api_key="test-key"))

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

    @patch("chapgent.cli.main.SessionStorage")
    def test_sessions_empty(self, mock_storage_class):
        """Test sessions command when no sessions exist."""
        mock_storage = mock_storage_class.return_value
        mock_storage.list_sessions = AsyncMock(return_value=[])

        runner = CliRunner()
        result = runner.invoke(cli, ["sessions"])

        assert result.exit_code == 0
        assert "No sessions found" in result.output

    @patch("chapgent.cli.main.SessionStorage")
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

    @patch("chapgent.cli.bootstrap.ChapgentApp")
    @patch("chapgent.cli.bootstrap.Agent")
    @patch("chapgent.cli.bootstrap.LLMProvider")
    @patch("chapgent.cli.bootstrap.ToolRegistry")
    @patch("chapgent.cli.bootstrap.SessionStorage")
    @patch("chapgent.cli.bootstrap.PermissionManager")
    @patch("chapgent.cli.bootstrap.load_config")
    def test_resume_session_found(
        self, mock_load_config, mock_permissions, mock_storage_class, mock_registry, mock_provider, mock_agent, mock_app
    ):
        """Test resume command when session exists."""
        from chapgent.config.settings import LLMSettings, Settings
        from chapgent.session.models import Session

        # Mock config with API key (not OAuth)
        mock_load_config.return_value = Settings(llm=LLMSettings(api_key="test-key"))

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

    @patch("chapgent.cli.bootstrap.load_config")
    @patch("chapgent.cli.bootstrap.SessionStorage")
    def test_resume_session_not_found(self, mock_storage_class, mock_load_config):
        """Test resume command when session doesn't exist."""
        from chapgent.config.settings import LLMSettings, Settings

        mock_load_config.return_value = Settings(llm=LLMSettings(api_key="test-key"))

        mock_storage = mock_storage_class.return_value
        mock_storage.load = AsyncMock(return_value=None)

        runner = CliRunner()
        result = runner.invoke(cli, ["resume", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestConfigCommand:
    """Tests for the config CLI command group."""

    def test_config_is_group(self):
        """Test config is a command group with subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "Manage configuration" in result.output
        assert "show" in result.output
        assert "path" in result.output
        assert "edit" in result.output
        assert "init" in result.output
        assert "set" in result.output

    @patch("chapgent.cli.config.load_config")
    def test_config_show(self, mock_load_config):
        """Test config show command displays current configuration."""
        from chapgent.config.settings import Settings

        mock_load_config.return_value = Settings()

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        # Should show config keys
        assert "llm" in result.output.lower() or "model" in result.output.lower()


@patch("chapgent.cli.bootstrap.ChapgentApp")
@patch("chapgent.cli.bootstrap.Agent")
@patch("chapgent.cli.bootstrap.LLMProvider")
@patch("chapgent.cli.bootstrap.ToolRegistry")
@patch("chapgent.cli.bootstrap.SessionStorage")
@patch("chapgent.cli.bootstrap.PermissionManager")
@patch("chapgent.cli.bootstrap.load_config")
def test_cli_resume_not_found_raises(
    mock_load_config, mock_permissions, mock_storage_class, mock_registry, mock_provider, mock_agent, mock_app
):
    """Test resume command when session doesn't exist raises ClickException."""
    from chapgent.config.settings import LLMSettings, Settings

    mock_load_config.return_value = Settings(llm=LLMSettings(api_key="test-key"))

    mock_storage = mock_storage_class.return_value
    mock_storage.load = AsyncMock(return_value=None)

    runner = CliRunner()
    result = runner.invoke(cli, ["resume", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


class TestToolsCommand:
    """Tests for the tools CLI command."""

    def test_tools_list_all(self):
        """Test listing all tools without category filter."""
        runner = CliRunner()
        result = runner.invoke(cli, ["tools"])

        assert result.exit_code == 0
        # Should show category headers
        assert "Filesystem Tools" in result.output
        assert "Git Tools" in result.output
        assert "Search Tools" in result.output
        assert "Shell Tools" in result.output
        assert "Web Tools" in result.output
        # Should show some tools
        assert "read_file" in result.output
        assert "git_status" in result.output
        assert "grep_search" in result.output
        assert "shell" in result.output
        assert "web_fetch" in result.output

    def test_tools_filter_by_category_git(self):
        """Test filtering tools by git category."""
        runner = CliRunner()
        result = runner.invoke(cli, ["tools", "--category", "git"])

        assert result.exit_code == 0
        assert "Git Tools" in result.output
        assert "git_status" in result.output
        assert "git_diff" in result.output
        assert "git_commit" in result.output
        # Should NOT show other categories
        assert "Filesystem Tools" not in result.output
        assert "read_file" not in result.output

    def test_tools_filter_by_category_filesystem(self):
        """Test filtering tools by filesystem category."""
        runner = CliRunner()
        result = runner.invoke(cli, ["tools", "-c", "filesystem"])

        assert result.exit_code == 0
        assert "Filesystem Tools" in result.output
        assert "read_file" in result.output
        assert "edit_file" in result.output
        # Should NOT show git tools
        assert "Git Tools" not in result.output
        assert "git_status" not in result.output

    def test_tools_invalid_category(self):
        """Test that invalid category raises error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["tools", "--category", "invalid"])

        assert result.exit_code == 1
        assert "Invalid category" in result.output

    def test_tools_shows_risk_levels(self):
        """Test that risk levels are displayed."""
        runner = CliRunner()
        result = runner.invoke(cli, ["tools"])

        assert result.exit_code == 0
        assert "[LOW]" in result.output
        assert "[MEDIUM]" in result.output
        assert "[HIGH]" in result.output

    def test_tools_command_in_help(self):
        """Test that tools command is listed in help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "tools" in result.output


# =============================================================================
# Test Auth Commands
# =============================================================================


class TestAuthCommands:
    """Tests for chapgent auth commands."""

    def test_auth_is_group(self):
        """Test auth is a command group with subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert "login" in result.output
        assert "logout" in result.output
        assert "status" in result.output

    def test_auth_login_shows_options(self):
        """Verify login command shows authentication options."""
        runner = CliRunner()
        # Answer "n" to manual token prompt
        result = runner.invoke(cli, ["auth", "login"], input="n\n")

        # Should mention import option
        assert "import-claude-code" in result.output or "Claude Code" in result.output

    @patch("chapgent.cli.auth.load_config")
    def test_auth_status_no_auth(self, mock_load_config):
        """Verify status shows no auth when unconfigured."""
        from chapgent.config.settings import Settings

        mock_load_config.return_value = Settings()

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        # Default mode is "api", so it should show API key not configured
        assert "API key not configured" in result.output

    @patch("chapgent.cli.auth.load_config")
    def test_auth_status_with_api_key(self, mock_load_config):
        """Verify status shows API key when configured."""
        from chapgent.config.settings import Settings

        settings = Settings()
        settings.llm.api_key = "sk-ant-test12345678901234567890"
        mock_load_config.return_value = settings

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "API key configured" in result.output

    @patch("chapgent.cli.auth.load_config")
    def test_auth_status_max_mode_shows_claude_cli_status(self, mock_load_config):
        """Verify status shows Claude Code CLI status in max mode."""
        from chapgent.config.settings import Settings

        settings = Settings()
        settings.llm.auth_mode = "max"
        mock_load_config.return_value = settings

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "Claude Max" in result.output
        # Either shows installed or not installed
        assert "Claude Code CLI" in result.output


# =============================================================================
# Test Proxy Commands
# =============================================================================


class TestProxyCommands:
    """Tests for chapgent proxy commands."""

    def test_proxy_is_group(self):
        """Test proxy is a command group with subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["proxy", "--help"])

        assert result.exit_code == 0
        assert "start" in result.output
        assert "setup" in result.output

    @patch("subprocess.run")
    def test_proxy_start_displays_instructions(self, mock_run):
        """Verify proxy start auto-configures base_url and shows instructions."""
        # Mock subprocess to raise KeyboardInterrupt immediately
        mock_run.side_effect = KeyboardInterrupt()

        runner = CliRunner()
        result = runner.invoke(cli, ["proxy", "start"])

        # Should auto-configure base_url and show proxy info before starting
        assert "Starting LiteLLM Proxy" in result.output
        assert "Configured llm.base_url" in result.output
        assert "chapgent chat" in result.output

    @patch("subprocess.run")
    def test_proxy_start_custom_port(self, mock_run):
        """Verify proxy start uses custom port."""
        mock_run.side_effect = KeyboardInterrupt()

        runner = CliRunner()
        result = runner.invoke(cli, ["proxy", "start", "--port", "8080"])

        assert "8080" in result.output

    def test_proxy_setup_help(self):
        """Verify proxy setup shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["proxy", "setup", "--help"])

        assert result.exit_code == 0
        assert "Interactive setup wizard" in result.output


# =============================================================================
# Phase 7: LiteLLM Gateway Integration Tests
# =============================================================================


class TestAuthLoginTokenStorage:
    """Tests for auth login storing tokens in config."""

    @patch("chapgent.cli.auth.save_config_value")
    def test_auth_login_with_direct_token_stores_to_config(self, mock_save):
        """Verify login with --token flag stores token in config."""
        mock_save.return_value = ("/path/to/config.toml", True)

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "login", "--token", "test-oauth-token-12345678901234567890"])

        assert result.exit_code == 0
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][0] == "llm.oauth_token"
        assert call_args[0][1] == "test-oauth-token-12345678901234567890"
        assert "OAuth token saved successfully" in result.output

    @patch("chapgent.cli.auth.save_config_value")
    def test_auth_login_import_claude_code_reads_credentials(self, mock_save, tmp_path):
        """Verify login --import-claude-code reads from Claude Code credentials."""
        mock_save.return_value = ("/path/to/config.toml", True)

        # Create mock credentials file
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text('{"accessToken": "imported-token-12345678901234567890"}')

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["auth", "login", "--import-claude-code"])

        assert result.exit_code == 0
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][0] == "llm.oauth_token"
        assert call_args[0][1] == "imported-token-12345678901234567890"

    @patch("chapgent.cli.auth.save_config_value")
    def test_auth_login_import_nested_oauth_token(self, mock_save, tmp_path):
        """Verify login reads nested claudeAiOauth.accessToken format."""
        mock_save.return_value = ("/path/to/config.toml", True)

        # Create mock credentials with nested format
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text('{"claudeAiOauth": {"accessToken": "nested-token-12345678901234567890"}}')

        runner = CliRunner()
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(cli, ["auth", "login", "--import-claude-code"])

        assert result.exit_code == 0
        call_args = mock_save.call_args
        assert call_args[0][1] == "nested-token-12345678901234567890"

    def test_auth_login_rejects_short_token(self):
        """Verify login rejects tokens shorter than 20 characters."""
        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "login", "--token", "short"])

        assert result.exit_code == 1
        assert "Invalid token format" in result.output


class TestAuthLogoutTokenRemoval:
    """Tests for auth logout removing tokens from config."""

    @patch("chapgent.cli.auth.save_config_value")
    def test_auth_logout_removes_both_tokens(self, mock_save):
        """Verify logout removes both oauth_token and api_key."""
        mock_save.return_value = ("/path/to/config.toml", True)

        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "logout"])

        assert result.exit_code == 0
        assert mock_save.call_count == 2

        # Verify both tokens are cleared
        calls = [call[0] for call in mock_save.call_args_list]
        assert ("llm.oauth_token", "", False) in calls or any(c[0] == "llm.oauth_token" and c[1] == "" for c in calls)
        assert ("llm.api_key", "", False) in calls or any(c[0] == "llm.api_key" and c[1] == "" for c in calls)
        assert "Authentication tokens removed" in result.output


class TestCLIPassesSettingsToProvider:
    """Tests that CLI correctly passes gateway settings to LLMProvider."""

    @patch("chapgent.cli.bootstrap.ChapgentApp")
    @patch("chapgent.cli.bootstrap.Agent")
    @patch("chapgent.cli.bootstrap.ACPClaudeCodeProvider")
    @patch("chapgent.cli.bootstrap.ToolRegistry")
    @patch("chapgent.cli.bootstrap.SessionStorage")
    @patch("chapgent.cli.bootstrap.load_config")
    @patch("shutil.which")
    def test_cli_uses_streaming_provider_in_max_mode(
        self,
        mock_which,
        mock_load_config,
        mock_storage,
        mock_registry,
        mock_streaming_provider,
        mock_agent,
        mock_app,
    ):
        """Verify CLI uses ACPClaudeCodeProvider in max mode."""
        from chapgent.config.settings import LLMSettings, Settings

        # Mock claude CLI being available
        mock_which.return_value = "/usr/bin/claude"

        settings = Settings(
            llm=LLMSettings(
                auth_mode="max",
                model="claude-sonnet-4-20250514",
            )
        )
        mock_load_config.return_value = settings

        runner = CliRunner()
        result = runner.invoke(cli, ["chat"])

        if result.exit_code != 0:
            print(result.output)
        assert result.exit_code == 0

        # Verify ACPClaudeCodeProvider was called
        mock_streaming_provider.assert_called_once()
        call_kwargs = mock_streaming_provider.call_args.kwargs
        assert call_kwargs.get("model") == "sonnet"  # Should map to alias

    @patch("chapgent.cli.bootstrap.ChapgentApp")
    @patch("chapgent.cli.bootstrap.Agent")
    @patch("chapgent.cli.bootstrap.LLMProvider")
    @patch("chapgent.cli.bootstrap.ToolRegistry")
    @patch("chapgent.cli.bootstrap.SessionStorage")
    @patch("chapgent.cli.bootstrap.PermissionManager")
    @patch("chapgent.cli.bootstrap.load_config")
    def test_cli_passes_extra_headers_to_provider(
        self, mock_load_config, mock_permissions, mock_storage, mock_registry, mock_provider, mock_agent, mock_app
    ):
        """Verify CLI passes extra_headers from settings to LLMProvider."""
        from chapgent.config.settings import LLMSettings, Settings

        headers = {"x-litellm-api-key": "Bearer sk-test", "Authorization": "Bearer oauth-token"}
        settings = Settings(llm=LLMSettings(api_key="test-key", extra_headers=headers))
        mock_load_config.return_value = settings

        runner = CliRunner()
        result = runner.invoke(cli, ["chat"])

        assert result.exit_code == 0

        # Verify LLMProvider was called with extra_headers
        mock_provider.assert_called_once()
        call_kwargs = mock_provider.call_args.kwargs
        assert call_kwargs.get("extra_headers") == headers

    @patch("chapgent.cli.bootstrap.ChapgentApp")
    @patch("chapgent.cli.bootstrap.Agent")
    @patch("chapgent.cli.bootstrap.ClaudeCodeProvider")
    @patch("chapgent.cli.bootstrap.ToolRegistry")
    @patch("chapgent.cli.bootstrap.SessionStorage")
    @patch("chapgent.cli.bootstrap.PermissionManager")
    @patch("chapgent.cli.bootstrap.load_config")
    @patch("shutil.which")
    def test_cli_max_mode_requires_claude_cli(
        self,
        mock_which,
        mock_load_config,
        mock_permissions,
        mock_storage,
        mock_registry,
        mock_provider,
        mock_agent,
        mock_app,
    ):
        """Verify CLI errors if claude CLI is not installed in max mode."""
        from chapgent.config.settings import LLMSettings, Settings

        # Mock claude CLI NOT being available
        mock_which.return_value = None

        settings = Settings(
            llm=LLMSettings(
                auth_mode="max",
            )
        )
        mock_load_config.return_value = settings

        runner = CliRunner()
        result = runner.invoke(cli, ["chat"])

        # Should fail with error about missing claude CLI
        assert result.exit_code != 0
        assert "Claude Code CLI" in result.output or "npm install" in result.output

    @patch("chapgent.cli.bootstrap.ChapgentApp")
    @patch("chapgent.cli.bootstrap.ACPClaudeCodeProvider")
    @patch("chapgent.cli.bootstrap.ToolRegistry")
    @patch("chapgent.cli.bootstrap.SessionStorage")
    @patch("chapgent.cli.bootstrap.load_config")
    @patch("shutil.which")
    def test_cli_max_mode_maps_model_aliases(
        self,
        mock_which,
        mock_load_config,
        mock_storage,
        mock_registry,
        mock_streaming_provider,
        mock_app,
    ):
        """Verify CLI maps model names to Claude Code aliases in max mode."""
        from chapgent.config.settings import LLMSettings, Settings

        mock_which.return_value = "/usr/bin/claude"

        # Test with opus model
        settings = Settings(
            llm=LLMSettings(
                auth_mode="max",
                model="claude-opus-4-5-20251101",
            )
        )
        mock_load_config.return_value = settings

        runner = CliRunner()
        result = runner.invoke(cli, ["chat"])

        assert result.exit_code == 0

        # Verify ACPClaudeCodeProvider was called with mapped alias
        mock_streaming_provider.assert_called_once()
        call_kwargs = mock_streaming_provider.call_args.kwargs
        assert call_kwargs.get("model") == "opus"
