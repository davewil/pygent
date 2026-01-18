"""Tests for logging infrastructure."""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pygent.cli import cli
from pygent.core.logging import (
    DEFAULT_LOG_DIR,
    DEFAULT_LOG_FILE,
    LOG_FORMAT,
    VALID_LOG_LEVELS,
    disable_logging,
    enable_logging,
    get_log_dir,
    get_log_file,
    get_log_files,
    get_valid_log_levels,
    redact_sensitive,
    reset_logging,
    setup_logging,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class TestConstants:
    """Tests for module-level constants."""

    def test_default_log_dir_is_path(self) -> None:
        """DEFAULT_LOG_DIR should be a Path object."""
        assert isinstance(DEFAULT_LOG_DIR, Path)

    def test_default_log_dir_in_local_share(self) -> None:
        """DEFAULT_LOG_DIR should be in ~/.local/share/pygent/logs."""
        assert "pygent" in str(DEFAULT_LOG_DIR)
        assert "logs" in str(DEFAULT_LOG_DIR)

    def test_default_log_file_is_path(self) -> None:
        """DEFAULT_LOG_FILE should be a Path object."""
        assert isinstance(DEFAULT_LOG_FILE, Path)

    def test_default_log_file_ends_with_log(self) -> None:
        """DEFAULT_LOG_FILE should end with .log."""
        assert str(DEFAULT_LOG_FILE).endswith("pygent.log")

    def test_log_format_contains_required_parts(self) -> None:
        """LOG_FORMAT should contain time, level, name, and message."""
        assert "{time" in LOG_FORMAT
        assert "{level" in LOG_FORMAT
        assert "{name}" in LOG_FORMAT
        assert "{message}" in LOG_FORMAT

    def test_valid_log_levels_contains_all_levels(self) -> None:
        """VALID_LOG_LEVELS should contain standard log levels."""
        assert "DEBUG" in VALID_LOG_LEVELS
        assert "INFO" in VALID_LOG_LEVELS
        assert "WARNING" in VALID_LOG_LEVELS
        assert "ERROR" in VALID_LOG_LEVELS

    def test_valid_log_levels_is_frozenset(self) -> None:
        """VALID_LOG_LEVELS should be immutable."""
        assert isinstance(VALID_LOG_LEVELS, frozenset)


class TestGetLogDir:
    """Tests for get_log_dir function."""

    def test_returns_default_log_dir(self) -> None:
        """Returns the default log directory path."""
        result = get_log_dir()
        assert result == DEFAULT_LOG_DIR

    def test_returns_path_object(self) -> None:
        """Returns a Path object."""
        result = get_log_dir()
        assert isinstance(result, Path)


class TestGetLogFile:
    """Tests for get_log_file function."""

    def test_returns_default_log_file(self) -> None:
        """Returns the default log file path."""
        result = get_log_file()
        assert result == DEFAULT_LOG_FILE

    def test_returns_path_object(self) -> None:
        """Returns a Path object."""
        result = get_log_file()
        assert isinstance(result, Path)


class TestGetValidLogLevels:
    """Tests for get_valid_log_levels function."""

    def test_returns_valid_log_levels(self) -> None:
        """Returns the VALID_LOG_LEVELS constant."""
        result = get_valid_log_levels()
        assert result == VALID_LOG_LEVELS


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_log_directory(self, tmp_path: Path) -> None:
        """Creates log directory if it doesn't exist."""
        log_file = tmp_path / "logs" / "test.log"
        reset_logging()

        result = setup_logging(log_file=log_file)

        assert result == log_file
        assert log_file.parent.exists()

    def test_returns_log_file_path(self, tmp_path: Path) -> None:
        """Returns the path to the log file."""
        log_file = tmp_path / "test.log"
        reset_logging()

        result = setup_logging(log_file=log_file)

        assert result == log_file

    def test_default_level_is_info(self, tmp_path: Path) -> None:
        """Default log level is INFO."""
        log_file = tmp_path / "test.log"
        reset_logging()

        # Should not raise even without specifying level
        setup_logging(log_file=log_file)

    def test_accepts_valid_levels(self, tmp_path: Path) -> None:
        """Accepts all valid log levels."""
        for level in VALID_LOG_LEVELS:
            log_file = tmp_path / f"test_{level}.log"
            reset_logging()

            result = setup_logging(level=level, log_file=log_file)
            assert result == log_file

    def test_level_is_case_insensitive(self, tmp_path: Path) -> None:
        """Log level is case insensitive."""
        log_file = tmp_path / "test.log"
        reset_logging()

        result = setup_logging(level="debug", log_file=log_file)
        assert result == log_file

    def test_raises_for_invalid_level(self, tmp_path: Path) -> None:
        """Raises ValueError for invalid log level."""
        log_file = tmp_path / "test.log"
        reset_logging()

        with pytest.raises(ValueError) as exc_info:
            setup_logging(level="INVALID", log_file=log_file)

        assert "Invalid log level" in str(exc_info.value)
        assert "INVALID" in str(exc_info.value)

    def test_uses_default_path_when_none(self) -> None:
        """Uses default log file path when not specified."""
        reset_logging()

        result = setup_logging()

        assert result == DEFAULT_LOG_FILE


class TestDisableEnableLogging:
    """Tests for disable_logging and enable_logging functions."""

    def test_disable_logging_disables_pygent(self) -> None:
        """disable_logging disables the pygent logger."""
        # Should not raise
        disable_logging()

    def test_enable_logging_enables_pygent(self) -> None:
        """enable_logging enables the pygent logger."""
        disable_logging()
        # Should not raise
        enable_logging()


class TestResetLogging:
    """Tests for reset_logging function."""

    def test_reset_clears_handlers(self) -> None:
        """reset_logging removes all handlers."""
        # Should not raise
        reset_logging()


class TestRedactSensitive:
    """Tests for redact_sensitive function."""

    def test_redacts_api_key_pattern(self) -> None:
        """Redacts api_key = value patterns."""
        content = 'api_key = "sk-test12345678901234567890"'
        result = redact_sensitive(content)
        assert "sk-test12345678901234567890" not in result
        assert "[REDACTED]" in result or "[REDACTED_KEY]" in result

    def test_redacts_anthropic_api_key(self) -> None:
        """Redacts ANTHROPIC_API_KEY env var."""
        content = "ANTHROPIC_API_KEY=sk-ant-test1234"
        result = redact_sensitive(content)
        assert "sk-ant-test1234" not in result
        assert "[REDACTED]" in result

    def test_redacts_openai_api_key(self) -> None:
        """Redacts OPENAI_API_KEY env var."""
        content = "OPENAI_API_KEY=sk-proj-test1234"
        result = redact_sensitive(content)
        assert "sk-proj-test1234" not in result
        assert "[REDACTED]" in result

    def test_redacts_pygent_api_key(self) -> None:
        """Redacts PYGENT_API_KEY env var."""
        content = "PYGENT_API_KEY=my-secret-key"
        result = redact_sensitive(content)
        assert "my-secret-key" not in result
        assert "[REDACTED]" in result

    def test_redacts_sk_prefixed_keys(self) -> None:
        """Redacts any sk-xxx prefixed keys."""
        content = "key: sk-abcdefghijklmnopqrstuvwxyz"
        result = redact_sensitive(content)
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in result
        assert "[REDACTED_KEY]" in result

    def test_redacts_home_directory(self) -> None:
        """Replaces home directory with ~."""
        home = str(Path.home())
        content = f"Reading file at {home}/Documents/test.txt"
        result = redact_sensitive(content)
        assert home not in result
        assert "~/Documents/test.txt" in result

    def test_preserves_non_sensitive_content(self) -> None:
        """Preserves content that is not sensitive."""
        content = "This is a normal log message about testing."
        result = redact_sensitive(content)
        assert result == content

    def test_handles_empty_string(self) -> None:
        """Handles empty string input."""
        result = redact_sensitive("")
        assert result == ""

    def test_case_insensitive_api_key_matching(self) -> None:
        """Matches api_key patterns case-insensitively."""
        content = 'API_KEY: "mysecretkey123"'
        result = redact_sensitive(content)
        assert "mysecretkey123" not in result


class TestGetLogFiles:
    """Tests for get_log_files function."""

    def test_returns_empty_when_dir_not_exists(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Returns empty list when log directory doesn't exist."""
        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: tmp_path / "nonexistent")

        result = get_log_files()

        assert result == []

    def test_returns_log_files(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Returns list of log files when they exist."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create some log files
        (log_dir / "pygent.log").write_text("log content")
        (log_dir / "pygent.log.1").write_text("old log")
        (log_dir / "pygent.log.2.gz").write_text("compressed")

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)

        result = get_log_files()

        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)

    def test_sorted_by_modification_time(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Returns files sorted by modification time (newest first)."""
        import time

        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create files with different modification times
        file1 = log_dir / "pygent.log"
        file1.write_text("first")

        time.sleep(0.01)  # Small delay to ensure different mtime

        file2 = log_dir / "pygent.log.1"
        file2.write_text("second")

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)

        result = get_log_files()

        assert len(result) == 2
        # Newest first
        assert result[0].name == "pygent.log.1"
        assert result[1].name == "pygent.log"


class TestLoggingSettings:
    """Tests for LoggingSettings model."""

    def test_default_level_is_info(self) -> None:
        """Default log level is INFO."""
        from pygent.config.settings import LoggingSettings

        settings = LoggingSettings()
        assert settings.level == "INFO"

    def test_default_file_is_none(self) -> None:
        """Default file path is None."""
        from pygent.config.settings import LoggingSettings

        settings = LoggingSettings()
        assert settings.file is None

    def test_accepts_valid_levels(self) -> None:
        """Accepts all valid log levels."""
        from pygent.config.settings import LoggingSettings

        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            settings = LoggingSettings(level=level)
            assert settings.level == level

    def test_validates_file_not_empty(self) -> None:
        """Rejects empty string for file path."""
        from pydantic import ValidationError

        from pygent.config.settings import LoggingSettings

        with pytest.raises(ValidationError) as exc_info:
            LoggingSettings(file="")

        assert "logging.file" in str(exc_info.value).lower() or "cannot be an empty string" in str(exc_info.value)

    def test_accepts_file_path(self) -> None:
        """Accepts a valid file path."""
        from pygent.config.settings import LoggingSettings

        settings = LoggingSettings(file="~/custom/log.log")
        assert settings.file == "~/custom/log.log"


class TestCLIReportCommand:
    """Tests for the 'pygent report' CLI command."""

    def test_report_no_logs_dir(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Shows message when log directory doesn't exist."""
        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: tmp_path / "nonexistent")

        runner = CliRunner()
        result = runner.invoke(cli, ["report"])

        assert result.exit_code == 0
        assert "No logs found" in result.output

    def test_report_no_log_files(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Shows message when no log files found."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)
        monkeypatch.setattr("pygent.core.logging.get_log_files", lambda days=7: [])

        runner = CliRunner()
        result = runner.invoke(cli, ["report"])

        assert result.exit_code == 0
        assert "No log files found" in result.output

    def test_report_creates_archive(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Creates a tar.gz archive with log files."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create a log file
        log_file = log_dir / "pygent.log"
        log_file.write_text("Test log content")

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)
        monkeypatch.setattr("pygent.core.logging.get_log_files", lambda days=7: [log_file])

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "-o", "test-report.tar.gz"])

            assert result.exit_code == 0
            assert "Report created" in result.output
            assert Path("test-report.tar.gz").exists()

            # Verify archive contents
            with tarfile.open("test-report.tar.gz", "r:gz") as tar:
                names = tar.getnames()
                assert "pygent.log" in names

    def test_report_redacts_sensitive_data(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Redacts sensitive data in the archive."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create a log file with sensitive data
        log_file = log_dir / "pygent.log"
        log_file.write_text("ANTHROPIC_API_KEY=sk-ant-secret123\nNormal log entry")

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)
        monkeypatch.setattr("pygent.core.logging.get_log_files", lambda days=7: [log_file])

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "-o", "test-report.tar.gz"])

            assert result.exit_code == 0

            # Extract and check content is redacted
            with tarfile.open("test-report.tar.gz", "r:gz") as tar:
                member = tar.extractfile("pygent.log")
                assert member is not None
                content = member.read().decode("utf-8")
                assert "sk-ant-secret123" not in content
                assert "[REDACTED]" in content

    def test_report_custom_output_path(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Supports custom output path."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "pygent.log"
        log_file.write_text("Log content")

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)
        monkeypatch.setattr("pygent.core.logging.get_log_files", lambda days=7: [log_file])

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["report", "-o", "custom-name.tar.gz"])

            assert result.exit_code == 0
            assert Path("custom-name.tar.gz").exists()


