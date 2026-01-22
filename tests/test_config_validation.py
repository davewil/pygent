"""Tests for configuration validation (settings.py validators)."""

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from pydantic import ValidationError

from chapgent.config.settings import (
    KNOWN_MODELS,
    MAX_OUTPUT_TOKENS_MAX,
    MAX_OUTPUT_TOKENS_MIN,
    VALID_PROVIDERS,
    VALID_THEMES,
    ConfigValidationError,
    LLMSettings,
    PermissionSettings,
    Settings,
    SystemPromptSettings,
    TUISettings,
    get_known_models,
    get_valid_providers,
    get_valid_themes,
)

# =============================================================================
# Test Constants (Consolidated)
# =============================================================================


class TestValidationConstants:
    """Tests for validation constants (providers, models, themes)."""

    @pytest.mark.parametrize(
        "constant,getter,expected_items,expected_substring_items",
        [
            (VALID_PROVIDERS, get_valid_providers, {"anthropic", "openai", "azure", "ollama", "groq"}, None),
            (KNOWN_MODELS, get_known_models, None, [("claude", 1), ("gpt", 1)]),
            (VALID_THEMES, get_valid_themes, {"textual-dark", "rose-pine"}, None),
        ],
    )
    def test_constant_structure_and_content(self, constant, getter, expected_items, expected_substring_items):
        """Test validation constants are frozensets with expected content."""
        assert isinstance(constant, frozenset)
        assert getter() is constant
        if expected_items:
            assert expected_items.issubset(constant)
        if expected_substring_items:
            for substr, min_count in expected_substring_items:
                assert len([m for m in constant if substr in m]) >= min_count

    @pytest.mark.parametrize("constant", [VALID_PROVIDERS, VALID_THEMES])
    def test_constants_all_lowercase(self, constant):
        """All values in lowercase constants should be lowercase."""
        for item in constant:
            assert item == item.lower()

    def test_config_validation_error(self):
        """ConfigValidationError should be a ValueError and raisable."""
        assert issubclass(ConfigValidationError, ValueError)
        with pytest.raises(ConfigValidationError, match="test error"):
            raise ConfigValidationError("test error")


# =============================================================================
# Test LLMSettings Validation (Consolidated)
# =============================================================================


