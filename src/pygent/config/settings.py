from pydantic import BaseModel


class LLMSettings(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    api_key: str | None = None  # Falls back to env var


class PermissionSettings(BaseModel):
    auto_approve_low_risk: bool = True
    session_override_allowed: bool = True


class TUISettings(BaseModel):
    theme: str = "textual-dark"
    show_tool_panel: bool = True


class SystemPromptSettings(BaseModel):
    content: str = "You are a helpful coding assistant..."


class Settings(BaseModel):
    llm: LLMSettings = LLMSettings()
    permissions: PermissionSettings = PermissionSettings()
    tui: TUISettings = TUISettings()
    system_prompt: SystemPromptSettings = SystemPromptSettings()
