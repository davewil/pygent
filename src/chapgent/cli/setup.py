"""Interactive setup command."""

import asyncio
import sys
from pathlib import Path
from typing import Any

import click

from chapgent.cli.main import cli
from chapgent.config.loader import load_config
from chapgent.config.writer import get_config_paths, write_toml


def _setup_api_key(
    existing: dict[str, Any],
    user_config: Path,
    validate_api_key_format: Any,
) -> None:
    """Set up authentication using an Anthropic API key."""
    click.echo()
    click.echo("=" * 60)
    click.echo("API Key Setup")
    click.echo("=" * 60)
    click.echo()
    click.echo("Get your API key from: https://console.anthropic.com/")
    click.echo("Keys start with 'sk-ant-api03-'")
    click.echo()

    api_key = click.prompt("Enter your Anthropic API key", hide_input=True)

    is_valid, message = validate_api_key_format(api_key)
    if not is_valid:
        click.echo(f"Warning: {message}")
        if not click.confirm("Continue anyway?"):
            click.echo("Setup cancelled.")
            return

    existing["llm"]["api_key"] = api_key
    existing["llm"]["auth_mode"] = "api"  # Set auth mode
    # Clear any proxy settings that might conflict
    existing["llm"].pop("base_url", None)
    existing["llm"].pop("oauth_token", None)

    write_toml(user_config, existing)
    click.echo()
    click.echo(f"API key saved to {user_config}")
    click.echo()
    click.echo("You're all set! Run 'chapgent chat' to start.")


def _setup_claude_max(existing: dict[str, Any], user_config: Path) -> None:
    """Set up authentication using Claude Max subscription via LiteLLM proxy."""
    import json

    click.echo()
    click.echo("=" * 60)
    click.echo("Claude Max Setup")
    click.echo("=" * 60)
    click.echo()
    click.echo("This setup requires:")
    click.echo("  1. A Claude Max subscription ($100/month)")
    click.echo("  2. Claude Code CLI installed and logged in")
    click.echo()

    # Step 1: Check for Claude Code credentials
    click.echo("Step 1: Import OAuth token from Claude Code")
    click.echo("-" * 40)

    claude_creds_path = Path.home() / ".claude" / ".credentials.json"
    if not claude_creds_path.exists():
        click.echo()
        click.echo("Claude Code credentials not found!")
        click.echo()
        click.echo("Please install and log in to Claude Code first:")
        click.echo("  1. Install: npm install -g @anthropic-ai/claude-code")
        click.echo("  2. Run: claude")
        click.echo("  3. Type: /login")
        click.echo("  4. Complete the login in your browser")
        click.echo("  5. Run 'chapgent setup' again")
        click.echo()
        return

    # Try to read the OAuth token
    try:
        with open(claude_creds_path) as f:
            creds = json.load(f)

        # Token can be in different locations depending on Claude Code version
        oauth_token = (
            creds.get("accessToken") or creds.get("access_token") or creds.get("claudeAiOauth", {}).get("accessToken")
        )

        if not oauth_token:
            click.echo("No OAuth token found in Claude Code credentials.")
            click.echo("Please run 'claude' and use '/login' to authenticate.")
            return

        click.echo("Found OAuth token from Claude Code.")
        existing["llm"]["oauth_token"] = oauth_token

    except Exception as e:
        click.echo(f"Error reading Claude Code credentials: {e}")
        return

    # Step 2: Configure proxy URL
    click.echo()
    click.echo("Step 2: Configure LiteLLM Proxy")
    click.echo("-" * 40)
    click.echo()
    click.echo("The proxy forwards your OAuth token to Anthropic.")
    click.echo()

    proxy_choice = click.prompt(
        "Proxy setup",
        type=click.Choice(["local", "remote"]),
        default="local",
    )

    if proxy_choice == "local":
        port = click.prompt("Local proxy port", default="4000")
        base_url = f"http://localhost:{port}"
        click.echo()
        click.echo("To start the proxy, run in a separate terminal:")
        click.echo(f"  chapgent proxy start --port {port}")
        click.echo()
    else:
        base_url = click.prompt("Remote proxy URL", default="http://localhost:4000")

    existing["llm"]["base_url"] = base_url
    existing["llm"]["auth_mode"] = "max"  # Set auth mode
    # Clear API key if using OAuth
    existing["llm"].pop("api_key", None)

    write_toml(user_config, existing)
    click.echo()
    click.echo(f"Configuration saved to {user_config}")
    click.echo()
    click.echo("Setup complete! To use chapgent:")
    if proxy_choice == "local":
        click.echo(f"  1. Start the proxy: chapgent proxy start --port {port}")
        click.echo("  2. In another terminal: chapgent chat")
    else:
        click.echo("  Run: chapgent chat")


@cli.command()
def setup() -> None:
    """Interactive setup for first-time users.

    Guides you through configuring chapgent with either:
    - Option 1: Anthropic API key (pay-per-token)
    - Option 2: Claude Max subscription (unlimited via LiteLLM proxy)
    """
    from chapgent.ux.first_run import (
        check_setup_status,
        format_setup_complete_message,
        get_welcome_message,
        validate_api_key_format,
    )

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]

    status = check_setup_status()

    # Show welcome message
    click.echo(get_welcome_message())

    # Check if already fully configured
    if status.has_api_key and status.has_config_file:
        click.echo("You're already set up!")
        click.echo()
        click.echo("Current status:")
        click.echo("  API key: configured")
        click.echo(f"  Config:  {status.config_path}")
        click.echo()
        click.echo("Run 'chapgent chat' to start chatting.")
        return

    # Present the two options
    click.echo("How would you like to authenticate?")
    click.echo()
    click.echo("  [1] Anthropic API Key (pay-per-token)")
    click.echo("      - Get a key at https://console.anthropic.com/")
    click.echo("      - Billed based on usage")
    click.echo()
    click.echo("  [2] Claude Max Subscription (unlimited usage)")
    click.echo("      - Requires Claude Max subscription ($100/month)")
    click.echo("      - Uses LiteLLM proxy to forward OAuth tokens")
    click.echo("      - Requires Claude Code CLI for authentication")
    click.echo()

    choice = click.prompt("Choose an option", type=click.Choice(["1", "2"]), default="1")

    user_config, _ = get_config_paths()
    user_config.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if user_config.exists():
        with open(user_config, "rb") as f:
            existing = tomllib.load(f)

    if "llm" not in existing:
        existing["llm"] = {}

    if choice == "1":
        # Option 1: API Key setup
        _setup_api_key(existing, user_config, validate_api_key_format)
    else:
        # Option 2: Claude Max setup
        _setup_claude_max(existing, user_config)

    # Show completion message
    click.echo()
    try:
        settings = asyncio.run(load_config())
        click.echo(format_setup_complete_message(settings))
    except Exception:
        click.echo(format_setup_complete_message(None))


__all__ = ["setup"]
