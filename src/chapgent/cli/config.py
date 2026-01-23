"""Configuration CLI commands."""

import asyncio
import subprocess
from pathlib import Path

import click

from chapgent.cli.main import cli
from chapgent.config.loader import load_config
from chapgent.config.writer import (
    ConfigWriteError,
    get_config_paths,
    save_config_value,
    write_default_config,
)


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
    click.echo(f"  max_output_tokens: {settings.llm.max_output_tokens}")
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
    try:
        config_path, typed_value = save_config_value(key, value, project=project)
    except ConfigWriteError as e:
        raise click.ClickException(str(e)) from None

    location = "project" if project else "user"
    click.echo(f"Set {key} = {typed_value} in {location} config")


__all__ = ["config"]
