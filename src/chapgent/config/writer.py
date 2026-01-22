"""Configuration writer module for chapgent.

Provides utilities for writing configuration values to TOML files.
This module is used by both the CLI and TUI for persisting configuration changes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]


class ConfigWriteError(Exception):
    """Error raised when config writing fails."""

    def __init__(self, message: str, path: Path | None = None) -> None:
        """Initialize the error.

        Args:
            message: Error message.
            path: Optional path to the config file that failed.
        """
        super().__init__(message)
        self.message = message
        self.path = path


# Valid config keys that can be set
VALID_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "llm.provider",
        "llm.model",
        "llm.max_output_tokens",
        "llm.api_key",
        "llm.base_url",
        "llm.extra_headers",
        "llm.oauth_token",
        "permissions.auto_approve_low_risk",
        "permissions.session_override_allowed",
        "tui.theme",
        "tui.show_tool_panel",
        "tui.show_sidebar",
        "system_prompt.content",
        "system_prompt.file",
        "system_prompt.append",
        "system_prompt.mode",
        "logging.level",
        "logging.file",
    }
)


def get_config_paths() -> tuple[Path, Path]:
    """Get the user and project config file paths.

    Returns:
        Tuple of (user_config_path, project_config_path).
    """
    user_config = Path.home() / ".config" / "chapgent" / "config.toml"
    project_config = Path.cwd() / ".chapgent" / "config.toml"
    return user_config, project_config


def convert_value(key: str, value: str) -> str | int | bool | dict[str, str]:
    """Convert a string value to the appropriate type for the given key.

    Args:
        key: The config key (e.g., "llm.max_output_tokens").
        value: The string value to convert.

    Returns:
        The converted value (str, int, bool, or dict).

    Raises:
        ConfigWriteError: If the value cannot be converted or is invalid.
    """
    # Integer fields
    if key == "llm.max_output_tokens":
        try:
            return int(value)
        except ValueError:
            raise ConfigWriteError(f"Invalid integer value for {key}: {value}") from None

    # Boolean fields
    bool_keys = {
        "permissions.auto_approve_low_risk",
        "permissions.session_override_allowed",
        "tui.show_tool_panel",
        "tui.show_sidebar",
    }
    if key in bool_keys:
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False
        raise ConfigWriteError(f"Invalid boolean value for {key}: {value}. Use true/false.")

    # JSON dict fields
    if key == "llm.extra_headers":
        import json

        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ConfigWriteError(f"Invalid JSON for {key}: expected a dict, got {type(parsed).__name__}")
            # Validate all keys and values are strings
            for k, v in parsed.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    raise ConfigWriteError(f"Invalid JSON for {key}: all keys and values must be strings")
            return parsed
        except json.JSONDecodeError as e:
            raise ConfigWriteError(f"Invalid JSON for {key}: {e}") from None

    # Validate mode values
    if key == "system_prompt.mode":
        if value not in ("replace", "append"):
            raise ConfigWriteError(f"Invalid mode value: {value}. Use 'replace' or 'append'.")

    # Validate logging level
    if key == "logging.level":
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if value.upper() not in valid_levels:
            raise ConfigWriteError(f"Invalid log level: {value}. Valid levels are: DEBUG, INFO, WARNING, ERROR")
        return value.upper()  # Normalize to uppercase

    # Validate URL format for base_url
    if key == "llm.base_url":
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise ConfigWriteError(f"Invalid URL for {key}: must start with http:// or https://")

    return value


def format_toml_value(value: str | int | bool | dict[str, str]) -> str:
    """Format a value for TOML output.

    Args:
        value: The value to format.

    Returns:
        The TOML-formatted string representation.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, dict):
        # Format as inline TOML table: { key = "value", ... }
        items = []
        for k, v in sorted(value.items()):
            escaped_v = v.replace("\\", "\\\\").replace('"', '\\"')
            items.append(f'"{k}" = "{escaped_v}"')
        return "{ " + ", ".join(items) + " }"
    # String - escape quotes and wrap in quotes
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write data to a TOML file.

    Args:
        path: Path to the TOML file.
        data: Dictionary data to write.
    """
    lines: list[str] = []
    _write_toml_section(lines, data, [])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_toml_section(lines: list[str], data: dict[str, Any], path_parts: list[str]) -> None:
    """Recursively write TOML sections.

    Args:
        lines: List to append lines to.
        data: Dictionary data for this section.
        path_parts: List of keys forming the section path.
    """
    # First, write any non-dict values at this level
    simple_values = {k: v for k, v in data.items() if not isinstance(v, dict)}
    nested_values = {k: v for k, v in data.items() if isinstance(v, dict)}

    # Write section header if we're in a nested section and have values
    if path_parts and (simple_values or nested_values):
        section_name = ".".join(path_parts)
        if lines:  # Add blank line before new section
            lines.append("")
        lines.append(f"[{section_name}]")

    # Write simple key-value pairs
    for key, value in sorted(simple_values.items()):
        formatted = format_toml_value(value)
        lines.append(f"{key} = {formatted}")

    # Recursively write nested sections
    for key, value in sorted(nested_values.items()):
        _write_toml_section(lines, value, path_parts + [key])


def get_default_config_content() -> str:
    """Get the default configuration file content.

    Returns:
        The default configuration as a TOML string with comments.
    """
    return """\
# Chapgent Configuration
# See: https://github.com/davewil/chapgent for documentation

[llm]
# provider = "anthropic"
# model = "claude-sonnet-4-20250514"
# max_output_tokens = 4096
# api_key = ""  # Prefer ANTHROPIC_API_KEY env var

[permissions]
# auto_approve_low_risk = true
# session_override_allowed = true

[tui]
# theme = "textual-dark"
# show_tool_panel = true
# show_sidebar = true

[system_prompt]
# content = "Custom system prompt content"
# file = "~/.config/chapgent/prompt.md"
# append = "Additional context appended to base prompt"
# mode = "append"  # or "replace"

[logging]
# level = "INFO"  # DEBUG, INFO, WARNING, ERROR
# file = "~/.local/share/chapgent/logs/chapgent.log"  # Custom log path
"""


def write_default_config(config_path: Path) -> None:
    """Write default configuration to a file.

    Args:
        config_path: Path to write the config file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(get_default_config_content(), encoding="utf-8")


def save_config_value(key: str, value: str, *, project: bool = False) -> tuple[Path, Any]:
    """Save a configuration value to the config file.

    This is the main entry point for saving config values from both CLI and TUI.

    Args:
        key: The config key (e.g., "llm.model", "tui.theme").
        value: The value to set (as a string).
        project: If True, save to project config; otherwise save to user config.

    Returns:
        Tuple of (config_path, typed_value) that was saved.

    Raises:
        ConfigWriteError: If the key is invalid or value conversion fails.
    """
    if key not in VALID_CONFIG_KEYS:
        valid_keys = ", ".join(sorted(VALID_CONFIG_KEYS))
        raise ConfigWriteError(f"Invalid config key: {key}\nValid keys: {valid_keys}")

    # Convert value to appropriate type
    typed_value = convert_value(key, value)

    user_config, project_config = get_config_paths()
    config_path = project_config if project else user_config

    # Load existing config or create empty structure
    existing: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            existing = tomllib.load(f)

    # Update the nested value
    keys = key.split(".")
    current = existing
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    current[keys[-1]] = typed_value

    # Write back as TOML
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_toml(config_path, existing)

    return config_path, typed_value


def get_valid_config_keys() -> frozenset[str]:
    """Get the set of valid configuration keys.

    Returns:
        Frozenset of valid config key strings.
    """
    return VALID_CONFIG_KEYS
