"""Authentication commands."""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console

from chapgent.cli.main import cli
from chapgent.config.loader import load_config
from chapgent.config.writer import ConfigWriteError, save_config_value


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
            raise SystemExit(1) from None

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
        console.print("[green]✓ OAuth token saved successfully![/green]")
        console.print(f"  Config: {config_path}")
    except ConfigWriteError as e:
        raise click.ClickException(str(e)) from None


@auth.command()
def logout() -> None:
    """Remove stored authentication tokens."""
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
    import shutil
    import subprocess

    settings = asyncio.run(load_config())
    console = Console()

    console.print("\n[bold]Authentication Status[/bold]\n")

    # Show auth mode
    mode = settings.llm.auth_mode
    if mode == "max":
        console.print("[cyan]Mode: Claude Max (subscription)[/cyan]")
    else:
        console.print("[cyan]Mode: Claude API (pay-per-token)[/cyan]")
    console.print()

    # Show credentials based on mode
    if mode == "max":
        # Check if Claude Code CLI is installed
        claude_path = shutil.which("claude")
        if claude_path:
            console.print("[green]✓ Claude Code CLI installed[/green]")
            console.print(f"  Path: {claude_path}")

            # Check if authenticated by running claude auth status
            try:
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    console.print(f"  Version: {result.stdout.strip()}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        else:
            console.print("[yellow]✗ Claude Code CLI not installed[/yellow]")
            console.print("  Install: npm install -g @anthropic-ai/claude-code")
            console.print("  Then run: claude auth login")
    else:  # api mode
        if settings.llm.api_key:
            console.print("[green]✓ API key configured[/green]")
            key = settings.llm.api_key
            masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
            console.print(f"  Key: {masked}")
        else:
            console.print("[yellow]✗ API key not configured[/yellow]")
            console.print("  Run: chapgent setup")

    console.print()
    console.print("[dim]Switch modes with: chapgent chat --mode api|max[/dim]")
    console.print()


__all__ = ["auth"]
