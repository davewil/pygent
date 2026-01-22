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
    import os

    from chapgent.core.logging import setup_logging

    # 0. Initialize logging (respects CHAPGENT_LOG_LEVEL env var)
    log_level = os.environ.get("CHAPGENT_LOG_LEVEL", "INFO").upper()
    setup_logging(level=log_level)

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
            base_url=settings.llm.base_url,
            extra_headers=settings.llm.extra_headers,
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


# =============================================================================
# Auth Commands
# =============================================================================


@cli.group()
def auth() -> None:
    """Authentication commands for Claude Max subscription."""
    pass


@auth.command()
@click.option(
    "--import-claude-code",
    is_flag=True,
    help="Import OAuth token from Claude Code credentials (~/.claude/.credentials.json)",
)
@click.option(
    "--token",
    help="Directly provide an OAuth token",
)
def login(import_claude_code: bool, token: str | None) -> None:
    """Authenticate with Claude Max subscription.

    Claude Max OAuth tokens can be obtained by:
    1. Installing Claude Code CLI and running '/login'
    2. Using --import-claude-code to import from Claude Code's credentials
    3. Providing a token directly with --token
    """
    import json

    from rich.console import Console

    from chapgent.config.writer import save_config_value

    console = Console()
    console.print("\n[bold]Claude Max Authentication[/bold]\n")

    # Option 1: Import from Claude Code
    if import_claude_code:
        credentials_path = Path.home() / ".claude" / ".credentials.json"
        if not credentials_path.exists():
            console.print("[red]Error: Claude Code credentials not found[/red]")
            console.print(f"  Expected: {credentials_path}")
            console.print("\nTo get credentials:")
            console.print("  1. Install Claude Code: npm install -g @anthropic/claude-code")
            console.print("  2. Run: claude")
            console.print("  3. Type: /login")
            raise SystemExit(1)

        try:
            with open(credentials_path) as f:
                creds = json.load(f)
            # Token can be at top level or nested under claudeAiOauth
            token = (
                creds.get("accessToken")
                or creds.get("access_token")
                or creds.get("claudeAiOauth", {}).get("accessToken")
            )
            if not token:
                console.print("[red]Error: No access token found in credentials[/red]")
                console.print("[dim]Expected 'accessToken' or 'claudeAiOauth.accessToken'[/dim]")
                raise SystemExit(1)
            console.print("[green]✓ Imported token from Claude Code credentials[/green]")
        except json.JSONDecodeError:
            console.print("[red]Error: Invalid JSON in credentials file[/red]")
            raise SystemExit(1)

    # Option 2: Token provided directly
    elif token:
        console.print("Using provided token...")

    # Option 3: Interactive - guide user
    else:
        console.print("To authenticate with Claude Max, you have several options:\n")
        console.print("[bold]Option 1: Import from Claude Code (Recommended)[/bold]")
        console.print("  If you have Claude Code installed and logged in:")
        console.print("    chapgent auth login --import-claude-code\n")
        console.print("[bold]Option 2: Use Claude Code to login first[/bold]")
        console.print("  1. Install Claude Code: npm install -g @anthropic/claude-code")
        console.print("  2. Run: claude")
        console.print("  3. Type: /login")
        console.print("  4. Then run: chapgent auth login --import-claude-code\n")
        console.print("[bold]Option 3: Enter token manually[/bold]")

        if not click.confirm("Do you have an OAuth token to enter manually?", default=False):
            console.print("\nRun 'chapgent auth login --import-claude-code' after logging into Claude Code.")
            return

        token = click.prompt("Paste your OAuth token", hide_input=True)

    # Validate and save token
    if not token or len(token) < 20:
        console.print("[red]Error: Invalid token format[/red]")
        raise SystemExit(1)

    try:
        config_path, _ = save_config_value("llm.oauth_token", token, project=False)
        console.print(f"[green]✓ OAuth token saved successfully![/green]")
        console.print(f"  Config: {config_path}")
    except ConfigWriteError as e:
        raise click.ClickException(str(e)) from None


@auth.command()
def logout() -> None:
    """Remove stored authentication tokens."""
    from rich.console import Console

    from chapgent.config.writer import save_config_value

    console = Console()

    try:
        # Remove oauth_token
        save_config_value("llm.oauth_token", "", project=False)
        # Remove api_key
        save_config_value("llm.api_key", "", project=False)
        console.print("[green]✓ Authentication tokens removed[/green]")
    except ConfigWriteError as e:
        raise click.ClickException(str(e)) from None


