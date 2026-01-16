import pytest
import tomli_w

from pygent.config.loader import load_config
from pygent.config.settings import Settings


# Test Defaults
def test_default_settings():
    settings = Settings()
    assert settings.llm.provider == "anthropic"
    assert settings.permissions.auto_approve_low_risk is True
    assert settings.tui.theme == "textual-dark"


# Test TOML Loading
@pytest.mark.asyncio
async def test_load_config_defaults(tmp_path):
    # No config files exist
    settings = await load_config(
        user_config_path=tmp_path / "user_config.toml",
        project_config_path=tmp_path / "project_config.toml",
    )
    assert settings.llm.provider == "anthropic"


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
    assert settings.llm.max_tokens == 4096


@pytest.mark.asyncio
async def test_load_project_config_overrides_user(tmp_path):
    user_config_path = tmp_path / "user_config.toml"
    project_config_path = tmp_path / "project_config.toml"

    # User config
    user_data = {"llm": {"provider": "openai", "max_tokens": 1000}, "tui": {"theme": "light"}}
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
    assert settings.llm.max_tokens == 1000
    assert settings.tui.theme == "light"

    # Project overrides Default
    assert settings.permissions.session_override_allowed is False

    # Check default remaining untouched
    assert settings.permissions.auto_approve_low_risk is True
