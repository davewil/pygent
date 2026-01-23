"""LiteLLM proxy commands."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]
from rich.console import Console

from chapgent.cli.main import cli
from chapgent.config.writer import ConfigWriteError, save_config_value
from chapgent.ux.first_run import (
    check_proxy_setup_status,
    get_proxy_welcome_message,
    validate_proxy_url,
)

# Default proxy settings
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 4000


def _is_proxy_running(host: str = DEFAULT_PROXY_HOST, port: int = DEFAULT_PROXY_PORT) -> bool:
    """Check if proxy is already running by trying to connect."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _start_proxy_background(host: str = DEFAULT_PROXY_HOST, port: int = DEFAULT_PROXY_PORT) -> bool:
    """Start the LiteLLM proxy in the background.

    Returns True if proxy started successfully, False otherwise.
    """
    import os
    import time

    # Generate LiteLLM config
    config = {
        "model_list": [
            {
                "model_name": "anthropic-claude",
                "litellm_params": {"model": "anthropic/claude-sonnet-4-20250514"},
            },
            {
                "model_name": "claude-sonnet-4-20250514",
                "litellm_params": {"model": "anthropic/claude-sonnet-4-20250514"},
            },
            {
                "model_name": "claude-3-5-haiku-20241022",
                "litellm_params": {"model": "anthropic/claude-3-5-haiku-20241022"},
            },
        ],
        "general_settings": {"forward_client_headers_to_llm_api": True},
        "litellm_settings": {"drop_params": True},
    }

    # Write config file
    config_dir = Path(tempfile.gettempdir()) / "chapgent"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "litellm-proxy.yaml"

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    # Start proxy in background
    # Find litellm binary - check venv first, then system PATH
    venv_litellm = Path(sys.executable).parent / "litellm"
    if venv_litellm.exists():
        litellm_cmd = str(venv_litellm)
    else:
        found_litellm = shutil.which("litellm")
        if not found_litellm:
            return False
        litellm_cmd = found_litellm

    try:
        # LiteLLM requires ANTHROPIC_API_KEY env var even when using OAuth via proxy.
        # The actual auth comes from the forwarded Authorization header, but the proxy
        # needs this env var to initialize. We use a placeholder value.
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = env.get("ANTHROPIC_API_KEY", "placeholder-for-oauth-proxy")

        subprocess.Popen(
            [litellm_cmd, "--config", str(config_path), "--host", host, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process
            env=env,
        )
    except FileNotFoundError:
        return False

    # Wait for proxy to be ready (up to 10 seconds)
    for _ in range(20):
        time.sleep(0.5)
        if _is_proxy_running(host, port):
            return True

    return False


@cli.group()
def proxy() -> None:
    """LiteLLM proxy server commands."""
    pass


@proxy.command()
@click.option("--port", default=4000, help="Port to run proxy on")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--no-configure", is_flag=True, help="Don't auto-configure base_url in config")
def start(port: int, host: str, no_configure: bool) -> None:
    """Start LiteLLM proxy server (foreground).

    Runs a local LiteLLM Gateway that forwards OAuth tokens to Anthropic,
    enabling Claude Max subscription usage with cost tracking.

    By default, this command also configures chapgent to use this proxy
    by setting llm.base_url in your config. Use --no-configure to skip this.
    """
    console = Console()

    proxy_url = f"http://{host}:{port}"

    # Auto-configure base_url unless --no-configure is set
    if not no_configure:
        try:
            save_config_value("llm.base_url", proxy_url)
            console.print(f"[green]✓ Configured llm.base_url = {proxy_url}[/green]\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not auto-configure base_url: {e}[/yellow]")
            console.print("[dim]You can manually set it with:[/dim]")
            console.print(f"  chapgent config set llm.base_url {proxy_url}\n")

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

    # Find litellm binary - check venv first, then system PATH
    venv_litellm = Path(sys.executable).parent / "litellm"
    if venv_litellm.exists():
        litellm_cmd = str(venv_litellm)
    else:
        found_litellm = shutil.which("litellm")
        if not found_litellm:
            console.print("[red]Error: litellm CLI not found. Install with: pip install 'litellm[proxy]'[/red]")
            raise SystemExit(1)
        litellm_cmd = found_litellm

    console.print("[bold]Starting LiteLLM Proxy[/bold]\n")
    console.print(f"Config: {config_path}")
    console.print(f"URL:    {proxy_url}\n")
    console.print("[dim]In another terminal, run:[/dim]")
    console.print("  chapgent chat\n")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    console.print("-" * 50)

    try:
        subprocess.run(
            [litellm_cmd, "--config", str(config_path), "--host", host, "--port", str(port)],
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Proxy stopped[/yellow]")


@proxy.command("setup")
def proxy_setup() -> None:
    """Interactive setup wizard for LiteLLM proxy configuration.

    Guides you through configuring chapgent to use a LiteLLM proxy
    for cost tracking, budget controls, and Claude Max subscription support.
    """
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
        console.print("\n[dim]To start the proxy, run:[/dim]")
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
        raise SystemExit(1) from None

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


__all__ = ["proxy", "DEFAULT_PROXY_HOST", "DEFAULT_PROXY_PORT"]
