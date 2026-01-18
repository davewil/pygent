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
    LLMSettings,
    PermissionSettings,
    Settings,
    SystemPromptSettings,
    TUISettings,
)

__all__ = [
    # Settings
    "DEFAULT_SYSTEM_PROMPT",
    "LLMSettings",
    "PermissionSettings",
    "Settings",
    "SystemPromptSettings",
    "TUISettings",
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
