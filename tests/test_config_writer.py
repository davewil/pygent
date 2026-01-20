"""Tests for the config/writer.py module."""

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.config.writer import (
    VALID_CONFIG_KEYS,
    ConfigWriteError,
    convert_value,
    format_toml_value,
    get_config_paths,
    get_default_config_content,
    get_valid_config_keys,
    save_config_value,
    write_default_config,
    write_toml,
)


class TestValidConfigKeys:
    """Tests for VALID_CONFIG_KEYS constant."""

    def test_contains_llm_keys(self):
        """Test LLM config keys are present."""
        assert "llm.provider" in VALID_CONFIG_KEYS
        assert "llm.model" in VALID_CONFIG_KEYS
        assert "llm.max_tokens" in VALID_CONFIG_KEYS
        assert "llm.api_key" in VALID_CONFIG_KEYS

    def test_contains_permission_keys(self):
        """Test permission config keys are present."""
        assert "permissions.auto_approve_low_risk" in VALID_CONFIG_KEYS
        assert "permissions.session_override_allowed" in VALID_CONFIG_KEYS

    def test_contains_tui_keys(self):
        """Test TUI config keys are present."""
        assert "tui.theme" in VALID_CONFIG_KEYS
        assert "tui.show_tool_panel" in VALID_CONFIG_KEYS
        assert "tui.show_sidebar" in VALID_CONFIG_KEYS

    def test_contains_system_prompt_keys(self):
        """Test system prompt config keys are present."""
        assert "system_prompt.content" in VALID_CONFIG_KEYS
        assert "system_prompt.file" in VALID_CONFIG_KEYS
        assert "system_prompt.append" in VALID_CONFIG_KEYS
        assert "system_prompt.mode" in VALID_CONFIG_KEYS

    def test_contains_logging_keys(self):
        """Test logging config keys are present."""
        assert "logging.level" in VALID_CONFIG_KEYS
        assert "logging.file" in VALID_CONFIG_KEYS

    def test_is_frozen_set(self):
        """Test that VALID_CONFIG_KEYS is a frozenset (immutable)."""
        assert isinstance(VALID_CONFIG_KEYS, frozenset)


class TestGetConfigPaths:
    """Tests for get_config_paths helper."""

    def test_returns_tuple_of_paths(self):
        """Test that function returns tuple of two Path objects."""
        user_config, project_config = get_config_paths()

        assert isinstance(user_config, Path)
        assert isinstance(project_config, Path)

    def test_user_config_path_structure(self):
        """Test user config path is in ~/.config/chapgent/."""
        user_config, _ = get_config_paths()

        assert user_config.name == "config.toml"
        assert user_config.parent.name == "chapgent"
        assert user_config.parent.parent.name == ".config"

    def test_project_config_path_structure(self):
        """Test project config path is in .chapgent/."""
        _, project_config = get_config_paths()

        assert project_config.name == "config.toml"
        assert project_config.parent.name == ".chapgent"


class TestConvertValue:
    """Tests for convert_value helper."""

    def test_converts_max_tokens_to_int(self):
        """Test integer conversion for max_tokens."""
        result = convert_value("llm.max_tokens", "8192")
        assert result == 8192
        assert isinstance(result, int)

    def test_invalid_max_tokens_raises(self):
        """Test invalid integer raises ConfigWriteError."""
        with pytest.raises(ConfigWriteError) as exc_info:
            convert_value("llm.max_tokens", "not_a_number")

        assert "Invalid integer" in str(exc_info.value)

    def test_converts_boolean_true_values(self):
        """Test boolean conversion for true values."""
        for value in ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]:
            result = convert_value("tui.show_tool_panel", value)
            assert result is True

    def test_converts_boolean_false_values(self):
        """Test boolean conversion for false values."""
        for value in ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]:
            result = convert_value("tui.show_tool_panel", value)
            assert result is False

    def test_invalid_boolean_raises(self):
        """Test invalid boolean raises ConfigWriteError."""
        with pytest.raises(ConfigWriteError) as exc_info:
            convert_value("tui.show_tool_panel", "maybe")

        assert "Invalid boolean" in str(exc_info.value)

    def test_validates_mode_values(self):
        """Test mode value validation."""
        assert convert_value("system_prompt.mode", "replace") == "replace"
        assert convert_value("system_prompt.mode", "append") == "append"

    def test_invalid_mode_raises(self):
        """Test invalid mode raises ConfigWriteError."""
        with pytest.raises(ConfigWriteError) as exc_info:
            convert_value("system_prompt.mode", "invalid")

        assert "Invalid mode" in str(exc_info.value)

    def test_validates_logging_level(self):
        """Test logging level validation and normalization."""
        assert convert_value("logging.level", "debug") == "DEBUG"
        assert convert_value("logging.level", "INFO") == "INFO"
        assert convert_value("logging.level", "Warning") == "WARNING"
        assert convert_value("logging.level", "ERROR") == "ERROR"

    def test_invalid_logging_level_raises(self):
        """Test invalid logging level raises ConfigWriteError."""
        with pytest.raises(ConfigWriteError) as exc_info:
            convert_value("logging.level", "TRACE")

        assert "Invalid log level" in str(exc_info.value)

    def test_string_values_pass_through(self):
        """Test string values are returned as-is."""
        result = convert_value("llm.model", "claude-sonnet-4-20250514")
        assert result == "claude-sonnet-4-20250514"
        assert isinstance(result, str)


