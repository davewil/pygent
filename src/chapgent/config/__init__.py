"""Configuration module for chapgent."""

from chapgent.config.loader import API_KEY_ENV_PRIORITY, ENV_MAPPINGS, load_config
from chapgent.config.prompt import (
    TEMPLATE_VARIABLES,
    PromptLoadError,
    build_full_system_prompt,
    get_effective_prompt,
    get_template_variables,
    load_prompt_file,
    resolve_template_variables,
)
from chapgent.config.settings import (
    DEFAULT_SYSTEM_PROMPT,
    KNOWN_MODELS,
    VALID_PROVIDERS,
    VALID_THEMES,
    ConfigValidationError,
    LLMSettings,
    LoggingSettings,
    PermissionSettings,
    Settings,
    SystemPromptSettings,
    TUISettings,
    get_known_models,
    get_valid_providers,
    get_valid_themes,
)
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

__all__ = [
    # Settings
    "DEFAULT_SYSTEM_PROMPT",
    "KNOWN_MODELS",
    "VALID_PROVIDERS",
    "VALID_THEMES",
    "ConfigValidationError",
    "LLMSettings",
    "LoggingSettings",
    "PermissionSettings",
    "Settings",
    "SystemPromptSettings",
    "TUISettings",
    "get_known_models",
    "get_valid_providers",
    "get_valid_themes",
    # Loader
    "API_KEY_ENV_PRIORITY",
    "ENV_MAPPINGS",
    "load_config",
    # Prompt
    "TEMPLATE_VARIABLES",
    "PromptLoadError",
    "build_full_system_prompt",
    "get_effective_prompt",
    "get_template_variables",
    "load_prompt_file",
    "resolve_template_variables",
    # Writer
    "VALID_CONFIG_KEYS",
    "ConfigWriteError",
    "convert_value",
    "format_toml_value",
    "get_config_paths",
    "get_default_config_content",
    "get_valid_config_keys",
    "save_config_value",
    "write_default_config",
    "write_toml",
]
