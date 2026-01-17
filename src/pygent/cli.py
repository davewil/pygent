import asyncio
import uuid
from typing import Any

import click

from pygent.config.loader import load_config
from pygent.core.agent import Agent
from pygent.core.mock_provider import MockLLMProvider
from pygent.core.permissions import PermissionManager
from pygent.core.providers import LLMProvider
from pygent.session.models import Session
from pygent.session.storage import SessionStorage
from pygent.tools.base import ToolCategory
from pygent.tools.registry import ToolRegistry
from pygent.tui.app import PygentApp


@click.group()
@click.version_option()
def cli() -> None:
    """Pygent - AI-powered coding agent."""
    pass


async def _init_agent_and_app(
    session_id: str | None = None,
    is_new: bool = False,
    use_mock: bool = False,
) -> PygentApp:
    """Initialize agent and app components."""
    # 1. Load Config
    settings = await load_config()

    # 2. Initialize Components
    provider: LLMProvider
    if use_mock:
        provider = MockLLMProvider(delay=0.3)
    else:
        # Priority: Settings > Env (handled in settings.py)
        provider = LLMProvider(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
        )

    tools = ToolRegistry()
    # Register basic tools
    from pygent.tools.filesystem import edit_file, list_files, read_file
    from pygent.tools.shell import shell

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
    app = PygentApp(storage=storage, settings=settings)

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

    # 6. Agent
    agent = Agent(
        provider=provider,
        tools=tools,
        permissions=permissions,
        session=current_session,
    )
    app.agent = agent

    # 7. Apply TUI settings
    app.theme = settings.tui.theme

    return app


@cli.command()
@click.option("--session", "-s", help="Resume a session by ID")
@click.option("--new", "-n", is_flag=True, help="Start a new session")
@click.option("--mock", "-m", is_flag=True, help="Use mock provider (no API key needed)")
def chat(session: str | None, new: bool, mock: bool) -> None:
    """Start interactive chat session."""
    app = asyncio.run(_init_agent_and_app(session_id=session, is_new=new, use_mock=mock))
    app.run()


@cli.command()
def sessions() -> None:
    """List saved sessions."""
    storage = SessionStorage()
    session_list = asyncio.run(storage.list_sessions())

    if not session_list:
        click.echo("No sessions found.")
        return

    click.echo(f"{'ID':<40} {'Updated':<20} {'Messages':<10} {'Directory'}")
    click.echo("-" * 100)
    for s in session_list:
        updated_str = s.updated_at.strftime("%Y-%m-%d %H:%M")
        click.echo(f"{s.id:<40} {updated_str:<20} {s.message_count:<10} {s.working_directory}")


@cli.command()
@click.argument("session_id")
@click.option("--mock", "-m", is_flag=True, help="Use mock provider")
def resume(session_id: str, mock: bool) -> None:
    """Resume a specific session."""
    app = asyncio.run(_init_agent_and_app(session_id=session_id, use_mock=mock))
    app.run()


@cli.command()
def config() -> None:
    """Show current configuration."""
    settings = asyncio.run(load_config())

    click.echo("Current Configuration:")
    click.echo("=" * 40)
    click.echo("\n[LLM]")
    click.echo(f"  provider: {settings.llm.provider}")
    click.echo(f"  model: {settings.llm.model}")
    click.echo(f"  max_tokens: {settings.llm.max_tokens}")
    click.echo("\n[Permissions]")
    click.echo(f"  auto_approve_low_risk: {settings.permissions.auto_approve_low_risk}")
    click.echo(f"  session_override_allowed: {settings.permissions.session_override_allowed}")
    click.echo("\n[TUI]")
    click.echo(f"  theme: {settings.tui.theme}")
    click.echo(f"  show_tool_panel: {settings.tui.show_tool_panel}")


def _create_full_registry() -> ToolRegistry:
    """Create a registry with all available tools registered."""
    registry = ToolRegistry()

    # Filesystem tools
    from pygent.tools.filesystem import (
        copy_file,
        create_file,
        delete_file,
        edit_file,
        list_files,
        move_file,
        read_file,
    )

    registry.register(read_file)
    registry.register(list_files)
    registry.register(edit_file)
    registry.register(create_file)
    registry.register(delete_file)
    registry.register(move_file)
    registry.register(copy_file)

    # Shell tool
    from pygent.tools.shell import shell

    registry.register(shell)

    # Search tools
    from pygent.tools.search import find_definition, find_files, grep_search

    registry.register(grep_search)
    registry.register(find_files)
    registry.register(find_definition)

    # Git tools
    from pygent.tools.git import (
        git_add,
        git_branch,
        git_checkout,
        git_commit,
        git_diff,
        git_log,
        git_pull,
        git_push,
        git_status,
    )

    registry.register(git_status)
    registry.register(git_diff)
    registry.register(git_log)
    registry.register(git_branch)
    registry.register(git_add)
    registry.register(git_commit)
    registry.register(git_checkout)
    registry.register(git_push)
    registry.register(git_pull)

    # Web tools
    from pygent.tools.web import web_fetch

    registry.register(web_fetch)

    # Testing tools
    from pygent.tools.testing import run_tests

    registry.register(run_tests)

    return registry


@cli.command()
@click.option("--category", "-c", help="Filter by category (filesystem, git, search, web, shell, testing)")
def tools(category: str | None) -> None:
    """List all available tools."""
    registry = _create_full_registry()

    # Risk level colors/indicators
    risk_indicators = {
        "low": "[LOW]",
        "medium": "[MEDIUM]",
        "high": "[HIGH]",
    }

    if category:
        # Filter by category
        try:
            cat = ToolCategory(category.lower())
        except ValueError:
            valid = ", ".join(c.value for c in ToolCategory)
            raise click.ClickException(f"Invalid category '{category}'. Valid: {valid}") from None

        tool_list = registry.list_by_category(cat)
        if not tool_list:
            click.echo(f"No tools in category '{category}'.")
            return

        click.echo(f"\n{cat.value.title()} Tools:")
        click.echo("-" * 60)
        for tool in sorted(tool_list, key=lambda t: t.name):
            risk = risk_indicators.get(tool.risk.value, "[?]")
            click.echo(f"  {tool.name:<20} {tool.description:<40} {risk}")
    else:
        # Show all tools grouped by category
        categories = registry.get_categories()

        for cat in categories:
            tool_list = registry.list_by_category(cat)
            if not tool_list:
                continue

            click.echo(f"\n{cat.value.title()} Tools:")
            click.echo("-" * 60)
            for tool in sorted(tool_list, key=lambda t: t.name):
                risk = risk_indicators.get(tool.risk.value, "[?]")
                click.echo(f"  {tool.name:<20} {tool.description:<40} {risk}")

    click.echo()


if __name__ == "__main__":
    cli()
