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
