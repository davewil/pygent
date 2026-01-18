"""Configuration module for pygent."""

from pygent.config.loader import API_KEY_ENV_PRIORITY, ENV_MAPPINGS, load_config
from pygent.config.prompt import (
    TEMPLATE_VARIABLES,
    PromptLoadError,
    build_full_system_prompt,
    get_effective_prompt,
    get_template_variables,
    load_prompt_file,
    resolve_template_variables,
)
from pygent.config.settings import (
    DEFAULT_SYSTEM_PROMPT,
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

__all__ = [
    # Settings
    "DEFAULT_SYSTEM_PROMPT",
    "KNOWN_MODELS",
    "VALID_PROVIDERS",
    "VALID_THEMES",
    "ConfigValidationError",
    "LLMSettings",
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
]
