"""Tests for environment variable configuration support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import tomli_w
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.config.loader import (
    API_KEY_ENV_PRIORITY,
    ENV_MAPPINGS,
    _convert_env_value,
    _load_env_config,
    _set_nested_value,
    load_config,
)
from chapgent.config.settings import (
    MAX_OUTPUT_TOKENS_MAX,
    MAX_OUTPUT_TOKENS_MIN,
    LLMSettings,
    PermissionSettings,
)


class TestEnvMappings:
    """Tests for ENV_MAPPINGS constant."""

    def test_contains_chapgent_vars(self) -> None:
        """Chapgent-specific env vars are defined."""
        assert "CHAPGENT_MODEL" in ENV_MAPPINGS
        assert "CHAPGENT_API_KEY" in ENV_MAPPINGS
        assert "CHAPGENT_MAX_OUTPUT_TOKENS" in ENV_MAPPINGS
        assert "CHAPGENT_PROVIDER" in ENV_MAPPINGS

    def test_contains_api_key_fallbacks(self) -> None:
        """Standard API key env vars are defined as fallbacks."""
        assert "ANTHROPIC_API_KEY" in ENV_MAPPINGS
        assert "OPENAI_API_KEY" in ENV_MAPPINGS

    def test_paths_are_valid(self) -> None:
        """All mapped paths are valid dotted paths."""
        for env_var, path in ENV_MAPPINGS.items():
            parts = path.split(".")
            assert len(parts) >= 2, f"{env_var} path should have at least 2 parts"
            assert all(part.isidentifier() for part in parts), f"{env_var} path has invalid parts"


class TestApiKeyEnvPriority:
    """Tests for API_KEY_ENV_PRIORITY constant."""

    def test_chapgent_api_key_first(self) -> None:
        """CHAPGENT_API_KEY should have highest priority."""
        assert API_KEY_ENV_PRIORITY[0] == "CHAPGENT_API_KEY"

    def test_anthropic_before_openai(self) -> None:
        """ANTHROPIC_API_KEY should come before OPENAI_API_KEY."""
        anthropic_idx = API_KEY_ENV_PRIORITY.index("ANTHROPIC_API_KEY")
        openai_idx = API_KEY_ENV_PRIORITY.index("OPENAI_API_KEY")
        assert anthropic_idx < openai_idx

    def test_all_are_in_env_mappings(self) -> None:
        """All priority keys should be in ENV_MAPPINGS."""
        for key in API_KEY_ENV_PRIORITY:
            assert key in ENV_MAPPINGS


class TestSetNestedValue:
    """Tests for _set_nested_value helper function."""

    def test_single_level(self) -> None:
        """Sets value at top level."""
        data: dict[str, Any] = {}
        _set_nested_value(data, "key", "value")
        assert data == {"key": "value"}

    def test_two_levels(self) -> None:
        """Sets value at nested level."""
        data: dict[str, Any] = {}
        _set_nested_value(data, "llm.model", "gpt-4")
        assert data == {"llm": {"model": "gpt-4"}}

    def test_three_levels(self) -> None:
        """Sets value at deeply nested level."""
        data: dict[str, Any] = {}
        _set_nested_value(data, "a.b.c", "deep")
        assert data == {"a": {"b": {"c": "deep"}}}

    def test_preserves_existing_siblings(self) -> None:
        """Preserves existing values at same level."""
        data: dict[str, Any] = {"llm": {"provider": "anthropic"}}
        _set_nested_value(data, "llm.model", "claude-3")
        assert data == {"llm": {"provider": "anthropic", "model": "claude-3"}}

    def test_overwrites_existing_value(self) -> None:
        """Overwrites existing value at same path."""
        data: dict[str, Any] = {"llm": {"model": "old"}}
        _set_nested_value(data, "llm.model", "new")
        assert data == {"llm": {"model": "new"}}

    def test_creates_intermediate_dicts(self) -> None:
        """Creates intermediate dicts as needed."""
        data: dict[str, Any] = {}
        _set_nested_value(data, "deeply.nested.path.value", 42)
        assert data["deeply"]["nested"]["path"]["value"] == 42


class TestConvertEnvValue:
    """Tests for _convert_env_value helper function."""

    def test_max_output_tokens_converted_to_int(self) -> None:
        """max_output_tokens paths are converted to integers."""
        assert _convert_env_value("4096", "llm.max_output_tokens") == 4096
        assert _convert_env_value("8192", "some.max_output_tokens") == 8192

    def test_max_output_tokens_invalid_stays_string(self) -> None:
        """Invalid max_output_tokens value stays as string."""
        assert _convert_env_value("not_a_number", "llm.max_output_tokens") == "not_a_number"

    def test_boolean_true_values(self) -> None:
        """Boolean paths convert true-like values."""
        bool_path = "permissions.auto_approve_low_risk"
        assert _convert_env_value("true", bool_path) is True
        assert _convert_env_value("True", bool_path) is True
        assert _convert_env_value("TRUE", bool_path) is True
        assert _convert_env_value("1", bool_path) is True
        assert _convert_env_value("yes", bool_path) is True
        assert _convert_env_value("on", bool_path) is True

    def test_boolean_false_values(self) -> None:
        """Boolean paths convert false-like values."""
        bool_path = "permissions.session_override_allowed"
        assert _convert_env_value("false", bool_path) is False
        assert _convert_env_value("False", bool_path) is False
        assert _convert_env_value("0", bool_path) is False
        assert _convert_env_value("no", bool_path) is False
        assert _convert_env_value("off", bool_path) is False
        assert _convert_env_value("anything_else", bool_path) is False

    def test_tui_boolean_paths(self) -> None:
        """TUI boolean settings are converted."""
        assert _convert_env_value("true", "tui.show_tool_panel") is True
        assert _convert_env_value("false", "tui.show_sidebar") is False

    def test_string_values_unchanged(self) -> None:
        """Non-special paths stay as strings."""
        assert _convert_env_value("claude-3", "llm.model") == "claude-3"
        assert _convert_env_value("anthropic", "llm.provider") == "anthropic"


class TestLoadEnvConfig:
    """Tests for _load_env_config function."""

    def test_empty_when_no_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns empty dict when no relevant env vars set."""
        # Clear all relevant env vars
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        result = _load_env_config()
        assert result == {}

    def test_loads_chapgent_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Loads CHAPGENT_MODEL env var."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_MODEL", "gpt-4")

        result = _load_env_config()
        assert result == {"llm": {"model": "gpt-4"}}

    def test_loads_chapgent_max_output_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Loads CHAPGENT_MAX_OUTPUT_TOKENS as integer."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_MAX_OUTPUT_TOKENS", "8192")

        result = _load_env_config()
        assert result == {"llm": {"max_output_tokens": 8192}}

    def test_api_key_priority_chapgent_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_API_KEY takes priority over others."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_API_KEY", "chapgent-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        result = _load_env_config()
        assert result["llm"]["api_key"] == "chapgent-key"

    def test_api_key_priority_anthropic_second(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_API_KEY used when CHAPGENT_API_KEY not set."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        result = _load_env_config()
        assert result["llm"]["api_key"] == "anthropic-key"

    def test_api_key_priority_openai_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENAI_API_KEY used as last fallback."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        result = _load_env_config()
        assert result["llm"]["api_key"] == "openai-key"

    def test_loads_multiple_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Loads multiple env vars at once."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_MODEL", "claude-3")
        monkeypatch.setenv("CHAPGENT_PROVIDER", "anthropic")
        monkeypatch.setenv("CHAPGENT_MAX_OUTPUT_TOKENS", "2048")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        result = _load_env_config()
        assert result["llm"]["model"] == "claude-3"
        assert result["llm"]["provider"] == "anthropic"
        assert result["llm"]["max_output_tokens"] == 2048
        assert result["llm"]["api_key"] == "test-key"


