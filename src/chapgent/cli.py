import asyncio
import uuid
from pathlib import Path
from typing import Any

import click

from chapgent.config.loader import load_config
from chapgent.config.prompt import PromptLoadError, build_full_system_prompt
from chapgent.config.writer import (
    ConfigWriteError,
    get_config_paths,
    write_default_config,
    write_toml,
)
from chapgent.context.detection import detect_project_context
from chapgent.core.agent import Agent
from chapgent.core.mock_provider import MockLLMProvider
from chapgent.core.permissions import PermissionManager
from chapgent.core.providers import LLMProvider
from chapgent.session.models import Session
from chapgent.session.storage import SessionStorage
from chapgent.tools.base import ToolCategory
from chapgent.tools.registry import ToolRegistry
from chapgent.tui.app import ChapgentApp


@click.group()
@click.version_option()
def cli() -> None:
    """Chapgent - AI-powered coding agent."""
    pass


async def _init_agent_and_app(
    session_id: str | None = None,
    is_new: bool = False,
    use_mock: bool = False,
) -> ChapgentApp:
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


@cli.group()
def config() -> None:
    """Manage configuration."""
    pass


@config.command()
def show() -> None:
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


@config.command()
def path() -> None:
    """Show config file paths."""
    user_config, project_config = get_config_paths()

    click.echo("Configuration File Paths:")
    click.echo("=" * 60)

    # User config
    user_exists = user_config.exists()
    user_status = "[exists]" if user_exists else "[not found]"
    click.echo(f"\nUser config:    {user_config} {user_status}")

    # Project config
    project_exists = project_config.exists()
    project_status = "[exists]" if project_exists else "[not found]"
    click.echo(f"Project config: {project_config} {project_status}")

    click.echo("\nPriority (highest to lowest):")
    click.echo("  1. Environment variables")
    click.echo("  2. Project config (.chapgent/config.toml)")
    click.echo("  3. User config (~/.config/chapgent/config.toml)")
    click.echo("  4. Defaults")


@config.command()
@click.option("--project", "-p", is_flag=True, help="Edit project config instead of user config")
def edit(project: bool) -> None:
    """Open config in $EDITOR."""
    import os
    import subprocess

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
    user_config, project_config = get_config_paths()

    config_path = project_config if project else user_config

    # Create parent directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Create file with defaults if it doesn't exist
    if not config_path.exists():
        write_default_config(config_path)
        click.echo(f"Created {config_path} with default settings.")

    try:
        subprocess.run([editor, str(config_path)], check=True)
    except FileNotFoundError:
        raise click.ClickException(f"Editor '{editor}' not found. Set $EDITOR environment variable.") from None
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Editor exited with error: {e.returncode}") from None


@config.command()
@click.option("--project", "-p", is_flag=True, help="Initialize project config instead of user config")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config file")
def init(project: bool, force: bool) -> None:
    """Create default config file."""
    user_config, project_config = get_config_paths()
    config_path = project_config if project else user_config

    if config_path.exists() and not force:
        raise click.ClickException(f"Config file already exists at {config_path}. Use --force to overwrite.") from None

    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_default_config(config_path)

    location = "project" if project else "user"
    click.echo(f"Created {location} config at {config_path}")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--project", "-p", is_flag=True, help="Set in project config instead of user config")
def set_config(key: str, value: str, project: bool) -> None:
    """Set a configuration value.

    KEY is a dotted path like 'llm.model' or 'tui.theme'.
    VALUE is the value to set.

    Example: chapgent config set llm.model claude-3-5-haiku-20241022
    """
    from chapgent.config.writer import save_config_value

    try:
        config_path, typed_value = save_config_value(key, value, project=project)
    except ConfigWriteError as e:
        raise click.ClickException(str(e)) from None

    location = "project" if project else "user"
    click.echo(f"Set {key} = {typed_value} in {location} config")