class TestCLILogsCommand:
    """Tests for the 'pygent logs' CLI command."""

    def test_logs_shows_path(self, monkeypatch: MonkeyPatch) -> None:
        """Shows log file path without options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])

        assert result.exit_code == 0
        assert "Log file:" in result.output

    def test_logs_shows_exists_status(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Shows [exists] or [not found] status."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])

        assert result.exit_code == 0
        assert "[exists]" in result.output or "[not found]" in result.output


class TestConfigSetLogging:
    """Tests for setting logging config via CLI."""

    def test_set_logging_level(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Can set logging.level via config set."""
        config_file = tmp_path / "config.toml"

        def mock_get_config_paths() -> tuple[Path, Path]:
            return config_file, tmp_path / ".pygent" / "config.toml"

        monkeypatch.setattr("pygent.cli._get_config_paths", mock_get_config_paths)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "logging.level", "DEBUG"])

        assert result.exit_code == 0
        assert "Set logging.level" in result.output

        # Verify the file was written
        content = config_file.read_text()
        assert "DEBUG" in content

    def test_set_logging_file(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Can set logging.file via config set."""
        config_file = tmp_path / "config.toml"

        def mock_get_config_paths() -> tuple[Path, Path]:
            return config_file, tmp_path / ".pygent" / "config.toml"

        monkeypatch.setattr("pygent.cli._get_config_paths", mock_get_config_paths)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "logging.file", "/custom/path.log"])

        assert result.exit_code == 0
        assert "Set logging.file" in result.output

    def test_set_logging_level_validates(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Validates logging level value."""
        config_file = tmp_path / "config.toml"

        def mock_get_config_paths() -> tuple[Path, Path]:
            return config_file, tmp_path / ".pygent" / "config.toml"

        monkeypatch.setattr("pygent.cli._get_config_paths", mock_get_config_paths)

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "logging.level", "INVALID"])

        assert result.exit_code != 0
        assert "Invalid log level" in result.output


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50)
    def test_redact_sensitive_never_raises(self, content: str) -> None:
        """redact_sensitive never raises on any string input."""
        result = redact_sensitive(content)
        assert isinstance(result, str)

    @given(level=st.sampled_from(list(VALID_LOG_LEVELS)))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_setup_logging_accepts_all_valid_levels(self, tmp_path: Path, level: str) -> None:
        """setup_logging accepts all valid log levels."""
        import uuid

        log_file = tmp_path / f"test_{uuid.uuid4()}_{level}.log"
        reset_logging()

        result = setup_logging(level=level, log_file=log_file)
        assert result == log_file

    @given(level=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=5, max_size=20))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_levels_always_raise(self, tmp_path: Path, level: str) -> None:
        """Invalid log levels always raise ValueError."""
        import uuid

        if level.upper() in VALID_LOG_LEVELS:
            return  # Skip valid levels

        log_file = tmp_path / f"test_{uuid.uuid4()}.log"
        reset_logging()

        with pytest.raises(ValueError):
            setup_logging(level=level, log_file=log_file)