@auth.command()
def status() -> None:
    """Show current authentication status."""
    from rich.console import Console

    settings = asyncio.run(load_config())
    console = Console()

    console.print("\n[bold]Authentication Status[/bold]\n")

    if settings.llm.oauth_token:
        console.print("[green]✓ Claude Max OAuth token configured[/green]")
        # Show partial token for verification
        token = settings.llm.oauth_token
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "****"
        console.print(f"  Token: {masked}")
    elif settings.llm.api_key:
        console.print("[green]✓ API key configured[/green]")
        # Show partial key for verification
        key = settings.llm.api_key
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
        console.print(f"  Key: {masked}")
    else:
        console.print("[yellow]✗ No authentication configured[/yellow]")
        console.print("  Run: chapgent auth login")

    # Show base_url if configured (for proxy)
    if settings.llm.base_url:
        console.print(f"\n[dim]Proxy URL: {settings.llm.base_url}[/dim]")

    console.print()


# =============================================================================
# Proxy Commands
# =============================================================================


@cli.group()
def proxy() -> None:
    """LiteLLM proxy server commands."""
    pass


@proxy.command()
@click.option("--port", default=4000, help="Port to run proxy on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
def start(port: int, host: str) -> None:
    """Start LiteLLM proxy server (foreground).

    Runs a local LiteLLM Gateway that forwards OAuth tokens to Anthropic,
    enabling Claude Max subscription usage with cost tracking.
    """
    import subprocess
    import tempfile

    import yaml
    from rich.console import Console

    console = Console()

    # Generate LiteLLM config
    config = {
        "model_list": [
            {
                "model_name": "anthropic-claude",
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-20250514",
                },
            },
            {
                "model_name": "claude-sonnet-4-20250514",
                "litellm_params": {
                    "model": "anthropic/claude-sonnet-4-20250514",
                },
            },
            {
                "model_name": "claude-3-5-haiku-20241022",
                "litellm_params": {
                    "model": "anthropic/claude-3-5-haiku-20241022",
                },
            },
        ],
        "general_settings": {
            "forward_client_headers_to_llm_api": True,
        },
        "litellm_settings": {
            "drop_params": True,
        },
    }

    # Write temp config
    config_dir = Path(tempfile.gettempdir()) / "chapgent"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "litellm-proxy.yaml"

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    console.print("\n[bold]Starting LiteLLM Proxy[/bold]\n")
    console.print(f"Config: {config_path}")
    console.print(f"URL:    http://{host}:{port}\n")
    console.print("[dim]Configure chapgent to use this proxy:[/dim]")
    console.print(f"  export CHAPGENT_BASE_URL=http://{host}:{port}")
    console.print(f"  export ANTHROPIC_BASE_URL=http://{host}:{port}\n")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    console.print("-" * 50)

    try:
        subprocess.run(
            ["litellm", "--config", str(config_path), "--host", host, "--port", str(port)],
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Proxy stopped[/yellow]")
    except FileNotFoundError:
        console.print("[red]Error: litellm CLI not found. Install with: pip install litellm[proxy][/red]")
        raise SystemExit(1)


@proxy.command("setup")
def proxy_setup() -> None:
    """Interactive setup wizard for LiteLLM proxy configuration.

    Guides you through configuring chapgent to use a LiteLLM proxy
    for cost tracking, budget controls, and Claude Max subscription support.
    """
    import json

    from rich.console import Console

    from chapgent.config.writer import save_config_value
    from chapgent.ux.first_run import (
        check_proxy_setup_status,
        get_proxy_setup_instructions,
        get_proxy_welcome_message,
        validate_proxy_url,
    )

    console = Console()
    status = check_proxy_setup_status()

    # Show welcome message
    console.print(get_proxy_welcome_message())

    # Show current status
    if status.has_proxy_url:
        console.print(f"[green]✓ Proxy URL already configured: {status.proxy_url}[/green]")
    if status.has_oauth_token:
        console.print("[green]✓ OAuth token already configured[/green]")
    if status.has_litellm_key:
        console.print("[green]✓ LiteLLM API key already configured[/green]")

    if status.has_proxy_url and status.has_oauth_token:
        console.print("\n[bold]You're already set up![/bold]")
        if not click.confirm("\nWould you like to reconfigure?", default=False):
            console.print("\nRun 'chapgent chat' to start chatting.")
            return

    console.print()

    # Step 1: Choose setup mode
    console.print("[bold]Step 1: Choose proxy mode[/bold]")
    console.print("  1. Local proxy (run LiteLLM proxy on your machine)")
    console.print("  2. Remote proxy (connect to an existing proxy)")
    console.print()

    mode_choice = click.prompt(
        "Enter your choice",
        type=click.Choice(["1", "2"]),
        default="1",
    )

    if mode_choice == "1":
        # Local proxy setup
        port = click.prompt("Port for local proxy", default=4000, type=int)
        base_url = f"http://localhost:{port}"
        console.print(f"\n[dim]To start the proxy, run:[/dim]")
        console.print(f"  chapgent proxy start --port {port}")
        console.print()
    else:
        # Remote proxy setup
        console.print()
        base_url = click.prompt("Proxy URL", default="http://localhost:4000")
        is_valid, msg = validate_proxy_url(base_url)
        if not is_valid:
            console.print(f"[yellow]Warning: {msg}[/yellow]")

    # Step 2: LiteLLM API key (optional)
    console.print("\n[bold]Step 2: LiteLLM API key (optional)[/bold]")
    console.print("If your proxy requires authentication, enter the LiteLLM API key.")
    console.print("This is used for cost tracking and budget controls.")
    console.print()

    if click.confirm("Configure LiteLLM API key?", default=False):
        litellm_key = click.prompt("LiteLLM API key", hide_input=True)
        headers = {"x-litellm-api-key": f"Bearer {litellm_key}"}
        try:
            save_config_value("llm.extra_headers", json.dumps(headers), project=False)
            console.print("[green]✓ LiteLLM API key saved[/green]")
        except ConfigWriteError as e:
            console.print(f"[red]Error saving headers: {e}[/red]")

    # Step 3: OAuth token for Claude Max
    console.print("\n[bold]Step 3: Claude Max OAuth token[/bold]")
    console.print("To use your Claude Max subscription instead of per-token API pricing,")
    console.print("you need an OAuth token from Claude Code.")
    console.print()

    if click.confirm("Configure Claude Max OAuth token?", default=True):
        # Check for existing Claude Code credentials
        credentials_path = Path.home() / ".claude" / ".credentials.json"

        if credentials_path.exists():
            if click.confirm("Found Claude Code credentials. Import token from there?", default=True):
                try:
                    with open(credentials_path) as f:
                        creds = json.load(f)
                    token = (
                        creds.get("accessToken")
                        or creds.get("access_token")
                        or creds.get("claudeAiOauth", {}).get("accessToken")
                    )
                    if token and len(token) >= 20:
                        save_config_value("llm.oauth_token", token, project=False)
                        console.print("[green]✓ OAuth token imported from Claude Code[/green]")
                    else:
                        console.print("[yellow]No valid token found in credentials[/yellow]")
                except (json.JSONDecodeError, ConfigWriteError) as e:
                    console.print(f"[red]Error importing token: {e}[/red]")
            else:
                console.print("[dim]Skipping OAuth token configuration[/dim]")
        else:
            console.print("To get your OAuth token:")
            console.print("  1. Install Claude Code: npm install -g @anthropic/claude-code")
            console.print("  2. Run: claude")
            console.print("  3. Type: /login")
            console.print("  4. Then run: chapgent auth login --import-claude-code")
            console.print()

            if click.confirm("Do you have a token to enter manually?", default=False):
                token = click.prompt("Paste your OAuth token", hide_input=True)
                if token and len(token) >= 20:
                    try:
                        save_config_value("llm.oauth_token", token, project=False)
                        console.print("[green]✓ OAuth token saved[/green]")
                    except ConfigWriteError as e:
                        console.print(f"[red]Error saving token: {e}[/red]")
                else:
                    console.print("[yellow]Token appears invalid, skipping[/yellow]")

    # Step 4: Save base_url
    console.print("\n[bold]Step 4: Save proxy configuration[/bold]")
    try:
        config_path, _ = save_config_value("llm.base_url", base_url, project=False)
        console.print(f"[green]✓ Proxy URL saved: {base_url}[/green]")
    except ConfigWriteError as e:
        console.print(f"[red]Error saving proxy URL: {e}[/red]")
        raise SystemExit(1)

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold green]Proxy Setup Complete![/bold green]")
    console.print("=" * 60)
    console.print(f"\nProxy URL: {base_url}")
    console.print(f"Config: {config_path}")

    if mode_choice == "1":
        console.print("\n[bold]Next steps:[/bold]")
        console.print(f"  1. Start the proxy: chapgent proxy start --port {port}")
        console.print("  2. In another terminal: chapgent chat")
    else:
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Ensure your remote proxy is running")
        console.print("  2. Run: chapgent chat")

    console.print("\nFor more help: chapgent help proxy")


if __name__ == "__main__":
    cli()
