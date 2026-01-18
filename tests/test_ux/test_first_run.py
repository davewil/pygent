"""Tests for UX first-run experience module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pygent.ux.first_run import (
    SetupStatus,
    check_api_key,
    check_setup_status,
    create_first_run_marker,
    format_setup_complete_message,
    get_api_key_help,
    get_config_path,
    get_setup_instructions,
    get_welcome_message,
    has_completed_first_run,
    should_show_first_run_prompt,
    validate_api_key_format,
)


class TestSetupStatus:
    """Tests for SetupStatus dataclass."""

    def test_create_setup_status(self) -> None:
        """Should create a SetupStatus."""
        status = SetupStatus(
            is_first_run=True,
            has_api_key=False,
            has_config_file=False,
            config_path=Path("/test/config.toml"),
            missing_items=["API key"],
        )
        assert status.is_first_run is True
        assert status.has_api_key is False
        assert status.has_config_file is False
        assert status.config_path == Path("/test/config.toml")
        assert "API key" in status.missing_items

    def test_setup_status_with_everything_configured(self) -> None:
        """Should represent fully configured state."""
        status = SetupStatus(
            is_first_run=False,
            has_api_key=True,
            has_config_file=True,
            config_path=Path("/test/config.toml"),
            missing_items=[],
        )
        assert status.is_first_run is False
        assert status.has_api_key is True
        assert status.has_config_file is True
        assert len(status.missing_items) == 0


class TestGetConfigPath:
    """Tests for get_config_path function."""

    def test_returns_path(self) -> None:
        """Should return a Path object."""
        result = get_config_path()
        assert isinstance(result, Path)

    def test_path_ends_with_config_toml(self) -> None:
        """Path should end with config.toml."""
        result = get_config_path()
        assert result.name == "config.toml"

    def test_path_includes_pygent(self) -> None:
        """Path should include pygent directory."""
        result = get_config_path()
        assert "pygent" in str(result)

    def test_path_is_in_home(self) -> None:
        """Path should be under home directory."""
        result = get_config_path()
        home = Path.home()
        assert str(result).startswith(str(home))


class TestCheckApiKey:
    """Tests for check_api_key function."""

    def test_returns_false_when_no_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when no API key env vars are set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)
        result = check_api_key()
        assert result is False

    def test_returns_true_with_anthropic_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when ANTHROPIC_API_KEY is set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        result = check_api_key()
        assert result is True

    def test_returns_true_with_openai_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when OPENAI_API_KEY is set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        result = check_api_key()
        assert result is True

    def test_returns_true_with_pygent_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when PYGENT_API_KEY is set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("PYGENT_API_KEY", "custom-key")
        result = check_api_key()
        assert result is True

    def test_empty_string_is_not_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string env var should not count as valid."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        result = check_api_key()
        assert result is False


class TestCheckSetupStatus:
    """Tests for check_setup_status function."""

    def test_returns_setup_status(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Should return a SetupStatus object."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        result = check_setup_status()
        assert isinstance(result, SetupStatus)

    def test_first_run_when_nothing_configured(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Should detect first run when no API key and no config."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        # Mock home to use tmp_path
        with patch.object(Path, "home", return_value=tmp_path):
            result = check_setup_status()
            assert result.is_first_run is True
            assert result.has_api_key is False
            assert result.has_config_file is False

    def test_not_first_run_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should not be first run if API key is set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        result = check_setup_status()
        assert result.is_first_run is False
        assert result.has_api_key is True


class TestValidateApiKeyFormat:
    """Tests for validate_api_key_format function."""

    def test_anthropic_key_format(self) -> None:
        """Should validate Anthropic key format."""
        valid_key = "sk-ant-api03-" + "x" * 40
        is_valid, message = validate_api_key_format(valid_key)
        assert is_valid is True
        assert "Anthropic" in message

    def test_openai_key_format(self) -> None:
        """Should validate OpenAI key format."""
        valid_key = "sk-" + "x" * 40
        is_valid, message = validate_api_key_format(valid_key)
        assert is_valid is True
        assert "OpenAI" in message

    def test_empty_key_invalid(self) -> None:
        """Empty key should be invalid."""
        is_valid, message = validate_api_key_format("")
        assert is_valid is False
        assert "empty" in message.lower()

    def test_short_key_invalid(self) -> None:
        """Very short key should be invalid."""
        is_valid, message = validate_api_key_format("abc")
        assert is_valid is False
        assert "short" in message.lower()

    def test_whitespace_stripped(self) -> None:
        """Whitespace should be stripped."""
        valid_key = "  sk-ant-api03-" + "x" * 40 + "  "
        is_valid, _ = validate_api_key_format(valid_key)
        assert is_valid is True

    def test_unknown_format_accepted(self) -> None:
        """Unknown format should be accepted if long enough."""
        is_valid, _ = validate_api_key_format("x" * 50)
        assert is_valid is True


class TestGetWelcomeMessage:
    """Tests for get_welcome_message function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        result = get_welcome_message()
        assert isinstance(result, str)

    def test_contains_welcome(self) -> None:
        """Should contain welcome text."""
        result = get_welcome_message()
        assert "Welcome" in result or "welcome" in result

    def test_contains_pygent(self) -> None:
        """Should mention Pygent."""
        result = get_welcome_message()
        assert "Pygent" in result or "pygent" in result

    def test_has_meaningful_length(self) -> None:
        """Should have meaningful content."""
        result = get_welcome_message()
        assert len(result) > 100


