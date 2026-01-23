"""Agent and TUI initialization for CLI commands."""

import uuid
from pathlib import Path
from typing import Any

import click

from chapgent.config.loader import load_config
from chapgent.config.prompt import PromptLoadError, build_full_system_prompt
from chapgent.context.detection import detect_project_context
from chapgent.core.agent import Agent
from chapgent.core.mock_provider import MockLLMProvider
from chapgent.core.permissions import PermissionManager
from chapgent.core.providers import ClaudeCodeProvider, LLMProvider
from chapgent.session.models import Session
from chapgent.session.storage import SessionStorage
from chapgent.tools.registry import ToolRegistry
from chapgent.tui.app import ChapgentApp


async def init_agent_and_app(
    session_id: str | None = None,
    is_new: bool = False,
    use_mock: bool = False,
    auth_mode_override: str | None = None,
) -> ChapgentApp:
    """Initialize agent and app components.

    Args:
        session_id: Optional session ID to resume.
        is_new: If True, create new session even if session_id not found.
        use_mock: If True, use mock provider for testing.
        auth_mode_override: Override auth_mode from config ("api" or "max").
    """
    import os

    from chapgent.core.logging import setup_logging

    # 0. Initialize logging (respects CHAPGENT_LOG_LEVEL env var)
    log_level = os.environ.get("CHAPGENT_LOG_LEVEL", "INFO").upper()
    setup_logging(level=log_level)

    # 1. Load Config
    settings = await load_config()

    # 2. Determine auth mode and validate
    provider: LLMProvider | ClaudeCodeProvider
    if use_mock:
        provider = MockLLMProvider(delay=0.3)
    else:
        # Determine effective auth mode
        auth_mode = auth_mode_override or settings.llm.auth_mode

        if auth_mode == "max":
            # Claude Max mode: delegate to Claude Code CLI
            # Claude Code handles OAuth authentication internally
            import shutil

            if not shutil.which("claude"):
                raise click.ClickException(
                    "Claude Max mode requires Claude Code CLI.\n\n"
                    "Install Claude Code:\n"
                    "  npm install -g @anthropic-ai/claude-code\n\n"
                    "Then authenticate:\n"
                    "  claude auth login\n\n"
                    "Or switch to API mode:\n"
                    "  chapgent chat --mode api"
                )

            # Map model name to Claude Code alias
            model_alias = settings.llm.model
            if "sonnet" in model_alias.lower():
                model_alias = "sonnet"
            elif "opus" in model_alias.lower():
                model_alias = "opus"
            elif "haiku" in model_alias.lower():
                model_alias = "haiku"

            provider = ClaudeCodeProvider(model=model_alias)
            click.echo("Using Claude Max (via Claude Code CLI)\n")

        else:  # auth_mode == "api"
            # API mode: direct API key, no proxy needed
            if not settings.llm.api_key:
                raise click.ClickException(
                    "API mode requires an API key.\n\n"
                    "Set your Anthropic API key:\n"
                    "  export ANTHROPIC_API_KEY=sk-...\n"
                    "  # or\n"
                    "  chapgent config set llm.api_key sk-...\n\n"
                    "Or switch to Claude Max mode:\n"
                    "  chapgent chat --mode max"
                )

            # Direct API call - no proxy, no extra headers needed
            headers = dict(settings.llm.extra_headers) if settings.llm.extra_headers else None
            provider = LLMProvider(
                model=settings.llm.model,
                api_key=settings.llm.api_key,
                base_url=None,  # Direct to Anthropic
                extra_headers=headers,
            )

    tools = ToolRegistry()
    # Register basic tools
    from chapgent.tools.filesystem import edit_file, list_files, read_file
    from chapgent.tools.shell import shell

    tools.register(read_file)
    tools.register(list_files)
    tools.register(edit_file)
    tools.register(shell)

    # 3. Session Management
    storage = SessionStorage()
    current_session: Session | None = None

    if session_id:
        current_session = await storage.load(session_id)
        if not current_session and not is_new:
            raise click.ClickException(f"Session {session_id} not found.")

    if not current_session:
        current_session = Session(
            id=str(uuid.uuid4()),
            working_directory=".",
            messages=[],
            tool_history=[],
        )

    # 4. Initialize App & Wiring
    app = ChapgentApp(storage=storage, settings=settings)

    async def permission_callback(tool_name: str, risk: Any, args: dict[str, Any]) -> bool:
        return await app.get_permission(tool_name, args)

    # 5. Permissions
    permissions = PermissionManager(
        prompt_callback=permission_callback,
        session_override=not settings.permissions.auto_approve_low_risk,  # This seems backwards in current logic?
    )
    # Actually, current PermissionManager logic:
    # if risk == LOW: return True
    # if risk == MEDIUM and self.session_override: return True
    # else return prompt_callback
    # So settings.permissions.auto_approve_low_risk is ALWAYS True for LOW risk in code.
    # The session_override in PermissionManager is for MEDIUM risk.
    # Let's check settings again.
    # class PermissionSettings(BaseModel):
    #     auto_approve_low_risk: bool = True
    #     session_override_allowed: bool = True
    # The session_override in PermissionManager is a RUNTIME toggle (Ctrl+P).
    # It should probably start as False unless we want it sticky.
    permissions.session_override = False

    # 6. Build system prompt
    system_prompt: str | None = None
    try:
        # Detect project context for template variables and context injection
        project_context = await detect_project_context(Path.cwd())
        system_prompt = build_full_system_prompt(settings.system_prompt, project_context)
    except PromptLoadError as e:
        # Log warning but continue - system prompt customization failing
        # shouldn't prevent the agent from starting
        click.echo(f"Warning: Could not load custom system prompt: {e}", err=True)

    # 7. Agent
    agent = Agent(
        provider=provider,
        tools=tools,
        permissions=permissions,
        session=current_session,
        system_prompt=system_prompt,
    )
    app.agent = agent

    # 8. Apply TUI settings
    app.theme = settings.tui.theme

    return app


__all__ = ["init_agent_and_app"]
