import os
import sys
from pathlib import Path
from typing import Any, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

from .settings import Settings

# Environment variable to config path mappings
# These env vars override config file values
ENV_MAPPINGS: dict[str, str] = {
    # Pygent-specific env vars (highest priority)
    "PYGENT_MODEL": "llm.model",
    "PYGENT_API_KEY": "llm.api_key",
    "PYGENT_MAX_TOKENS": "llm.max_tokens",
    "PYGENT_PROVIDER": "llm.provider",
    # Standard API key env vars (fallback for api_key)
    "ANTHROPIC_API_KEY": "llm.api_key",
    "OPENAI_API_KEY": "llm.api_key",
}

# Priority order for API key env vars (first found wins)
API_KEY_ENV_PRIORITY = ["PYGENT_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]


def _deep_update(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Recursively update a dictionary."""
    for key, value in update.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _set_nested_value(data: dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dict using a dotted path.

    Args:
        data: The dictionary to modify.
        path: Dotted path like "llm.model" or "permissions.auto_approve_low_risk".
        value: The value to set.
    """
    keys = path.split(".")
    current = data

    # Navigate to the parent of the target key, creating dicts as needed
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Set the final value
    current[keys[-1]] = value


def _convert_env_value(value: str, path: str) -> Any:
    """Convert an environment variable string to the appropriate type.

    Args:
        value: The string value from the environment.
        path: The config path (used to determine expected type).

    Returns:
        Converted value (int, bool, or str).
    """
    # Integer fields
    if path.endswith(".max_tokens"):
        try:
            return int(value)
        except ValueError:
            return value

    # Boolean fields
    bool_paths = {
        "permissions.auto_approve_low_risk",
        "permissions.session_override_allowed",
        "tui.show_tool_panel",
        "tui.show_sidebar",
    }
    if path in bool_paths:
        return value.lower() in ("true", "1", "yes", "on")

    # Default to string
    return value


def _load_env_config() -> dict[str, Any]:
    """Load configuration values from environment variables.

    Returns:
        Dictionary of config values from environment variables.
    """
    env_config: dict[str, Any] = {}

    # Handle API key with priority
    for env_var in API_KEY_ENV_PRIORITY:
        value = os.environ.get(env_var)
        if value:
            _set_nested_value(env_config, "llm.api_key", value)
            break

    # Handle other env vars (excluding API key vars already handled)
    api_key_vars = set(API_KEY_ENV_PRIORITY)
    for env_var, path in ENV_MAPPINGS.items():
        if env_var in api_key_vars:
            continue  # Already handled above with priority

        value = os.environ.get(env_var)
        if value:
            converted = _convert_env_value(value, path)
            _set_nested_value(env_config, path, converted)

    return env_config


def _load_toml(path: Path) -> dict[str, Any]:
    """Load and parse a TOML file if it exists."""
    if not path.exists():
        return {}

    with open(path, "rb") as f:
        data: Any = tomllib.load(f)
        return cast(dict[str, Any], data)


async def load_config(
    user_config_path: Path | None = None,
    project_config_path: Path | None = None,
    load_env: bool = True,
) -> Settings:
    """Load and merge configuration from multiple sources.

    Priority (highest to lowest):
    1. Environment variables (if load_env=True)
    2. Project config (.pygent/config.toml)
    3. User config (~/.config/pygent/config.toml)
    4. Defaults

    Args:
        user_config_path: Override user config location.
        project_config_path: Override project config location.
        load_env: Whether to load from environment variables (default True).

    Returns:
        Merged Settings instance.
    """
    config_data: dict[str, Any] = {}

    # 1. User Config (lowest priority after defaults)
    if user_config_path is None:
        user_config_path = Path.home() / ".config" / "pygent" / "config.toml"

    user_config = _load_toml(user_config_path)
    config_data = _deep_update(config_data, user_config)

    # 2. Project Config (higher priority)
    if project_config_path is None:
        project_config_path = Path.cwd() / ".pygent" / "config.toml"

    project_config = _load_toml(project_config_path)
    config_data = _deep_update(config_data, project_config)

    # 3. Environment Variables (highest priority)
    if load_env:
        env_config = _load_env_config()
        config_data = _deep_update(config_data, env_config)

    # 4. Create Settings (this handles validation and defaults for missing keys)
    return Settings(**config_data)
