import pytest
import tomli_w

from chapgent.config.loader import load_config
from chapgent.config.settings import LLMSettings, PermissionSettings, Settings, TUISettings


# Test Defaults
def test_default_settings():
    settings = Settings()
    assert settings.llm.provider == LLMSettings.model_fields["provider"].default
    expected_auto_approve = PermissionSettings.model_fields["auto_approve_low_risk"].default
    assert settings.permissions.auto_approve_low_risk == expected_auto_approve
    assert settings.tui.theme == TUISettings.model_fields["theme"].default


# Test TOML Loading
@pytest.mark.asyncio
async def test_load_config_defaults(tmp_path):
    # No config files exist
    settings = await load_config(
        user_config_path=tmp_path / "user_config.toml",
        project_config_path=tmp_path / "project_config.toml",
    )
    assert settings.llm.provider == LLMSettings.model_fields["provider"].default


@pytest.mark.asyncio
async def test_load_user_config(tmp_path):
    user_config_path = tmp_path / "user_config.toml"
    config_data = {"llm": {"provider": "openai", "model": "gpt-4"}}
    with open(user_config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=tmp_path / "project_config.toml",
    )

    assert settings.llm.provider == "openai"
    assert settings.llm.model == "gpt-4"
    # Should keep defaults for others
    assert settings.llm.max_output_tokens == LLMSettings.model_fields["max_output_tokens"].default


@pytest.mark.asyncio
async def test_load_project_config_overrides_user(tmp_path):
    user_config_path = tmp_path / "user_config.toml"
    project_config_path = tmp_path / "project_config.toml"

    # User config
    user_data = {"llm": {"provider": "openai", "max_output_tokens": 1000}, "tui": {"theme": "textual-light"}}
    with open(user_config_path, "wb") as f:
        tomli_w.dump(user_data, f)

    # Project config (should override user)
    project_data = {"llm": {"provider": "azure"}, "permissions": {"session_override_allowed": False}}
    with open(project_config_path, "wb") as f:
        tomli_w.dump(project_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=project_config_path,
    )

    # Project overrides User
    assert settings.llm.provider == "azure"

    # User overrides Default (if not in Project)
    assert settings.llm.max_output_tokens == 1000
    assert settings.tui.theme == "textual-light"

    # Project overrides Default
    assert settings.permissions.session_override_allowed is False

    # Check default remaining untouched
    expected_auto_approve = PermissionSettings.model_fields["auto_approve_low_risk"].default
    assert settings.permissions.auto_approve_low_risk == expected_auto_approve


# =============================================================================
# Phase 7: LiteLLM Gateway TOML Config Tests
# =============================================================================


@pytest.mark.asyncio
async def test_load_base_url_from_toml(tmp_path):
    """Test loading base_url from TOML config file."""
    user_config_path = tmp_path / "user_config.toml"
    config_data = {"llm": {"base_url": "http://localhost:4000"}}
    with open(user_config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=tmp_path / "project_config.toml",
    )

    assert settings.llm.base_url == "http://localhost:4000"


@pytest.mark.asyncio
async def test_load_extra_headers_from_toml(tmp_path):
    """Test loading extra_headers from TOML config file."""
    user_config_path = tmp_path / "user_config.toml"
    config_data = {
        "llm": {
            "extra_headers": {
                "x-litellm-api-key": "Bearer sk-litellm",
                "Authorization": "Bearer oauth-token",
            }
        }
    }
    with open(user_config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=tmp_path / "project_config.toml",
    )

    assert settings.llm.extra_headers == {
        "x-litellm-api-key": "Bearer sk-litellm",
        "Authorization": "Bearer oauth-token",
    }


@pytest.mark.asyncio
async def test_load_oauth_token_from_toml(tmp_path):
    """Test loading oauth_token from TOML config file."""
    user_config_path = tmp_path / "user_config.toml"
    config_data = {"llm": {"oauth_token": "oauth-test-token-12345"}}
    with open(user_config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=tmp_path / "project_config.toml",
    )

    assert settings.llm.oauth_token == "oauth-test-token-12345"


@pytest.mark.asyncio
async def test_full_gateway_config_from_toml(tmp_path):
    """Test loading complete gateway configuration from TOML."""
    user_config_path = tmp_path / "user_config.toml"
    config_data = {
        "llm": {
            "model": "anthropic-claude",
            "base_url": "http://litellm-proxy:4000",
            "extra_headers": {"x-custom": "header-value"},
            "oauth_token": "full-oauth-token-12345",
        }
    }
    with open(user_config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=tmp_path / "project_config.toml",
    )

    assert settings.llm.model == "anthropic-claude"
    assert settings.llm.base_url == "http://litellm-proxy:4000"
    assert settings.llm.extra_headers == {"x-custom": "header-value"}
    assert settings.llm.oauth_token == "full-oauth-token-12345"


@pytest.mark.asyncio
async def test_project_config_overrides_gateway_settings(tmp_path):
    """Test that project config overrides user gateway settings."""
    user_config_path = tmp_path / "user_config.toml"
    project_config_path = tmp_path / "project_config.toml"

    # User config sets base_url
    user_data = {"llm": {"base_url": "http://user-proxy:4000"}}
    with open(user_config_path, "wb") as f:
        tomli_w.dump(user_data, f)

    # Project config overrides base_url
    project_data = {"llm": {"base_url": "http://project-proxy:4000"}}
    with open(project_config_path, "wb") as f:
        tomli_w.dump(project_data, f)

    settings = await load_config(
        user_config_path=user_config_path,
        project_config_path=project_config_path,
    )

    assert settings.llm.base_url == "http://project-proxy:4000"
