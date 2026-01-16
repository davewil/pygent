import asyncio
import uuid

import click

from pygent.core.agent import Agent
from pygent.core.permissions import PermissionManager
from pygent.core.providers import LLMProvider
from pygent.session.models import Session
from pygent.session.storage import SessionStorage
from pygent.tools.registry import ToolRegistry
from pygent.tui.app import PygentApp


@click.group()
@click.version_option()
def cli():
    """Pygent - AI-powered coding agent."""
    pass


@cli.command()
@click.option("--session", "-s", help="Resume a session by ID")
@click.option("--new", "-n", is_flag=True, help="Start a new session")
def chat(session: str | None, new: bool):
    """Start interactive chat session."""

    # 1. Load Config (Default for now)
    # config = asyncio.run(load_config())
    # TODO: Pass config to components

    # 2. Initialize Components
    provider = LLMProvider(model="anthropic/claude-3-5-sonnet-20241022")  # Default hardcoded for MVP if not in config
    # Note: LLMProvider in specs/phase-1-mvp.md signature is (model, api_key).
    # We should check providers.py to match signature.

    tools = ToolRegistry()
    # Register basic tools
    # We need to import the tool definitions or functions decorated with @tool
    # The current implementation of filesystem.py and shell.py uses @tool decorator
    # which returns a function with .tool_def attribute or we need to manage registration.
    # Let's check how tools are implemented. Assuming standard registry pattern.

    # For MVP we manually register known tools
    # Actually, the @tool decorator usually registers or we need to pass the function.
    # Let's check existing tool implementations.
    # But I will proceed with assumption and fix if needed in verification.

    # 3. Session Management
    storage = SessionStorage()

    current_session = None
    if session:
        current_session = asyncio.run(storage.load(session))
        if not current_session:
            click.echo(f"Session {session} not found.")
            return
    else:
        # Create new session
        current_session = Session(id=str(uuid.uuid4()), working_directory=".", messages=[], tool_history=[])
        # async save? storage.save(current_session)

    # 6. Initialize App & Wiring
    # We initialize the app first so we can use it in the permission callback
    app = PygentApp()

    async def permission_callback(tool_name: str, risk: str, args: dict) -> bool:
        # We need to run this on the main app loop
        # Since this callback is async, we can just await the app method
        return await app.get_permission(tool_name, args)

    # 4. Permissions (now with callback)
    permissions = PermissionManager(prompt_callback=permission_callback)

    # 5. Agent
    # For MVP manual tool registration
    # Inspecting src/pygent/tools/filesystem.py and shell.py shows they use @tool decorator
    # We need to import them to register
    from pygent.tools.filesystem import edit_file, list_files, read_file
    from pygent.tools.shell import shell

    tools.register(read_file)
    tools.register(list_files)
    tools.register(edit_file)
    tools.register(shell)

    agent = Agent(provider=provider, tools=tools, permissions=permissions, session=current_session)

    # Connect agent to app
    app.agent = agent

    # 7. Run TUI
    app.run()


@cli.command()
def sessions():
    """List saved sessions."""
    click.echo("Sessions list not implemented yet.")


@cli.command()
@click.argument("session_id")
def resume(session_id: str):
    """Resume a specific session."""
    click.echo(f"Resuming {session_id} not implemented yet.")


@cli.command()
def config():
    """Show current configuration."""
    click.echo("Config view not implemented yet.")


if __name__ == "__main__":
    cli()