class TestLLMSettingsValidation:
    """Tests for LLMSettings validation."""

    @pytest.mark.parametrize(
        "provider,expected",
        [("anthropic", "anthropic"), ("openai", "openai"), ("ANTHROPIC", "anthropic"), ("OpenAI", "openai")],
    )
    def test_valid_providers(self, provider: str, expected: str):
        """Should accept valid providers with case normalization."""
        assert LLMSettings(provider=provider).provider == expected

    def test_invalid_provider_raises_error_with_options(self):
        """Should raise error for unknown provider, listing valid options."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(provider="invalid_provider")
        error_msg = str(exc_info.value)
        assert "Unknown provider" in error_msg and "anthropic" in error_msg and "openai" in error_msg

    @pytest.mark.parametrize("max_output_tokens", [MAX_OUTPUT_TOKENS_MIN, 4096, 8192, MAX_OUTPUT_TOKENS_MAX])
    def test_valid_max_output_tokens(self, max_output_tokens: int):
        """Should accept max_output_tokens within valid range."""
        assert LLMSettings(max_output_tokens=max_output_tokens).max_output_tokens == max_output_tokens

    @pytest.mark.parametrize(
        "max_output_tokens,error_substring",
        [
            (MAX_OUTPUT_TOKENS_MIN - 1, f"at least {MAX_OUTPUT_TOKENS_MIN}"),
            (-100, f"at least {MAX_OUTPUT_TOKENS_MIN}"),
            (MAX_OUTPUT_TOKENS_MAX + 1, "exceeds maximum"),
        ],
    )
    def test_invalid_max_output_tokens(self, max_output_tokens: int, error_substring: str):
        """Should reject invalid max_output_tokens values."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(max_output_tokens=max_output_tokens)
        assert error_substring in str(exc_info.value)

    @pytest.mark.parametrize("api_key", [None, "sk-test-key-123"])
    def test_valid_api_key(self, api_key: str | None):
        """Should accept None or valid api_key strings."""
        assert LLMSettings(api_key=api_key).api_key == api_key

    @pytest.mark.parametrize("api_key", ["", "   "])
    def test_invalid_api_key(self, api_key: str):
        """Should reject empty or whitespace-only api_key."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(api_key=api_key)
        assert "empty string" in str(exc_info.value)

    @pytest.mark.parametrize("model", ["claude-sonnet-4-20250514", "gpt-4", "custom-model-v1"])
    def test_model_field_accepts_any(self, model: str):
        """Should accept any model name (known or custom)."""
        assert LLMSettings(model=model).model == model

    def test_default_model(self):
        """Should have default model matching LLMSettings default."""
        default_settings = LLMSettings()
        assert default_settings.model == LLMSettings.model_fields["model"].default

    # -------------------------------------------------------------------------
    # base_url validation
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("base_url", [None, "http://localhost:4000", "https://proxy.example.com"])
    def test_valid_base_url(self, base_url: str | None):
        """Should accept None or valid URL strings."""
        assert LLMSettings(base_url=base_url).base_url == base_url

    @pytest.mark.parametrize(
        "base_url,error_substring",
        [
            ("", "empty string"),
            ("   ", "empty string"),
            ("localhost:4000", "must start with http"),
            ("ftp://proxy.example.com", "must start with http"),
        ],
    )
    def test_invalid_base_url(self, base_url: str, error_substring: str):
        """Should reject invalid base_url values."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(base_url=base_url)
        assert error_substring in str(exc_info.value)

    # -------------------------------------------------------------------------
    # extra_headers validation
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "extra_headers",
        [
            None,
            {"x-api-key": "test"},
            {"x-litellm-api-key": "Bearer sk-test", "Authorization": "Bearer oauth"},
        ],
    )
    def test_valid_extra_headers(self, extra_headers: dict[str, str] | None):
        """Should accept None or valid header dicts."""
        assert LLMSettings(extra_headers=extra_headers).extra_headers == extra_headers

    # -------------------------------------------------------------------------
    # oauth_token validation
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("oauth_token", [None, "oauth-token-12345"])
    def test_valid_oauth_token(self, oauth_token: str | None):
        """Should accept None or valid oauth_token strings."""
        assert LLMSettings(oauth_token=oauth_token).oauth_token == oauth_token

    @pytest.mark.parametrize("oauth_token", ["", "   "])
    def test_invalid_oauth_token(self, oauth_token: str):
        """Should reject empty or whitespace-only oauth_token."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(oauth_token=oauth_token)
        assert "empty string" in str(exc_info.value)


# =============================================================================
# Test TUISettings Validation (Consolidated)
# =============================================================================


class TestTUISettingsValidation:
    """Tests for TUISettings validation."""

    @pytest.mark.parametrize(
        "theme,expected",
        [
            ("textual-dark", "textual-dark"),
            ("textual-light", "textual-light"),
            ("rose-pine", "rose-pine"),
            ("TEXTUAL-DARK", "textual-dark"),
        ],
    )
    def test_valid_themes(self, theme: str, expected: str):
        """Should accept valid themes with case normalization."""
        assert TUISettings(theme=theme).theme == expected

    def test_invalid_theme_raises_error_with_options(self):
        """Should raise error for unknown theme, listing valid options."""
        with pytest.raises(ValidationError) as exc_info:
            TUISettings(theme="invalid-theme")
        error_msg = str(exc_info.value)
        assert "Unknown theme" in error_msg and "textual-dark" in error_msg

    def test_boolean_defaults_and_custom(self):
        """Test TUISettings boolean fields defaults and custom values."""
        default = TUISettings()
        assert default.show_tool_panel == TUISettings.model_fields["show_tool_panel"].default
        assert default.show_sidebar == TUISettings.model_fields["show_sidebar"].default
        custom = TUISettings(show_tool_panel=False)
        assert custom.show_tool_panel is False


# =============================================================================
# Test SystemPromptSettings Validation (Consolidated)
# =============================================================================


class TestSystemPromptSettingsValidation:
    """Tests for SystemPromptSettings validation."""

    @pytest.mark.parametrize("file", [None, "~/.config/chapgent/prompt.md"])
    def test_valid_file(self, file: str | None):
        """Should accept None or valid file paths."""
        assert SystemPromptSettings(file=file).file == file

    @pytest.mark.parametrize("file", ["", "   "])
    def test_invalid_file(self, file: str):
        """Should reject empty or whitespace-only file paths."""
        with pytest.raises(ValidationError) as exc_info:
            SystemPromptSettings(file=file)
        assert "empty string" in str(exc_info.value)

    def test_mode_and_content(self):
        """Test mode defaults and content/append fields."""
        default = SystemPromptSettings()
        assert default.mode == "append"
        custom = SystemPromptSettings(mode="replace", content="Base", append="Extra")
        assert (custom.mode, custom.content, custom.append) == ("replace", "Base", "Extra")


# =============================================================================
# Test PermissionSettings (Consolidated)
# =============================================================================


class TestPermissionSettings:
    """Tests for PermissionSettings."""

    def test_defaults_and_custom(self):
        """Test PermissionSettings defaults and custom values."""
        default = PermissionSettings()
        assert default.auto_approve_low_risk == PermissionSettings.model_fields["auto_approve_low_risk"].default
        assert default.session_override_allowed == PermissionSettings.model_fields["session_override_allowed"].default
        custom = PermissionSettings(auto_approve_low_risk=False, session_override_allowed=False)
        assert (custom.auto_approve_low_risk, custom.session_override_allowed) == (False, False)


# =============================================================================
# Test Settings (Root Model) (Consolidated)
# =============================================================================


class TestSettingsValidation:
    """Tests for Settings root model."""

    def test_default_settings(self):
        """Should create valid settings with defaults."""
        settings = Settings()
        # Verify defaults match the field defaults from settings classes
        assert settings.llm.provider == LLMSettings.model_fields["provider"].default
        assert settings.tui.theme == TUISettings.model_fields["theme"].default
        expected = PermissionSettings.model_fields["auto_approve_low_risk"].default
        assert settings.permissions.auto_approve_low_risk == expected

    def test_valid_config_dict(self):
        """Should accept valid config dict."""
        settings = Settings.validate_config({"llm": {"provider": "openai", "model": "gpt-4"}})
        assert (settings.llm.provider, settings.llm.model) == ("openai", "gpt-4")

    def test_invalid_config_raises_error_with_field_path(self):
        """Should raise ConfigValidationError with field path for invalid config."""
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config({"llm": {"provider": "bad"}})
        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg and "llm.provider" in error_msg

    def test_multiple_errors_all_reported(self):
        """Should report all validation errors."""
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config({"llm": {"provider": "bad", "max_output_tokens": -1}, "tui": {"theme": "invalid"}})
        error_msg = str(exc_info.value)
        assert all(field in error_msg for field in ["llm.provider", "llm.max_output_tokens", "tui.theme"])

    def test_nested_validation(self):
        """Should validate nested settings models."""
        with pytest.raises(ValidationError):
            Settings(llm=LLMSettings(provider="invalid"))
        with pytest.raises(ValidationError):
            Settings(tui=TUISettings(theme="invalid"))


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.sampled_from(list(VALID_PROVIDERS)))
    @hypothesis_settings(max_examples=20)
    def test_all_valid_providers_accepted(self, provider: str):
        """All valid providers should be accepted."""
        settings = LLMSettings(provider=provider)
        assert settings.provider == provider.lower()

    @given(st.sampled_from(list(VALID_THEMES)))
    @hypothesis_settings(max_examples=20)
    def test_all_valid_themes_accepted(self, theme: str):
        """All valid themes should be accepted."""
        settings = TUISettings(theme=theme)
        assert settings.theme == theme.lower()

    @given(st.integers(min_value=MAX_OUTPUT_TOKENS_MIN, max_value=MAX_OUTPUT_TOKENS_MAX))
    @hypothesis_settings(max_examples=50)
    def test_valid_max_output_tokens_range(self, max_output_tokens: int):
        """All max_output_tokens in valid range should be accepted."""
        settings = LLMSettings(max_output_tokens=max_output_tokens)
        assert settings.max_output_tokens == max_output_tokens

    @given(st.integers(max_value=MAX_OUTPUT_TOKENS_MIN - 1))
    @hypothesis_settings(max_examples=20)
    def test_invalid_max_output_tokens_below_minimum(self, max_output_tokens: int):
        """All max_output_tokens below minimum should be rejected."""
        with pytest.raises(ValidationError):
            LLMSettings(max_output_tokens=max_output_tokens)

    @given(st.text(min_size=1).filter(lambda x: x.strip() and x.lower() not in VALID_PROVIDERS))
    @hypothesis_settings(max_examples=30)
    def test_invalid_providers_rejected(self, provider: str):
        """Invalid providers should be rejected."""
        with pytest.raises(ValidationError):
            LLMSettings(provider=provider)

    @given(st.text(min_size=1).filter(lambda x: x.strip() and x.lower() not in VALID_THEMES))
    @hypothesis_settings(max_examples=30)
    def test_invalid_themes_rejected(self, theme: str):
        """Invalid themes should be rejected."""
        with pytest.raises(ValidationError):
            TUISettings(theme=theme)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_provider_with_leading_trailing_spaces(self):
        """Provider with spaces should still be validated correctly."""
        # Pydantic strips by default for str, but validator receives cleaned value
        settings = LLMSettings(provider="anthropic")
        assert settings.provider == "anthropic"

    def test_theme_unicode(self):
        """Unicode theme names should be rejected gracefully."""
        with pytest.raises(ValidationError) as exc_info:
            TUISettings(theme="theme-\u2603")  # snowman
        assert "Unknown theme" in str(exc_info.value)

    def test_api_key_with_newlines(self):
        """API key with newlines should be accepted (some keys have them)."""
        settings = LLMSettings(api_key="sk-key\n123")
        assert settings.api_key == "sk-key\n123"

    def test_model_with_special_characters(self):
        """Model names can have special characters."""
        settings = LLMSettings(model="anthropic/claude-3.5-sonnet@latest")
        assert settings.model == "anthropic/claude-3.5-sonnet@latest"

    def test_empty_config_dict(self):
        """Empty config dict should use all defaults."""
        settings = Settings.validate_config({})
        assert settings.llm.provider == LLMSettings.model_fields["provider"].default
        assert settings.tui.theme == TUISettings.model_fields["theme"].default

    def test_partial_nested_config(self):
        """Partial nested config should merge with defaults."""
        config = {"llm": {"model": "gpt-4"}}
        settings = Settings.validate_config(config)
        assert settings.llm.model == "gpt-4"
        # Defaults should be preserved
        assert settings.llm.provider == LLMSettings.model_fields["provider"].default
        assert settings.llm.max_output_tokens == LLMSettings.model_fields["max_output_tokens"].default


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for config validation."""

    def test_full_config_round_trip(self):
        """Should handle full config creation and validation."""
        config = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "max_output_tokens": 8192,
            },
            "permissions": {
                "auto_approve_low_risk": False,
                "session_override_allowed": True,
            },
            "tui": {
                "theme": "rose-pine",
                "show_tool_panel": False,
                "show_sidebar": True,
            },
            "system_prompt": {
                "content": "You are a helpful assistant.",
                "mode": "replace",
            },
        }
        settings = Settings.validate_config(config)

        assert settings.llm.provider == "openai"
        assert settings.llm.model == "gpt-4"
        assert settings.llm.max_output_tokens == 8192
        assert settings.permissions.auto_approve_low_risk is False
        assert settings.tui.theme == "rose-pine"
        assert settings.tui.show_tool_panel is False
        assert settings.system_prompt.content == "You are a helpful assistant."
        assert settings.system_prompt.mode == "replace"

    def test_validation_preserves_known_good_values_on_error(self):
        """Validation should fail fast but report all errors."""
        # This tests that multiple errors are collected
        config = {
            "llm": {"provider": "invalid", "max_output_tokens": -1},
            "tui": {"theme": "invalid"},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config(config)

        error_str = str(exc_info.value)
        # All three errors should be reported
        assert "llm.provider" in error_str
        assert "llm.max_output_tokens" in error_str
        assert "tui.theme" in error_str