class TestLoadConfigWithEnv:
    """Tests for load_config with environment variables."""

    @pytest.mark.asyncio
    async def test_env_vars_override_config_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables override config file values."""
        # Clear env vars first
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        # Create config file with model
        config_path = tmp_path / "config.toml"
        config_data = {"llm": {"model": "file-model"}}
        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        # Set env var
        monkeypatch.setenv("CHAPGENT_MODEL", "env-model")

        settings = await load_config(
            user_config_path=config_path,
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.model == "env-model"

    @pytest.mark.asyncio
    async def test_load_env_false_skips_env_vars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_env=False ignores environment variables."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        # Create config file
        config_path = tmp_path / "config.toml"
        config_data = {"llm": {"model": "file-model"}}
        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        # Set env var (should be ignored)
        monkeypatch.setenv("CHAPGENT_MODEL", "env-model")

        settings = await load_config(
            user_config_path=config_path,
            project_config_path=tmp_path / "no_exist.toml",
            load_env=False,
        )

        assert settings.llm.model == "file-model"

    @pytest.mark.asyncio
    async def test_env_api_key_sets_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key from env var is set in settings."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        settings = await load_config(
            user_config_path=tmp_path / "no_exist.toml",
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.api_key == "sk-test-key"

    @pytest.mark.asyncio
    async def test_priority_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full priority chain: env > project > user > defaults."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        user_config_path = tmp_path / "user.toml"
        project_config_path = tmp_path / "project.toml"

        # User config sets provider and model
        with open(user_config_path, "wb") as f:
            tomli_w.dump({"llm": {"provider": "openai", "model": "user-model"}}, f)

        # Project config sets model (overrides user)
        with open(project_config_path, "wb") as f:
            tomli_w.dump({"llm": {"model": "project-model"}}, f)

        # Env var sets provider (overrides all) - use a different valid provider
        monkeypatch.setenv("CHAPGENT_PROVIDER", "groq")

        settings = await load_config(
            user_config_path=user_config_path,
            project_config_path=project_config_path,
            load_env=True,
        )

        # Env overrides user for provider
        assert settings.llm.provider == "groq"
        # Project overrides user for model
        assert settings.llm.model == "project-model"
        # Default for max_output_tokens (not set anywhere)
        assert settings.llm.max_output_tokens == LLMSettings.model_fields["max_output_tokens"].default


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz_"))
    @settings(max_examples=30)
    def test_set_nested_value_roundtrip(self, key: str) -> None:
        """Setting a value and retrieving it works correctly."""
        data: dict[str, Any] = {}
        value = "test_value"
        path = f"section.{key}"

        _set_nested_value(data, path, value)

        assert data["section"][key] == value

    @given(st.integers(min_value=MAX_OUTPUT_TOKENS_MIN, max_value=MAX_OUTPUT_TOKENS_MAX))
    @settings(max_examples=20)
    def test_max_output_tokens_conversion(self, num: int) -> None:
        """Integer strings are converted for max_output_tokens."""
        result = _convert_env_value(str(num), "llm.max_output_tokens")
        assert result == num

    @given(st.sampled_from(["true", "True", "TRUE", "1", "yes", "on"]))
    @settings(max_examples=10)
    def test_boolean_true_variants(self, value: str) -> None:
        """Various true-like strings convert to True."""
        result = _convert_env_value(value, "permissions.auto_approve_low_risk")
        assert result is True


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_env_var_not_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string env var is not loaded (treated as unset)."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        # Empty string should be falsy
        monkeypatch.setenv("CHAPGENT_MODEL", "")

        result = _load_env_config()
        # Empty string is falsy, so should not be in result
        assert "llm" not in result or "model" not in result.get("llm", {})

    def test_whitespace_env_var_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace-only env var is loaded (non-empty)."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_MODEL", "   ")

        result = _load_env_config()
        # Whitespace is truthy
        assert result["llm"]["model"] == "   "

    def test_special_characters_in_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API keys with special characters are preserved."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        special_key = "sk-ant-abc123!@#$%^&*()_+-=[]{}|;':\",./<>?"
        monkeypatch.setenv("ANTHROPIC_API_KEY", special_key)

        result = _load_env_config()
        assert result["llm"]["api_key"] == special_key

    @pytest.mark.asyncio
    async def test_no_config_files_only_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Works when only env vars are set (no config files)."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_MODEL", "test-model")
        monkeypatch.setenv("CHAPGENT_API_KEY", "test-key")

        settings = await load_config(
            user_config_path=tmp_path / "no_exist.toml",
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.model == "test-model"
        assert settings.llm.api_key == "test-key"
        # Defaults still work
        assert settings.llm.provider == LLMSettings.model_fields["provider"].default
        assert settings.llm.max_output_tokens == LLMSettings.model_fields["max_output_tokens"].default


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_realistic_usage_pattern(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test realistic usage with user config and API key in env."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        # User config sets preferences
        user_config = tmp_path / "user.toml"
        with open(user_config, "wb") as f:
            tomli_w.dump(
                {
                    "llm": {"model": "claude-sonnet-4-20250514", "max_output_tokens": 8192},
                    "tui": {"theme": "gruvbox", "show_tool_panel": True},
                },
                f,
            )

        # API key from environment (common pattern for secrets)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-production-key")

        settings = await load_config(
            user_config_path=user_config,
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        # File settings applied
        assert settings.llm.model == "claude-sonnet-4-20250514"
        assert settings.llm.max_output_tokens == 8192
        assert settings.tui.theme == "gruvbox"
        assert settings.tui.show_tool_panel is True

        # Env var for secret
        assert settings.llm.api_key == "sk-ant-production-key"

        # Defaults for unset
        assert settings.llm.provider == LLMSettings.model_fields["provider"].default
        expected = PermissionSettings.model_fields["auto_approve_low_risk"].default
        assert settings.permissions.auto_approve_low_risk == expected


# =============================================================================
# Phase 7: LiteLLM Gateway Environment Variable Tests
# =============================================================================


class TestBaseUrlEnvVars:
    """Tests for base_url environment variable support."""

    def test_chapgent_base_url_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_BASE_URL is loaded into config."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_BASE_URL", "http://localhost:4000")

        result = _load_env_config()
        assert result["llm"]["base_url"] == "http://localhost:4000"

    def test_anthropic_base_url_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_BASE_URL is loaded into config."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://proxy.example.com")

        result = _load_env_config()
        assert result["llm"]["base_url"] == "http://proxy.example.com"

    def test_chapgent_base_url_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_BASE_URL takes priority over ANTHROPIC_BASE_URL."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_BASE_URL", "http://chapgent-proxy:4000")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://anthropic-proxy:4000")

        result = _load_env_config()
        assert result["llm"]["base_url"] == "http://chapgent-proxy:4000"

    @pytest.mark.asyncio
    async def test_base_url_env_overrides_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Base URL from env overrides config file value."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        config_path = tmp_path / "config.toml"
        config_data = {"llm": {"base_url": "http://file-proxy:4000"}}
        with open(config_path, "wb") as f:
            tomli_w.dump(config_data, f)

        monkeypatch.setenv("CHAPGENT_BASE_URL", "http://env-proxy:4000")

        settings = await load_config(
            user_config_path=config_path,
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.base_url == "http://env-proxy:4000"


class TestExtraHeadersEnvVars:
    """Tests for extra_headers environment variable support."""

    def test_chapgent_extra_headers_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_EXTRA_HEADERS is loaded as JSON dict."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_EXTRA_HEADERS", '{"x-api-key": "test-key"}')

        result = _load_env_config()
        assert result["llm"]["extra_headers"] == {"x-api-key": "test-key"}

    def test_anthropic_custom_headers_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_CUSTOM_HEADERS is loaded as JSON dict."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", '{"Authorization": "Bearer token123"}')

        result = _load_env_config()
        assert result["llm"]["extra_headers"] == {"Authorization": "Bearer token123"}

    def test_chapgent_extra_headers_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_EXTRA_HEADERS takes priority over ANTHROPIC_CUSTOM_HEADERS."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_EXTRA_HEADERS", '{"x-chapgent": "value1"}')
        monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", '{"x-anthropic": "value2"}')

        result = _load_env_config()
        assert result["llm"]["extra_headers"] == {"x-chapgent": "value1"}

    def test_extra_headers_with_multiple_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Extra headers can contain multiple key-value pairs."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        headers = '{"x-litellm-api-key": "Bearer sk-test", "Authorization": "Bearer oauth"}'
        monkeypatch.setenv("CHAPGENT_EXTRA_HEADERS", headers)

        result = _load_env_config()
        assert result["llm"]["extra_headers"] == {
            "x-litellm-api-key": "Bearer sk-test",
            "Authorization": "Bearer oauth",
        }

    @pytest.mark.asyncio
    async def test_extra_headers_env_to_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Extra headers from env are set in Settings."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_EXTRA_HEADERS", '{"x-custom": "header-value"}')

        settings = await load_config(
            user_config_path=tmp_path / "no_exist.toml",
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.extra_headers == {"x-custom": "header-value"}


class TestOAuthTokenEnvVars:
    """Tests for oauth_token environment variable support."""

    def test_chapgent_oauth_token_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_OAUTH_TOKEN is loaded into config."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_OAUTH_TOKEN", "chapgent-oauth-token-12345")

        result = _load_env_config()
        assert result["llm"]["oauth_token"] == "chapgent-oauth-token-12345"

    def test_anthropic_oauth_token_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_OAUTH_TOKEN is loaded into config."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("ANTHROPIC_OAUTH_TOKEN", "anthropic-oauth-token-12345")

        result = _load_env_config()
        assert result["llm"]["oauth_token"] == "anthropic-oauth-token-12345"

    def test_chapgent_oauth_token_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CHAPGENT_OAUTH_TOKEN takes priority over ANTHROPIC_OAUTH_TOKEN."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_OAUTH_TOKEN", "chapgent-token")
        monkeypatch.setenv("ANTHROPIC_OAUTH_TOKEN", "anthropic-token")

        result = _load_env_config()
        assert result["llm"]["oauth_token"] == "chapgent-token"

    @pytest.mark.asyncio
    async def test_oauth_token_env_to_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """OAuth token from env is set in Settings."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("CHAPGENT_OAUTH_TOKEN", "test-oauth-token-123456")

        settings = await load_config(
            user_config_path=tmp_path / "no_exist.toml",
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.oauth_token == "test-oauth-token-123456"


class TestGatewayConfigIntegration:
    """Integration tests for full LiteLLM gateway configuration via env vars."""

    @pytest.mark.asyncio
    async def test_full_gateway_env_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test complete gateway configuration from env vars."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        # Set all gateway-related env vars
        monkeypatch.setenv("CHAPGENT_BASE_URL", "http://localhost:4000")
        monkeypatch.setenv("CHAPGENT_EXTRA_HEADERS", '{"x-litellm-api-key": "Bearer sk-litellm"}')
        monkeypatch.setenv("CHAPGENT_OAUTH_TOKEN", "oauth-test-token-12345")
        monkeypatch.setenv("CHAPGENT_MODEL", "anthropic-claude")

        settings = await load_config(
            user_config_path=tmp_path / "no_exist.toml",
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.base_url == "http://localhost:4000"
        assert settings.llm.extra_headers == {"x-litellm-api-key": "Bearer sk-litellm"}
        assert settings.llm.oauth_token == "oauth-test-token-12345"
        assert settings.llm.model == "anthropic-claude"

    @pytest.mark.asyncio
    async def test_anthropic_env_vars_for_claude_max(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ANTHROPIC_* env vars for Claude Max subscription."""
        for var in ENV_MAPPINGS:
            monkeypatch.delenv(var, raising=False)

        # Simulate Claude Max setup with ANTHROPIC_* env vars
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://litellm-proxy:4000")
        monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", '{"Authorization": "Bearer claude-max-token"}')
        monkeypatch.setenv("ANTHROPIC_OAUTH_TOKEN", "claude-max-oauth-12345")

        settings = await load_config(
            user_config_path=tmp_path / "no_exist.toml",
            project_config_path=tmp_path / "no_exist.toml",
            load_env=True,
        )

        assert settings.llm.base_url == "http://litellm-proxy:4000"
        assert settings.llm.extra_headers == {"Authorization": "Bearer claude-max-token"}
        assert settings.llm.oauth_token == "claude-max-oauth-12345"