class TestGetSetupInstructions:
    """Tests for get_setup_instructions function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        status = SetupStatus(
            is_first_run=True,
            has_api_key=False,
            has_config_file=False,
            config_path=Path("/test/config.toml"),
            missing_items=["API key"],
        )
        result = get_setup_instructions(status)
        assert isinstance(result, str)

    def test_mentions_api_key_when_missing(self) -> None:
        """Should mention API key when missing."""
        status = SetupStatus(
            is_first_run=True,
            has_api_key=False,
            has_config_file=True,
            config_path=Path("/test/config.toml"),
            missing_items=["API key"],
        )
        result = get_setup_instructions(status)
        assert "API" in result or "api" in result

    def test_mentions_config_when_missing(self) -> None:
        """Should mention config when missing."""
        status = SetupStatus(
            is_first_run=True,
            has_api_key=True,
            has_config_file=False,
            config_path=Path("/test/config.toml"),
            missing_items=["Config file"],
        )
        result = get_setup_instructions(status)
        assert "config" in result.lower()


class TestGetApiKeyHelp:
    """Tests for get_api_key_help function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        result = get_api_key_help()
        assert isinstance(result, str)

    def test_mentions_environment_variable(self) -> None:
        """Should mention environment variable option."""
        result = get_api_key_help()
        assert "environment" in result.lower() or "export" in result.lower()

    def test_mentions_anthropic(self) -> None:
        """Should mention Anthropic."""
        result = get_api_key_help()
        assert "anthropic" in result.lower()


class TestFormatSetupCompleteMessage:
    """Tests for format_setup_complete_message function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        result = format_setup_complete_message()
        assert isinstance(result, str)

    def test_contains_complete(self) -> None:
        """Should indicate completion."""
        result = format_setup_complete_message()
        assert "Complete" in result or "complete" in result or "set" in result.lower()

    def test_with_settings(self) -> None:
        """Should include settings info when provided."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_settings.llm.provider = "test-provider"

        result = format_setup_complete_message(mock_settings)
        assert "test-model" in result
        assert "test-provider" in result


class TestShouldShowFirstRunPrompt:
    """Tests for should_show_first_run_prompt function."""

    def test_false_when_api_key_exists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when API key exists."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        result = should_show_first_run_prompt()
        assert result is False

    def test_true_when_no_api_key_and_no_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Should return True when no API key and no config."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        with patch.object(Path, "home", return_value=tmp_path):
            result = should_show_first_run_prompt()
            assert result is True


class TestFirstRunMarker:
    """Tests for first-run marker functions."""

    def test_create_marker(self, tmp_path: Path) -> None:
        """Should create marker file."""
        with patch.object(Path, "home", return_value=tmp_path):
            create_first_run_marker()
            marker_path = tmp_path / ".local" / "share" / "pygent" / ".first_run_complete"
            assert marker_path.exists()

    def test_has_completed_first_run_false_initially(self, tmp_path: Path) -> None:
        """Should return False when marker doesn't exist."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = has_completed_first_run()
            assert result is False

    def test_has_completed_first_run_true_after_marker(self, tmp_path: Path) -> None:
        """Should return True after marker is created."""
        with patch.object(Path, "home", return_value=tmp_path):
            create_first_run_marker()
            result = has_completed_first_run()
            assert result is True


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=50)
    def test_validate_api_key_never_raises(self, key: str) -> None:
        """validate_api_key_format should never raise."""
        is_valid, message = validate_api_key_format(key)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

    @given(st.booleans(), st.booleans())
    @settings(max_examples=20)
    def test_setup_status_creation(self, has_api: bool, has_config: bool) -> None:
        """SetupStatus should accept various combinations."""
        status = SetupStatus(
            is_first_run=not has_api and not has_config,
            has_api_key=has_api,
            has_config_file=has_config,
            config_path=Path("/test/config.toml"),
            missing_items=[],
        )
        assert isinstance(status, SetupStatus)


class TestEdgeCases:
    """Edge case tests."""

    def test_validate_only_whitespace(self) -> None:
        """Should handle whitespace-only key."""
        is_valid, message = validate_api_key_format("   ")
        assert is_valid is False

    def test_validate_unicode_key(self) -> None:
        """Should handle unicode in key."""
        is_valid, message = validate_api_key_format("\u00e9" * 50)
        # Should accept if long enough
        assert isinstance(is_valid, bool)

    def test_setup_status_with_empty_path(self) -> None:
        """Should handle empty path."""
        status = SetupStatus(
            is_first_run=True,
            has_api_key=False,
            has_config_file=False,
            config_path=Path(""),
            missing_items=[],
        )
        assert status.config_path == Path("")


class TestIntegration:
    """Integration tests."""

    def test_full_first_run_flow(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test complete first-run detection flow."""
        # Clear env vars
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PYGENT_API_KEY", raising=False)

        with patch.object(Path, "home", return_value=tmp_path):
            # Should be first run
            assert should_show_first_run_prompt() is True

            # Get welcome message
            welcome = get_welcome_message()
            assert len(welcome) > 0

            # Get setup status
            status = check_setup_status()
            assert status.is_first_run is True

            # Get instructions
            instructions = get_setup_instructions(status)
            assert "API" in instructions

            # Create marker
            create_first_run_marker()

            # Should still show prompt (marker doesn't affect should_show logic directly)
            # The first run check is based on API key, not marker

    def test_configured_user_flow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test flow for configured user."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        # Should not show first run
        assert should_show_first_run_prompt() is False

        # Status should reflect configured state
        status = check_setup_status()
        assert status.has_api_key is True
        assert status.is_first_run is False
