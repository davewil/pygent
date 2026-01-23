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
    # Chapgent-specific env vars (highest priority)
    "CHAPGENT_MODEL": "llm.model",
    "CHAPGENT_API_KEY": "llm.api_key",
    "CHAPGENT_AUTH_MODE": "llm.auth_mode",  # "api" or "max"
    "CHAPGENT_MAX_OUTPUT_TOKENS": "llm.max_output_tokens",
    "CHAPGENT_MAX_TOKENS": "llm.max_output_tokens",  # Backwards compat
    "CHAPGENT_PROVIDER": "llm.provider",
    "CHAPGENT_BASE_URL": "llm.base_url",
    "CHAPGENT_EXTRA_HEADERS": "llm.extra_headers",
    "CHAPGENT_OAUTH_TOKEN": "llm.oauth_token",
    # Standard API key env vars (fallback for api_key)
    "ANTHROPIC_API_KEY": "llm.api_key",
    "OPENAI_API_KEY": "llm.api_key",
    # Anthropic-compatible env vars (for Claude Code Max subscription)
    "ANTHROPIC_BASE_URL": "llm.base_url",
    "ANTHROPIC_CUSTOM_HEADERS": "llm.extra_headers",
    "ANTHROPIC_OAUTH_TOKEN": "llm.oauth_token",
}

# Priority order for API key env vars (first found wins)
API_KEY_ENV_PRIORITY = ["CHAPGENT_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]

# Priority order for base_url env vars (first found wins)
BASE_URL_ENV_PRIORITY = ["CHAPGENT_BASE_URL", "ANTHROPIC_BASE_URL"]

# Priority order for extra_headers env vars (first found wins)
EXTRA_HEADERS_ENV_PRIORITY = ["CHAPGENT_EXTRA_HEADERS", "ANTHROPIC_CUSTOM_HEADERS"]

# Priority order for oauth_token env vars (first found wins)
OAUTH_TOKEN_ENV_PRIORITY = ["CHAPGENT_OAUTH_TOKEN", "ANTHROPIC_OAUTH_TOKEN"]


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
        Converted value (int, bool, dict, or str).
    """
    # Integer fields
    if path.endswith(".max_output_tokens") or path.endswith(".max_tokens"):
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

    # JSON dict fields (extra_headers)
    if path.endswith(".extra_headers"):
        import json

        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass  # Fall through to return as string

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

    # Handle OAuth token with priority
    for env_var in OAUTH_TOKEN_ENV_PRIORITY:
        value = os.environ.get(env_var)
        if value:
            _set_nested_value(env_config, "llm.oauth_token", value)
            break

    # Handle base_url with priority
    for env_var in BASE_URL_ENV_PRIORITY:
        value = os.environ.get(env_var)
        if value:
            _set_nested_value(env_config, "llm.base_url", value)
            break

    # Handle extra_headers with priority
    for env_var in EXTRA_HEADERS_ENV_PRIORITY:
        value = os.environ.get(env_var)
        if value:
            converted = _convert_env_value(value, "llm.extra_headers")
            _set_nested_value(env_config, "llm.extra_headers", converted)
            break

    # Handle other env vars (excluding vars already handled with priority)
    priority_handled_vars = (
        set(API_KEY_ENV_PRIORITY)
        | set(OAUTH_TOKEN_ENV_PRIORITY)
        | set(BASE_URL_ENV_PRIORITY)
        | set(EXTRA_HEADERS_ENV_PRIORITY)
    )
    for env_var, path in ENV_MAPPINGS.items():
        if env_var in priority_handled_vars:
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


def _migrate_deprecated_keys(config_data: dict[str, Any]) -> dict[str, Any]:
    """Migrate deprecated config keys to their new names.

    Args:
        config_data: The configuration dictionary to migrate.

    Returns:
        The migrated configuration dictionary.
    """
    llm = config_data.get("llm", {})
    if isinstance(llm, dict):
        # Migrate max_tokens -> max_output_tokens
        if "max_tokens" in llm and "max_output_tokens" not in llm:
            llm["max_output_tokens"] = llm.pop("max_tokens")
        elif "max_tokens" in llm:
            # If both exist, prefer max_output_tokens and remove max_tokens
            del llm["max_tokens"]
    return config_data


async def load_config(
    user_config_path: Path | None = None,
    project_config_path: Path | None = None,
    load_env: bool = True,
) -> Settings:
    """Load and merge configuration from multiple sources.

    Priority (highest to lowest):
    1. Environment variables (if load_env=True)
    2. Project config (.chapgent/config.toml)
    3. User config (~/.config/chapgent/config.toml)
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
        user_config_path = Path.home() / ".config" / "chapgent" / "config.toml"

    user_config = _load_toml(user_config_path)
    config_data = _deep_update(config_data, user_config)

    # 2. Project Config (higher priority)
    if project_config_path is None:
        project_config_path = Path.cwd() / ".chapgent" / "config.toml"

    project_config = _load_toml(project_config_path)
    config_data = _deep_update(config_data, project_config)

    # 3. Environment Variables (highest priority)
    if load_env:
        env_config = _load_env_config()
        config_data = _deep_update(config_data, env_config)

    # 4. Migrate deprecated keys (e.g., max_tokens -> max_output_tokens)
    config_data = _migrate_deprecated_keys(config_data)

    # 5. Create Settings (this handles validation and defaults for missing keys)
    return Settings(**config_data)