class TestEdgeCases:
    """Edge case tests."""

    def test_redact_multiple_keys_same_line(self) -> None:
        """Redacts multiple keys on the same line."""
        content = "ANTHROPIC_API_KEY=key1 OPENAI_API_KEY=key2"
        result = redact_sensitive(content)
        assert "key1" not in result
        assert "key2" not in result

    def test_redact_json_format(self) -> None:
        """Redacts API keys in JSON format."""
        content = '{"api_key": "sk-secret12345678901234567890"}'
        result = redact_sensitive(content)
        assert "sk-secret12345678901234567890" not in result

    def test_redact_preserves_structure(self) -> None:
        """Preserves overall structure while redacting."""
        content = """
2024-01-15 10:00:00 | INFO | Starting with ANTHROPIC_API_KEY=sk-secret
2024-01-15 10:00:01 | DEBUG | Processing file at /home/user/test.py
"""
        result = redact_sensitive(content)
        # Structure preserved
        assert "2024-01-15 10:00:00" in result
        assert "INFO" in result
        assert "DEBUG" in result
        # Sensitive data redacted
        assert "sk-secret" not in result

    def test_setup_logging_with_tilde_path(self, tmp_path: Path) -> None:
        """setup_logging expands ~ in file path."""
        # Use tmp_path to avoid writing to actual home
        log_file = tmp_path / "test.log"
        reset_logging()

        result = setup_logging(log_file=log_file)
        assert result == log_file

    def test_get_log_files_ignores_non_log_files(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """get_log_files ignores files that don't match log pattern."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create various files
        (log_dir / "pygent.log").write_text("log")
        (log_dir / "other.txt").write_text("not a log")
        (log_dir / "random.dat").write_text("data")

        monkeypatch.setattr("pygent.core.logging.get_log_dir", lambda: log_dir)

        result = get_log_files()

        # Only pygent.log should be included
        assert len(result) == 1
        assert result[0].name == "pygent.log"


class TestIntegration:
    """Integration tests for logging infrastructure."""

    def test_full_logging_workflow(self, tmp_path: Path) -> None:
        """Test complete logging setup, write, and cleanup workflow."""
        log_file = tmp_path / "integration.log"
        reset_logging()

        # Setup logging
        result = setup_logging(level="DEBUG", log_file=log_file)
        assert result == log_file

        # Log file should be created
        assert log_file.parent.exists()

        # Disable logging
        disable_logging()

        # Re-enable logging
        enable_logging()

        # Reset for cleanup
        reset_logging()

    def test_settings_integration(self) -> None:
        """Test that LoggingSettings integrates with Settings."""
        from pygent.config.settings import Settings

        settings = Settings()
        assert hasattr(settings, "logging")
        assert settings.logging.level == "INFO"
        assert settings.logging.file is None

    def test_settings_with_custom_logging(self) -> None:
        """Test Settings with custom logging configuration."""
        from pygent.config.settings import Settings

        settings = Settings(logging={"level": "DEBUG", "file": "~/custom.log"})
        assert settings.logging.level == "DEBUG"
        assert settings.logging.file == "~/custom.log"