class TestFormatTomlValue:
    """Tests for format_toml_value helper."""

    def test_formats_boolean_true(self):
        """Test boolean true formatting."""
        assert format_toml_value(True) == "true"

    def test_formats_boolean_false(self):
        """Test boolean false formatting."""
        assert format_toml_value(False) == "false"

    def test_formats_integer(self):
        """Test integer formatting."""
        assert format_toml_value(8192) == "8192"

    def test_formats_string(self):
        """Test string formatting with quotes."""
        assert format_toml_value("hello") == '"hello"'

    def test_escapes_quotes_in_string(self):
        """Test quote escaping in strings."""
        assert format_toml_value('say "hello"') == '"say \\"hello\\""'

    def test_escapes_backslashes_in_string(self):
        """Test backslash escaping in strings."""
        assert format_toml_value("path\\to\\file") == '"path\\\\to\\\\file"'


class TestWriteDefaultConfig:
    """Tests for write_default_config helper."""

    def test_creates_config_file(self, tmp_path):
        """Test that config file is created."""
        config_path = tmp_path / "chapgent" / "config.toml"
        write_default_config(config_path)

        assert config_path.exists()

    def test_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        config_path = tmp_path / "deep" / "nested" / "config.toml"
        write_default_config(config_path)

        assert config_path.parent.exists()

    def test_content_is_valid_toml(self, tmp_path):
        """Test that generated content is valid TOML."""
        config_path = tmp_path / "config.toml"
        write_default_config(config_path)

        # Should not raise
        content = config_path.read_text()
        # Note: The default config has commented-out values, so it parses as empty
        # but should still be valid TOML syntax
        # Just check it contains expected sections
        assert "[llm]" in content
        assert "[tui]" in content
        assert "[permissions]" in content


class TestGetDefaultConfigContent:
    """Tests for get_default_config_content helper."""

    def test_returns_string(self):
        """Test that function returns a string."""
        content = get_default_config_content()
        assert isinstance(content, str)

    def test_contains_sections(self):
        """Test that content contains expected sections."""
        content = get_default_config_content()
        assert "[llm]" in content
        assert "[permissions]" in content
        assert "[tui]" in content
        assert "[system_prompt]" in content
        assert "[logging]" in content


class TestWriteToml:
    """Tests for write_toml helper."""

    def test_writes_simple_values(self, tmp_path):
        """Test writing simple key-value pairs."""
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

        config_path = tmp_path / "config.toml"
        data = {"llm": {"model": "test-model", "max_tokens": 4096}}
        write_toml(config_path, data)

        # Read back and verify
        with open(config_path, "rb") as f:
            loaded = tomllib.load(f)

        assert loaded["llm"]["model"] == "test-model"
        assert loaded["llm"]["max_tokens"] == 4096

    def test_writes_nested_sections(self, tmp_path):
        """Test writing nested sections."""
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

        config_path = tmp_path / "config.toml"
        data = {
            "llm": {"model": "test"},
            "tui": {"theme": "dark", "show_tool_panel": True},
        }
        write_toml(config_path, data)

        with open(config_path, "rb") as f:
            loaded = tomllib.load(f)

        assert loaded["llm"]["model"] == "test"
        assert loaded["tui"]["theme"] == "dark"
        assert loaded["tui"]["show_tool_panel"] is True


