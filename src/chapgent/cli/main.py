"""Root CLI group and core commands."""

import asyncio

import click

from chapgent.session.storage import SessionStorage


@click.group()
@click.version_option()
def cli() -> None:
    """Chapgent - AI-powered coding agent."""
    pass


@cli.command()
@click.option("--session", "-s", help="Resume a session by ID")
@click.option("--new", "-n", is_flag=True, help="Start a new session")
@click.option("--mock", "-m", is_flag=True, help="Use mock provider (no API key needed)")
@click.option(
    "--mode",
    type=click.Choice(["api", "max"]),
    help="Auth mode: 'api' for direct API key, 'max' for Claude Max subscription",
)
def chat(session: str | None, new: bool, mock: bool, mode: str | None) -> None:
    """Start interactive chat session."""
    from chapgent.cli.bootstrap import init_agent_and_app

    app = asyncio.run(init_agent_and_app(session_id=session, is_new=new, use_mock=mock, auth_mode_override=mode))
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
    from chapgent.cli.bootstrap import init_agent_and_app

    app = asyncio.run(init_agent_and_app(session_id=session_id, use_mock=mock))
    app.run()


__all__ = ["cli"]
