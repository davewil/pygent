"""First-run experience for new users.

Detects if this is a new user and guides them through initial setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chapgent.config.settings import Settings


@dataclass
class SetupStatus:
    """Status of user setup.

    Attributes:
        is_first_run: True if this appears to be a first run.
        has_api_key: True if an API key is configured.
        has_config_file: True if a config file exists.
        config_path: Path to the user config file.
        missing_items: List of items that need to be configured.
    """

    is_first_run: bool
    has_api_key: bool
    has_config_file: bool
    config_path: Path
    missing_items: list[str]


def get_config_path() -> Path:
    """Get the user config file path.

    Returns:
        Path to the user config file.
    """
    return Path.home() / ".config" / "chapgent" / "config.toml"


def check_api_key() -> bool:
    """Check if an API key is configured.

    Checks environment variables and returns True if any API key is set.

    Returns:
        True if an API key is found.
    """
    api_key_vars = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "CHAPGENT_API_KEY",
    ]

    for var in api_key_vars:
        if os.environ.get(var):
            return True

    return False


def check_setup_status() -> SetupStatus:
    """Check the current setup status.

    Returns:
        SetupStatus with details about what's configured.
    """
    config_path = get_config_path()
    has_config = config_path.exists()
    has_api_key = check_api_key()

    missing = []
    if not has_api_key:
        missing.append("API key")
    if not has_config:
        missing.append("Config file")

    # Consider it a first run if no API key and no config
    is_first_run = not has_api_key and not has_config

    return SetupStatus(
        is_first_run=is_first_run,
        has_api_key=has_api_key,
        has_config_file=has_config,
        config_path=config_path,
        missing_items=missing,
    )


def get_welcome_message() -> str:
    """Get the welcome message for first-time users.

    Returns:
        Formatted welcome message string.
    """
    return """\
================================================================================
                        Welcome to Chapgent!
================================================================================

Chapgent is an AI-powered coding agent for the command line.

It can help you with:
  - Reading and editing code files
  - Running shell commands
  - Git operations
  - Searching your codebase
  - Running tests
  - And much more!

================================================================================
"""


def get_setup_instructions(status: SetupStatus) -> str:
    """Get setup instructions based on current status.

    Args:
        status: Current SetupStatus.

    Returns:
        Formatted setup instructions.
    """
    lines = ["To get started, you need to configure a few things:\n"]

    step = 1

    if not status.has_api_key:
        lines.append(f"{step}. SET UP YOUR API KEY")
        lines.append("   Option A: Environment variable (recommended)")
        lines.append("     export ANTHROPIC_API_KEY=your-api-key")
        lines.append("")
        lines.append("   Option B: Config file")
        lines.append("     chapgent config set llm.api_key your-api-key")
        lines.append("")
        lines.append("   Get an API key at: https://console.anthropic.com/")
        lines.append("")
        step += 1

    if not status.has_config_file:
        lines.append(f"{step}. CREATE A CONFIG FILE (optional)")
        lines.append("   chapgent config init")
        lines.append("")
        lines.append("   This creates a config file with helpful comments.")
        lines.append("")
        step += 1

    lines.append(f"{step}. START CHATTING")
    lines.append("   chapgent chat")
    lines.append("")
    lines.append("For more help:")
    lines.append("   chapgent help quickstart")
    lines.append("   chapgent --help")

    return "\n".join(lines)


def get_api_key_help() -> str:
    """Get detailed help for setting up an API key.

    Returns:
        Formatted API key help text.
    """
    return """\
API Key Setup
=============

Chapgent needs an API key to communicate with the AI model.

OPTION 1: Environment Variable (Recommended)
---------------------------------------------
Add to your shell profile (~/.bashrc, ~/.zshrc, etc.):

  export ANTHROPIC_API_KEY=sk-ant-api03-...

Then restart your terminal or run:

  source ~/.bashrc  # or ~/.zshrc

OPTION 2: Config File
---------------------
Run:

  chapgent config set llm.api_key sk-ant-api03-...

Note: The key will be stored in plain text in your config file.
Environment variables are more secure.

GET AN API KEY
--------------
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Copy the key (it starts with sk-ant-api03-)

TROUBLESHOOTING
---------------
- Make sure you copied the entire key
- Keys cannot be viewed again after creation
- If lost, create a new key
- Check your usage limits at console.anthropic.com
"""


def validate_api_key_format(key: str) -> tuple[bool, str]:
    """Validate the format of an API key.

    Args:
        key: The API key to validate.

    Returns:
        Tuple of (is_valid, message).
    """
    key = key.strip()

    if not key:
        return False, "API key cannot be empty"

    # Anthropic keys
    if key.startswith("sk-ant-"):
        if len(key) < 40:
            return False, "Anthropic API key appears too short"
        return True, "Valid Anthropic API key format"

    # OpenAI keys
    if key.startswith("sk-"):
        if len(key) < 20:
            return False, "OpenAI API key appears too short"
        return True, "Valid OpenAI API key format"

    # Unknown format but allow it
    if len(key) < 10:
        return False, "API key appears too short"

    return True, "API key format accepted"


def should_show_first_run_prompt() -> bool:
    """Determine if the first-run prompt should be shown.

    This checks multiple conditions to avoid showing the prompt
    repeatedly or unnecessarily.

    Returns:
        True if first-run prompt should be shown.
    """
    status = check_setup_status()

    # Only show if it's truly a first run
    if not status.is_first_run:
        return False

    # Don't show if API key exists (even without config file)
    if status.has_api_key:
        return False

    return True


def format_setup_complete_message(settings: Settings | None = None) -> str:
    """Format the setup complete message.

    Args:
        settings: Optional loaded settings to show summary.

    Returns:
        Formatted completion message.
    """
    lines = [
        "================================================================================",
        "                         Setup Complete!",
        "================================================================================",
        "",
        "You're all set to use Chapgent.",
        "",
        "Quick commands:",
        "  chapgent chat           Start an interactive session",
        "  chapgent help           Show help topics",
        "  chapgent tools          List available tools",
        "",
    ]

    if settings:
        lines.extend(
            [
                "Current configuration:",
                f"  Model:    {settings.llm.model}",
                f"  Provider: {settings.llm.provider}",
                "",
            ]
        )

    lines.extend(
        [
            "Tips:",
            "  - Use Ctrl+S to save your session",
            "  - Use Ctrl+Shift+P for the command palette",
            "  - Use 'chapgent help <topic>' for detailed help",
            "",
            "================================================================================",
        ]
    )

    return "\n".join(lines)


def create_first_run_marker() -> None:
    """Create a marker file to indicate first run has been completed.

    This prevents showing the first-run prompt again.
    """
    marker_path = Path.home() / ".local" / "share" / "chapgent" / ".first_run_complete"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.touch()


def has_completed_first_run() -> bool:
    """Check if first run has been completed.

    Returns:
        True if the first-run marker exists.
    """
    marker_path = Path.home() / ".local" / "share" / "chapgent" / ".first_run_complete"
    return marker_path.exists()