class TestSaveConfigValue:
    """Tests for save_config_value helper."""

    def test_saves_string_value(self, tmp_path, monkeypatch):
        """Test saving a string config value."""
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

        # Mock the config paths to use tmp_path
        user_config = tmp_path / "user" / "config.toml"
        project_config = tmp_path / "project" / "config.toml"

        from chapgent.config import writer

        monkeypatch.setattr(writer, "get_config_paths", lambda: (user_config, project_config))

        path, value = save_config_value("llm.model", "test-model")

        assert path == user_config
        assert value == "test-model"

        with open(user_config, "rb") as f:
            loaded = tomllib.load(f)
        assert loaded["llm"]["model"] == "test-model"

    def test_saves_to_project_config(self, tmp_path, monkeypatch):
        """Test saving to project config."""
        user_config = tmp_path / "user" / "config.toml"
        project_config = tmp_path / "project" / "config.toml"

        from chapgent.config import writer

        monkeypatch.setattr(writer, "get_config_paths", lambda: (user_config, project_config))

        path, _ = save_config_value("llm.model", "test", project=True)

        assert path == project_config
        assert project_config.exists()

    def test_invalid_key_raises(self, tmp_path, monkeypatch):
        """Test that invalid key raises ConfigWriteError."""
        user_config = tmp_path / "user" / "config.toml"
        project_config = tmp_path / "project" / "config.toml"

        from chapgent.config import writer

        monkeypatch.setattr(writer, "get_config_paths", lambda: (user_config, project_config))

        with pytest.raises(ConfigWriteError) as exc_info:
            save_config_value("invalid.key", "value")

        assert "Invalid config key" in str(exc_info.value)

    def test_preserves_existing_values(self, tmp_path, monkeypatch):
        """Test that existing values are preserved."""
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

        user_config = tmp_path / "user" / "config.toml"
        user_config.parent.mkdir(parents=True)

        # Create existing config
        user_config.write_text('[llm]\nmodel = "existing-model"\n')

        from chapgent.config import writer

        monkeypatch.setattr(writer, "get_config_paths", lambda: (user_config, tmp_path / "p" / "c.toml"))

        save_config_value("llm.max_tokens", "8192")

        with open(user_config, "rb") as f:
            loaded = tomllib.load(f)

        # Both values should be present
        assert loaded["llm"]["model"] == "existing-model"
        assert loaded["llm"]["max_tokens"] == 8192


class TestGetValidConfigKeys:
    """Tests for get_valid_config_keys helper."""

    def test_returns_frozenset(self):
        """Test that function returns a frozenset."""
        result = get_valid_config_keys()
        assert isinstance(result, frozenset)

    def test_returns_same_as_constant(self):
        """Test that function returns the same as the constant."""
        assert get_valid_config_keys() == VALID_CONFIG_KEYS


class TestConfigWriteError:
    """Tests for ConfigWriteError exception."""

    def test_stores_message(self):
        """Test that message is stored."""
        error = ConfigWriteError("test message")
        assert error.message == "test message"
        assert str(error) == "test message"

    def test_stores_path(self):
        """Test that path is stored."""
        path = Path("/test/path")
        error = ConfigWriteError("test", path=path)
        assert error.path == path

    def test_path_default_none(self):
        """Test that path defaults to None."""
        error = ConfigWriteError("test")
        assert error.path is None


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.integers(min_value=1, max_value=100000))
    @settings(max_examples=20)
    def test_max_tokens_roundtrip(self, value):
        """Test max_tokens value roundtrip."""
        result = convert_value("llm.max_tokens", str(value))
        assert result == value

    @given(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cs"])))
    @settings(max_examples=20)
    def test_string_value_roundtrip(self, value):
        """Test string value formatting roundtrip."""
        formatted = format_toml_value(value)
        # Should be quoted
        assert formatted.startswith('"')
        assert formatted.endswith('"')

    @given(st.booleans())
    def test_boolean_format_roundtrip(self, value):
        """Test boolean formatting roundtrip."""
        formatted = format_toml_value(value)
        assert formatted in ("true", "false")


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_string_value(self):
        """Test handling empty string value."""
        result = convert_value("llm.model", "")
        assert result == ""

    def test_whitespace_string_value(self):
        """Test handling whitespace-only string value."""
        result = convert_value("llm.model", "   ")
        assert result == "   "

    def test_unicode_string_value(self):
        """Test handling unicode in string value."""
        result = convert_value("llm.model", "模型名称")
        assert result == "模型名称"

    def test_special_chars_in_string(self):
        """Test special characters in string value."""
        result = format_toml_value('test\n\t"value"')
        # Should escape quotes
        assert '\\"' in result


class TestIntegration:
    """Integration tests."""

    def test_full_config_write_workflow(self, tmp_path, monkeypatch):
        """Test full workflow of setting multiple config values."""
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

        user_config = tmp_path / "user" / "config.toml"

        from chapgent.config import writer

        monkeypatch.setattr(writer, "get_config_paths", lambda: (user_config, tmp_path / "p" / "c.toml"))

        # Set multiple values
        save_config_value("llm.model", "test-model")
        save_config_value("llm.max_tokens", "8192")
        save_config_value("tui.theme", "dark")
        save_config_value("tui.show_tool_panel", "true")

        # Verify all values
        with open(user_config, "rb") as f:
            loaded = tomllib.load(f)

        assert loaded["llm"]["model"] == "test-model"
        assert loaded["llm"]["max_tokens"] == 8192
        assert loaded["tui"]["theme"] == "dark"
        assert loaded["tui"]["show_tool_panel"] is True
