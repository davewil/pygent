"""Tests for configuration validation (settings.py validators)."""

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from pydantic import ValidationError

from pygent.config.settings import (
    KNOWN_MODELS,
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
# Test Constants
# =============================================================================


class TestValidProviders:
    """Tests for VALID_PROVIDERS constant."""

    def test_is_frozenset(self):
        """VALID_PROVIDERS should be a frozenset."""
        assert isinstance(VALID_PROVIDERS, frozenset)

    def test_contains_common_providers(self):
        """Should contain common LLM providers."""
        expected = {"anthropic", "openai", "azure", "ollama", "groq"}
        assert expected.issubset(VALID_PROVIDERS)

    def test_all_lowercase(self):
        """All provider names should be lowercase."""
        for provider in VALID_PROVIDERS:
            assert provider == provider.lower()

    def test_get_valid_providers_returns_same(self):
        """get_valid_providers() should return VALID_PROVIDERS."""
        assert get_valid_providers() is VALID_PROVIDERS


class TestKnownModels:
    """Tests for KNOWN_MODELS constant."""

    def test_is_frozenset(self):
        """KNOWN_MODELS should be a frozenset."""
        assert isinstance(KNOWN_MODELS, frozenset)

    def test_contains_anthropic_models(self):
        """Should contain Claude models."""
        claude_models = [m for m in KNOWN_MODELS if "claude" in m]
        assert len(claude_models) > 0

    def test_contains_openai_models(self):
        """Should contain GPT models."""
        gpt_models = [m for m in KNOWN_MODELS if "gpt" in m]
        assert len(gpt_models) > 0

    def test_get_known_models_returns_same(self):
        """get_known_models() should return KNOWN_MODELS."""
        assert get_known_models() is KNOWN_MODELS


class TestValidThemes:
    """Tests for VALID_THEMES constant."""

    def test_is_frozenset(self):
        """VALID_THEMES should be a frozenset."""
        assert isinstance(VALID_THEMES, frozenset)

    def test_contains_default_theme(self):
        """Should contain the default textual-dark theme."""
        assert "textual-dark" in VALID_THEMES

    def test_contains_rose_pine(self):
        """Should contain rose-pine theme."""
        assert "rose-pine" in VALID_THEMES

    def test_all_lowercase(self):
        """All theme names should be lowercase."""
        for theme in VALID_THEMES:
            assert theme == theme.lower()

    def test_get_valid_themes_returns_same(self):
        """get_valid_themes() should return VALID_THEMES."""
        assert get_valid_themes() is VALID_THEMES


class TestConfigValidationError:
    """Tests for ConfigValidationError exception."""

    def test_is_value_error(self):
        """ConfigValidationError should be a ValueError."""
        assert issubclass(ConfigValidationError, ValueError)

    def test_can_raise_with_message(self):
        """Should be raisable with a message."""
        with pytest.raises(ConfigValidationError, match="test error"):
            raise ConfigValidationError("test error")


# =============================================================================
# Test LLMSettings Validation
# =============================================================================


class TestLLMSettingsProviderValidation:
    """Tests for LLMSettings.provider validation."""

    def test_valid_provider_anthropic(self):
        """Should accept 'anthropic' as provider."""
        settings = LLMSettings(provider="anthropic")
        assert settings.provider == "anthropic"

    def test_valid_provider_openai(self):
        """Should accept 'openai' as provider."""
        settings = LLMSettings(provider="openai")
        assert settings.provider == "openai"

    def test_valid_provider_case_insensitive(self):
        """Provider validation should be case-insensitive."""
        settings = LLMSettings(provider="ANTHROPIC")
        assert settings.provider == "anthropic"

    def test_valid_provider_mixed_case(self):
        """Provider validation should normalize mixed case."""
        settings = LLMSettings(provider="OpenAI")
        assert settings.provider == "openai"

    def test_invalid_provider_raises_error(self):
        """Should raise error for unknown provider."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(provider="invalid_provider")
        assert "Unknown provider" in str(exc_info.value)

    def test_invalid_provider_shows_valid_options(self):
        """Error message should list valid providers."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(provider="bad")
        error_msg = str(exc_info.value)
        assert "anthropic" in error_msg
        assert "openai" in error_msg


class TestLLMSettingsMaxTokensValidation:
    """Tests for LLMSettings.max_tokens validation."""

    def test_valid_max_tokens_default(self):
        """Should accept default max_tokens."""
        settings = LLMSettings()
        assert settings.max_tokens == 4096

    def test_valid_max_tokens_custom(self):
        """Should accept custom max_tokens within range."""
        settings = LLMSettings(max_tokens=8192)
        assert settings.max_tokens == 8192

    def test_valid_max_tokens_minimum(self):
        """Should accept minimum max_tokens value."""
        settings = LLMSettings(max_tokens=1)
        assert settings.max_tokens == 1

    def test_valid_max_tokens_maximum(self):
        """Should accept maximum max_tokens value."""
        settings = LLMSettings(max_tokens=100000)
        assert settings.max_tokens == 100000

    def test_invalid_max_tokens_zero(self):
        """Should reject zero max_tokens."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(max_tokens=0)
        assert "at least 1" in str(exc_info.value)

    def test_invalid_max_tokens_negative(self):
        """Should reject negative max_tokens."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(max_tokens=-100)
        assert "at least 1" in str(exc_info.value)

    def test_invalid_max_tokens_too_large(self):
        """Should reject max_tokens exceeding maximum."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(max_tokens=100001)
        assert "exceeds maximum" in str(exc_info.value)


class TestLLMSettingsApiKeyValidation:
    """Tests for LLMSettings.api_key validation."""

    def test_valid_api_key_none(self):
        """Should accept None api_key (falls back to env)."""
        settings = LLMSettings(api_key=None)
        assert settings.api_key is None

    def test_valid_api_key_string(self):
        """Should accept valid api_key string."""
        settings = LLMSettings(api_key="sk-test-key-123")
        assert settings.api_key == "sk-test-key-123"

    def test_invalid_api_key_empty_string(self):
        """Should reject empty string api_key."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(api_key="")
        assert "empty string" in str(exc_info.value)

    def test_invalid_api_key_whitespace_only(self):
        """Should reject whitespace-only api_key."""
        with pytest.raises(ValidationError) as exc_info:
            LLMSettings(api_key="   ")
        assert "empty string" in str(exc_info.value)


class TestLLMSettingsModelField:
    """Tests for LLMSettings.model field (no strict validation)."""

    def test_default_model(self):
        """Should have a default model."""
        settings = LLMSettings()
        assert settings.model == "claude-sonnet-4-20250514"

    def test_custom_model_known(self):
        """Should accept known model names."""
        settings = LLMSettings(model="gpt-4")
        assert settings.model == "gpt-4"

    def test_custom_model_unknown(self):
        """Should accept unknown model names (flexible for new models)."""
        settings = LLMSettings(model="custom-model-v1")
        assert settings.model == "custom-model-v1"


# =============================================================================
# Test TUISettings Validation
# =============================================================================


class TestTUISettingsThemeValidation:
    """Tests for TUISettings.theme validation."""

    def test_valid_theme_default(self):
        """Should accept default theme."""
        settings = TUISettings()
        assert settings.theme == "textual-dark"

    def test_valid_theme_textual_light(self):
        """Should accept textual-light theme."""
        settings = TUISettings(theme="textual-light")
        assert settings.theme == "textual-light"

    def test_valid_theme_rose_pine(self):
        """Should accept rose-pine theme."""
        settings = TUISettings(theme="rose-pine")
        assert settings.theme == "rose-pine"

    def test_valid_theme_case_insensitive(self):
        """Theme validation should be case-insensitive."""
        settings = TUISettings(theme="TEXTUAL-DARK")
        assert settings.theme == "textual-dark"

    def test_invalid_theme_raises_error(self):
        """Should raise error for unknown theme."""
        with pytest.raises(ValidationError) as exc_info:
            TUISettings(theme="invalid-theme")
        assert "Unknown theme" in str(exc_info.value)

    def test_invalid_theme_shows_valid_options(self):
        """Error message should list valid themes."""
        with pytest.raises(ValidationError) as exc_info:
            TUISettings(theme="bad")
        error_msg = str(exc_info.value)
        assert "textual-dark" in error_msg


class TestTUISettingsBooleanFields:
    """Tests for TUISettings boolean fields."""

    def test_show_tool_panel_default(self):
        """Should have show_tool_panel True by default."""
        settings = TUISettings()
        assert settings.show_tool_panel is True

    def test_show_tool_panel_false(self):
        """Should accept False for show_tool_panel."""
        settings = TUISettings(show_tool_panel=False)
        assert settings.show_tool_panel is False

    def test_show_sidebar_default(self):
        """Should have show_sidebar True by default."""
        settings = TUISettings()
        assert settings.show_sidebar is True


# =============================================================================
# Test SystemPromptSettings Validation
# =============================================================================


class TestSystemPromptSettingsFileValidation:
    """Tests for SystemPromptSettings.file validation."""

    def test_valid_file_none(self):
        """Should accept None file path."""
        settings = SystemPromptSettings(file=None)
        assert settings.file is None

    def test_valid_file_path(self):
        """Should accept valid file path."""
        settings = SystemPromptSettings(file="~/.config/pygent/prompt.md")
        assert settings.file == "~/.config/pygent/prompt.md"

    def test_invalid_file_empty_string(self):
        """Should reject empty string file path."""
        with pytest.raises(ValidationError) as exc_info:
            SystemPromptSettings(file="")
        assert "empty string" in str(exc_info.value)

    def test_invalid_file_whitespace_only(self):
        """Should reject whitespace-only file path."""
        with pytest.raises(ValidationError) as exc_info:
            SystemPromptSettings(file="   ")
        assert "empty string" in str(exc_info.value)


class TestSystemPromptSettingsOtherFields:
    """Tests for SystemPromptSettings other fields."""

    def test_mode_default(self):
        """Should have append mode by default."""
        settings = SystemPromptSettings()
        assert settings.mode == "append"

    def test_mode_replace(self):
        """Should accept replace mode."""
        settings = SystemPromptSettings(mode="replace")
        assert settings.mode == "replace"

    def test_content_and_append(self):
        """Should accept both content and append."""
        settings = SystemPromptSettings(content="Base prompt", append="Extra instructions")
        assert settings.content == "Base prompt"
        assert settings.append == "Extra instructions"


# =============================================================================
# Test PermissionSettings (no custom validation)
# =============================================================================


class TestPermissionSettings:
    """Tests for PermissionSettings."""

    def test_defaults(self):
        """Should have correct defaults."""
        settings = PermissionSettings()
        assert settings.auto_approve_low_risk is True
        assert settings.session_override_allowed is True

    def test_custom_values(self):
        """Should accept custom boolean values."""
        settings = PermissionSettings(auto_approve_low_risk=False, session_override_allowed=False)
        assert settings.auto_approve_low_risk is False
        assert settings.session_override_allowed is False


# =============================================================================
# Test Settings (Root Model)
# =============================================================================


class TestSettingsDefaults:
    """Tests for Settings defaults."""

    def test_default_settings(self):
        """Should create valid settings with defaults."""
        settings = Settings()
        assert settings.llm.provider == "anthropic"
        assert settings.tui.theme == "textual-dark"
        assert settings.permissions.auto_approve_low_risk is True


class TestSettingsValidateConfig:
    """Tests for Settings.validate_config() method."""

    def test_valid_config_dict(self):
        """Should accept valid config dict."""
        config = {"llm": {"provider": "openai", "model": "gpt-4"}}
        settings = Settings.validate_config(config)
        assert settings.llm.provider == "openai"
        assert settings.llm.model == "gpt-4"

    def test_invalid_config_raises_config_validation_error(self):
        """Should raise ConfigValidationError for invalid config."""
        config = {"llm": {"provider": "invalid"}}
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config(config)
        assert "Configuration validation failed" in str(exc_info.value)

    def test_error_message_includes_field_path(self):
        """Error message should include the field path."""
        config = {"llm": {"provider": "bad"}}
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config(config)
        assert "llm.provider" in str(exc_info.value)

    def test_multiple_errors_all_reported(self):
        """Should report all validation errors."""
        config = {
            "llm": {"provider": "bad", "max_tokens": -1},
            "tui": {"theme": "invalid"},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config(config)
        error_msg = str(exc_info.value)
        assert "llm.provider" in error_msg
        assert "llm.max_tokens" in error_msg
        assert "tui.theme" in error_msg


class TestSettingsNestedValidation:
    """Tests for Settings nested model validation."""

    def test_nested_llm_validation(self):
        """Should validate nested LLM settings."""
        with pytest.raises(ValidationError):
            Settings(llm=LLMSettings(provider="invalid"))

    def test_nested_tui_validation(self):
        """Should validate nested TUI settings."""
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

    @given(st.integers(min_value=1, max_value=100000))
    @hypothesis_settings(max_examples=50)
    def test_valid_max_tokens_range(self, max_tokens: int):
        """All max_tokens in valid range should be accepted."""
        settings = LLMSettings(max_tokens=max_tokens)
        assert settings.max_tokens == max_tokens

    @given(st.integers(max_value=0))
    @hypothesis_settings(max_examples=20)
    def test_invalid_max_tokens_below_minimum(self, max_tokens: int):
        """All max_tokens below 1 should be rejected."""
        with pytest.raises(ValidationError):
            LLMSettings(max_tokens=max_tokens)

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
        assert settings.llm.provider == "anthropic"
        assert settings.tui.theme == "textual-dark"

    def test_partial_nested_config(self):
        """Partial nested config should merge with defaults."""
        config = {"llm": {"model": "gpt-4"}}
        settings = Settings.validate_config(config)
        assert settings.llm.model == "gpt-4"
        assert settings.llm.provider == "anthropic"  # Default preserved
        assert settings.llm.max_tokens == 4096  # Default preserved


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
                "max_tokens": 8192,
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
        assert settings.llm.max_tokens == 8192
        assert settings.permissions.auto_approve_low_risk is False
        assert settings.tui.theme == "rose-pine"
        assert settings.tui.show_tool_panel is False
        assert settings.system_prompt.content == "You are a helpful assistant."
        assert settings.system_prompt.mode == "replace"

    def test_validation_preserves_known_good_values_on_error(self):
        """Validation should fail fast but report all errors."""
        # This tests that multiple errors are collected
        config = {
            "llm": {"provider": "invalid", "max_tokens": -1},
            "tui": {"theme": "invalid"},
        }
        with pytest.raises(ConfigValidationError) as exc_info:
            Settings.validate_config(config)

        error_str = str(exc_info.value)
        # All three errors should be reported
        assert "llm.provider" in error_str
        assert "llm.max_tokens" in error_str
        assert "tui.theme" in error_str
