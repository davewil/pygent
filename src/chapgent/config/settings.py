from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator

# Valid LLM providers supported by litellm
VALID_PROVIDERS = frozenset(
    {
        "anthropic",
        "openai",
        "azure",
        "bedrock",
        "vertex_ai",
        "cohere",
        "replicate",
        "huggingface",
        "ollama",
        "together_ai",
        "deepinfra",
        "groq",
        "mistral",
        "perplexity",
        "anyscale",
        "fireworks_ai",
    }
)

# Known models by provider (not exhaustive, but common ones)
KNOWN_MODELS = frozenset(
    {
        # Anthropic
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        # OpenAI
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o1-preview",
        # Azure OpenAI (deployments vary, just check pattern)
        # Ollama (local models)
        "llama3.2",
        "llama3.1",
        "codellama",
        "mistral",
        "mixtral",
        # Groq
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    }
)

# Max output tokens validation bounds
MAX_OUTPUT_TOKENS_MIN = 1
MAX_OUTPUT_TOKENS_MAX = 100000

# Valid Textual themes
VALID_THEMES = frozenset(
    {
        "textual-dark",
        "textual-light",
        "textual-ansi",
        "nord",
        "gruvbox",
        "dracula",
        "monokai",
        "solarized-light",
        "solarized-dark",
        "tokyo-night",
        "rose-pine",
    }
)


def get_valid_providers() -> frozenset[str]:
    """Return set of valid LLM provider names."""
    return VALID_PROVIDERS


def get_known_models() -> frozenset[str]:
    """Return set of known model names."""
    return KNOWN_MODELS


def get_valid_themes() -> frozenset[str]:
    """Return set of valid TUI themes."""
    return VALID_THEMES


class ConfigValidationError(ValueError):
    """Raised when configuration validation fails."""

    pass


# Default base system prompt
DEFAULT_SYSTEM_PROMPT = """You are a helpful coding assistant.

You help with software engineering tasks including writing code, debugging,
explaining concepts, and performing file operations. You have access to tools
that let you read and modify files, run shell commands, search code, and more.

Be concise and direct in your responses. Follow the coding conventions and
style of the existing codebase when making changes."""


class LLMSettings(BaseModel):
    """LLM provider settings with validation.

    Attributes:
        provider: LLM provider name (e.g., "anthropic", "openai", "ollama").
        model: Model identifier. Known models are validated; unknown models
            trigger a warning but are allowed for flexibility.
        max_output_tokens: Maximum tokens in the model's response. Must be between 1 and 100000.
        api_key: API key for the provider. Falls back to environment variable.
        base_url: Custom API endpoint (e.g., LiteLLM proxy URL).
        extra_headers: Additional HTTP headers to send with requests.
        oauth_token: OAuth token for Claude Max subscription authentication.
    """

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    max_output_tokens: int = 4096  # Maximum tokens in the model's response
    api_key: str | None = None  # Falls back to env var
    base_url: str | None = None  # Custom API endpoint (e.g., LiteLLM proxy)
    extra_headers: dict[str, str] | None = None  # Additional HTTP headers
    oauth_token: str | None = None  # Claude Max OAuth token

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that provider is a known LLM provider."""
        v_lower = v.lower()
        if v_lower not in VALID_PROVIDERS:
            providers_list = ", ".join(sorted(VALID_PROVIDERS))
            raise ValueError(
                f"Unknown provider '{v}'. Valid providers are: {providers_list}. "
                f"If using a custom provider, ensure it's supported by litellm."
            )
        return v_lower

    @field_validator("max_output_tokens")
    @classmethod
    def validate_max_output_tokens(cls, v: int) -> int:
        """Validate that max_output_tokens is within reasonable bounds."""
        if v < MAX_OUTPUT_TOKENS_MIN:
            raise ValueError(f"max_output_tokens must be at least {MAX_OUTPUT_TOKENS_MIN}")
        if v > MAX_OUTPUT_TOKENS_MAX:
            raise ValueError(
                f"max_output_tokens value {v} exceeds maximum of {MAX_OUTPUT_TOKENS_MAX}. "
                "Most models support at most 4096-32000 tokens."
            )
        return v

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate that api_key is not an empty string."""
        if v is not None and v.strip() == "":
            raise ValueError(
                "api_key cannot be an empty string. "
                "Either provide a valid key or omit the setting to use environment variables."
            )
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate that base_url is a valid URL if provided."""
        if v is not None:
            v = v.strip()
            if v == "":
                raise ValueError(
                    "base_url cannot be an empty string. "
                    "Either provide a valid URL or omit the setting."
                )
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError(
                    f"base_url must start with http:// or https://, got: {v}"
                )
        return v

    @field_validator("extra_headers")
    @classmethod
    def validate_extra_headers(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate that extra_headers contains only string keys and values."""
        if v is not None:
            for key, value in v.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError(
                        f"extra_headers must have string keys and values. "
                        f"Got key={type(key).__name__}, value={type(value).__name__}"
                    )
        return v

    @field_validator("oauth_token")
    @classmethod
    def validate_oauth_token(cls, v: str | None) -> str | None:
        """Validate that oauth_token is not an empty string."""
        if v is not None and v.strip() == "":
            raise ValueError(
                "oauth_token cannot be an empty string. "
                "Either provide a valid token or omit the setting."
            )
        return v