def _create_full_registry() -> ToolRegistry:
    """Create a registry with all available tools registered."""
    registry = ToolRegistry()

    # Filesystem tools
    from chapgent.tools.filesystem import (
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
    from chapgent.tools.shell import shell

    registry.register(shell)

    # Search tools
    from chapgent.tools.search import find_definition, find_files, grep_search

    registry.register(grep_search)
    registry.register(find_files)
    registry.register(find_definition)

    # Git tools
    from chapgent.tools.git import (
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
    from chapgent.tools.web import web_fetch

    registry.register(web_fetch)

    # Testing tools
    from chapgent.tools.testing import run_tests

    registry.register(run_tests)

    # Project scaffolding tools
    from chapgent.tools.scaffold import add_component, create_project, list_components, list_templates

    registry.register(list_templates)
    registry.register(create_project)
    registry.register(add_component)
    registry.register(list_components)

    return registry


@cli.command()
@click.option("--category", "-c", help="Filter by category (filesystem, git, search, web, shell, testing, project)")
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


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--days", default=7, help="Include logs from last N days")
def report(output: str | None, days: int) -> None:
    """Package logs for bug reporting.

    Creates a compressed archive of recent logs with sensitive
    data (API keys, absolute paths) redacted.
    """
    import tarfile
    from datetime import datetime

    from chapgent.core.logging import get_log_dir, get_log_files, redact_sensitive

    log_dir = get_log_dir()

    if not log_dir.exists():
        click.echo("No logs found. Run chapgent with logging enabled first.")
        return

    log_files = get_log_files(days=days)
    if not log_files:
        click.echo("No log files found.")
        return

    # Default output path
    if output is None:
        output = f"chapgent-report-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"

    output_path = Path(output)

    # Collect and sanitize logs into archive
    try:
        with tarfile.open(output_path, "w:gz") as tar:
            for log_file in log_files:
                try:
                    # Read and redact sensitive info
                    content = log_file.read_text(errors="replace")
                    redacted = redact_sensitive(content)

                    # Create a tarinfo object with the redacted content
                    import io

                    data = redacted.encode("utf-8")
                    tarinfo = tarfile.TarInfo(name=log_file.name)
                    tarinfo.size = len(data)
                    tar.addfile(tarinfo, io.BytesIO(data))

                    click.echo(f"  Added: {log_file.name}")
                except Exception as e:
                    click.echo(f"  Skipped: {log_file.name} ({e})", err=True)

        click.echo(f"\nReport created: {output_path}")
        click.echo("Please attach this file to your GitHub issue.")
        click.echo(f"Report size: {output_path.stat().st_size} bytes")
    except Exception as e:
        raise click.ClickException(f"Failed to create report: {e}") from None


@cli.command()
@click.option(
    "--level", "-l", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO", help="Log level"
)
@click.option("--file", "-f", "log_file", type=click.Path(), help="Custom log file path")
def logs(level: str, log_file: str | None) -> None:
    """Show log file path and configure logging.

    Without options, shows current log file path. With options, you can
    configure logging level and custom log file path.
    """
    from chapgent.core.logging import get_log_file, setup_logging

    if log_file:
        # User wants to configure logging
        log_path = setup_logging(level=level, log_file=log_file)
        click.echo(f"Logging configured: level={level}, file={log_path}")
    else:
        # Just show current log file path
        log_path = get_log_file()
        exists = log_path.exists()
        status = "[exists]" if exists else "[not found]"
        click.echo(f"Log file: {log_path} {status}")

        if exists:
            size = log_path.stat().st_size
            click.echo(f"Size: {size} bytes")

        click.echo(f"\nTo view logs: cat {log_path}")
        click.echo(f"To tail logs: tail -f {log_path}")


@cli.command("help")
@click.argument("topic", required=False)
def help_cmd(topic: str | None) -> None:
    """Show help for a topic.

    Available topics: tools, config, shortcuts, permissions, sessions,
    prompts, quickstart, troubleshooting.

    Examples:
      chapgent help              List all help topics
      chapgent help tools        Show help about available tools
      chapgent help shortcuts    Show keyboard shortcuts
    """
    from chapgent.ux.help import format_help_topic, get_help_topic, list_help_topics

    if topic is None:
        # List all topics
        click.echo("Chapgent Help Topics")
        click.echo("=" * 60)
        click.echo()

        topics = list_help_topics()
        for name, summary in sorted(topics):
            click.echo(f"  {name:<15} {summary}")

        click.echo()
        click.echo("Use 'chapgent help <topic>' for detailed information.")
        click.echo("Use 'chapgent --help' for command-line options.")
        return

    # Show specific topic
    help_topic = get_help_topic(topic)
    if help_topic is None:
        topics = list_help_topics()
        available = ", ".join(name for name, _ in sorted(topics))
        raise click.ClickException(f"Unknown help topic: {topic}\nAvailable topics: {available}") from None

    click.echo(format_help_topic(help_topic))


@cli.command()
def setup() -> None:
    """Interactive setup for first-time users.

    Guides you through configuring chapgent with your API key
    and creating a configuration file.
    """
    from chapgent.ux.first_run import (
        check_setup_status,
        format_setup_complete_message,
        get_api_key_help,
        get_setup_instructions,
        get_welcome_message,
        validate_api_key_format,
    )

    status = check_setup_status()

    # Show welcome message
    click.echo(get_welcome_message())

    # Check if already set up
    if status.has_api_key and status.has_config_file:
        click.echo("You're already set up!")
        click.echo()
        click.echo("Current status:")
        click.echo("  API key: configured")
        click.echo(f"  Config:  {status.config_path}")
        click.echo()
        click.echo("Run 'chapgent chat' to start chatting.")
        return

    # Show what needs to be done
    click.echo(get_setup_instructions(status))
    click.echo()

    # Offer to set up API key interactively
    if not status.has_api_key:
        if click.confirm("Would you like to set up your API key now?"):
            click.echo()
            click.echo(get_api_key_help())
            click.echo()

            api_key = click.prompt("Enter your API key", hide_input=True)

            is_valid, message = validate_api_key_format(api_key)
            if not is_valid:
                click.echo(f"Warning: {message}")
                if not click.confirm("Continue anyway?"):
                    click.echo("Setup cancelled.")
                    return

            # Set the API key in config
            user_config, _ = get_config_paths()
            user_config.parent.mkdir(parents=True, exist_ok=True)

            import sys

            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

            existing: dict[str, Any] = {}
            if user_config.exists():
                with open(user_config, "rb") as f:
                    existing = tomllib.load(f)

            if "llm" not in existing:
                existing["llm"] = {}
            existing["llm"]["api_key"] = api_key

            write_toml(user_config, existing)
            click.echo(f"API key saved to {user_config}")
            click.echo()

    # Offer to create config file
    if not status.has_config_file:
        if click.confirm("Would you like to create a config file with defaults?"):
            status.config_path.parent.mkdir(parents=True, exist_ok=True)
            write_default_config(status.config_path)
            click.echo(f"Config file created at {status.config_path}")
            click.echo()

    # Show completion message
    try:
        settings = asyncio.run(load_config())
        click.echo(format_setup_complete_message(settings))
    except Exception:
        click.echo(format_setup_complete_message(None))


if __name__ == "__main__":
    cli()