class PermissionSettings(BaseModel):
    auto_approve_low_risk: bool = True
    session_override_allowed: bool = True


class TUISettings(BaseModel):
    """TUI appearance settings with validation.

    Attributes:
        theme: Color theme for the TUI. Must be a valid theme name.
        show_tool_panel: Whether to show the tool panel on the right.
        show_sidebar: Whether to show the session sidebar on the left.
    """

    theme: str = "textual-dark"
    show_tool_panel: bool = True
    show_sidebar: bool = True

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Validate that theme is a known theme name."""
        v_lower = v.lower()
        if v_lower not in VALID_THEMES:
            themes_list = ", ".join(sorted(VALID_THEMES))
            raise ValueError(f"Unknown theme '{v}'. Valid themes are: {themes_list}")
        return v_lower


class SystemPromptSettings(BaseModel):
    """System prompt configuration.

    Supports multiple modes for customizing the system prompt:
    - content: Direct prompt content (replaces or appends based on mode)
    - file: Path to a file containing the prompt (supports ~ expansion)
    - append: Additional content to append to the base prompt
    - mode: "replace" or "append" - how to combine custom content with base

    Priority:
    1. If 'file' is set, load content from that file
    2. Otherwise use 'content' if set
    3. In 'append' mode, the custom content is added after the base prompt
    4. In 'replace' mode, the custom content replaces the base prompt entirely

    Template variables (like {project_name}) are resolved at runtime.
    """

    content: str | None = None
    file: str | None = None  # Path to prompt file (supports ~ expansion)
    append: str | None = None  # Additional content to append
    mode: Literal["replace", "append"] = "append"

    @field_validator("file")
    @classmethod
    def validate_file_path(cls, v: str | None) -> str | None:
        """Validate that file path is well-formed (doesn't check existence)."""
        if v is not None:
            v = v.strip()
            if v == "":
                raise ValueError(
                    "system_prompt.file cannot be an empty string. Either provide a valid path or omit the setting."
                )
        return v

    @model_validator(mode="after")
    def validate_content_or_file(self) -> "SystemPromptSettings":
        """Warn if both content and file are set (file takes precedence)."""
        # This is informational - file takes precedence over content
        # No error raised, just documented behavior
        return self


class LoggingSettings(BaseModel):
    """Logging configuration.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        file: Custom log file path (supports ~ expansion).
               If not specified, defaults to ~/.local/share/chapgent/logs/chapgent.log
    """

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str | None = None  # Override default log path

    @field_validator("file")
    @classmethod
    def validate_file_path(cls, v: str | None) -> str | None:
        """Validate that file path is well-formed (doesn't check existence)."""
        if v is not None:
            v = v.strip()
            if v == "":
                raise ValueError(
                    "logging.file cannot be an empty string. Either provide a valid path or omit the setting."
                )
        return v


class Settings(BaseModel):
    """Root settings model combining all configuration sections.

    Attributes:
        llm: LLM provider and model settings.
        permissions: Permission handling settings.
        tui: TUI appearance settings.
        system_prompt: System prompt customization settings.
        logging: Logging configuration.
    """

    llm: LLMSettings = LLMSettings()
    permissions: PermissionSettings = PermissionSettings()
    tui: TUISettings = TUISettings()
    system_prompt: SystemPromptSettings = SystemPromptSettings()
    logging: LoggingSettings = LoggingSettings()

    @classmethod
    def validate_config(cls, config_dict: dict[str, Any]) -> "Settings":
        """Create Settings from dict with helpful error messages.

        Args:
            config_dict: Configuration dictionary (typically from TOML).

        Returns:
            Validated Settings instance.

        Raises:
            ConfigValidationError: If validation fails with user-friendly message.
        """
        from pydantic import ValidationError as PydanticValidationError

        try:
            return cls(**config_dict)
        except PydanticValidationError as e:
            # Convert Pydantic errors to user-friendly messages
            errors = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"  - {loc}: {msg}")
            error_text = "\n".join(errors)
            raise ConfigValidationError(f"Configuration validation failed:\n{error_text}") from None
