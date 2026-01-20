"""Slash command system for the TUI.

This module provides a registry of slash commands that users can type
in the message input (e.g., /help, /theme, /model) for quick access
to common actions without using the command palette.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SlashCommand:
    """A slash command that can be typed in the message input.

    Attributes:
        name: The command name (without the leading slash).
        aliases: Alternative names for the command.
        description: Short description of what the command does.
        action: The action method name to call (e.g., "show_help").
        args_pattern: Optional pattern showing expected arguments (e.g., "[topic]").
    """

    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    action: str = ""
    args_pattern: str | None = None

    def matches(self, command: str) -> bool:
        """Check if a command string matches this slash command.

        Args:
            command: The command to check (without leading slash).

        Returns:
            True if the command matches this SlashCommand's name or aliases.
        """
        command_lower = command.lower()
        if command_lower == self.name.lower():
            return True
        return any(command_lower == alias.lower() for alias in self.aliases)


# Registry of all slash commands
SLASH_COMMANDS: list[SlashCommand] = [
    # Help & Documentation
    SlashCommand(
        name="help",
        aliases=["h", "?"],
        description="Show help topics or a specific topic",
        action="show_help",
        args_pattern="[topic]",
    ),
    SlashCommand(
        name="tools",
        aliases=[],
        description="View available tools",
        action="show_tools",
        args_pattern="[category]",
    ),
    # Settings screens
    SlashCommand(
        name="theme",
        aliases=[],
        description="Change the TUI theme",
        action="show_theme_picker",
    ),
    SlashCommand(
        name="model",
        aliases=["llm"],
        description="Configure LLM settings",
        action="show_llm_settings",
    ),
    SlashCommand(
        name="tui",
        aliases=["ui"],
        description="Configure TUI settings",
        action="show_tui_settings",
    ),
    SlashCommand(
        name="prompt",
        aliases=["sysprompt"],
        description="Configure system prompt",
        action="show_prompt_settings",
    ),
    # Config commands
    SlashCommand(
        name="config",
        aliases=["cfg", "settings"],
        description="Show or set configuration",
        action="handle_config",
        args_pattern="[show|set <key> <value>]",
    ),
    # Session commands (map to existing actions)
    SlashCommand(
        name="new",
        aliases=["n"],
        description="Start a new session",
        action="new_session",
    ),
    SlashCommand(
        name="save",
        aliases=["s"],
        description="Save the current session",
        action="save_session",
    ),
    # UI toggle commands
    SlashCommand(
        name="sidebar",
        aliases=["sb"],
        description="Toggle the sessions sidebar",
        action="toggle_sidebar",
    ),
    SlashCommand(
        name="toolpanel",
        aliases=["tp", "tools-panel"],
        description="Toggle the tool panel",
        action="toggle_tools",
    ),
    # Utility commands
    SlashCommand(
        name="clear",
        aliases=["cls"],
        description="Clear the conversation",
        action="clear",
    ),
    SlashCommand(
        name="quit",
        aliases=["exit", "q"],
        description="Exit the application",
        action="quit",
    ),
]


def get_slash_command(name: str) -> SlashCommand | None:
    """Look up a slash command by name or alias.

    Args:
        name: The command name (without leading slash).

    Returns:
        The matching SlashCommand, or None if not found.
    """
    for cmd in SLASH_COMMANDS:
        if cmd.matches(name):
            return cmd
    return None


def parse_slash_command(user_input: str) -> tuple[SlashCommand | None, list[str]]:
    """Parse user input into a slash command and arguments.

    Args:
        user_input: The full user input (including leading slash).

    Returns:
        Tuple of (SlashCommand or None, list of argument strings).
        Returns (None, []) if the input is not a slash command or command not found.

    Example:
        >>> parse_slash_command("/help tools")
        (SlashCommand(name="help", ...), ["tools"])

        >>> parse_slash_command("/config set llm.model gpt-4")
        (SlashCommand(name="config", ...), ["set", "llm.model", "gpt-4"])

        >>> parse_slash_command("hello")
        (None, [])
    """
    user_input = user_input.strip()

    # Must start with /
    if not user_input.startswith("/"):
        return (None, [])

    # Remove leading slash and split into parts
    parts = user_input[1:].split()

    if not parts:
        return (None, [])

    # First part is the command name
    command_name = parts[0]
    args = parts[1:]

    # Look up the command
    command = get_slash_command(command_name)

    return (command, args)


def list_slash_commands() -> list[tuple[str, str, str | None]]:
    """List all available slash commands.

    Returns:
        List of tuples (name, description, args_pattern) for each command.
    """
    return [(cmd.name, cmd.description, cmd.args_pattern) for cmd in SLASH_COMMANDS]


def get_command_help(command_name: str) -> str | None:
    """Get help text for a specific slash command.

    Args:
        command_name: The command name (without leading slash).

    Returns:
        Help text for the command, or None if not found.
    """
    cmd = get_slash_command(command_name)
    if cmd is None:
        return None

    # Build help text
    lines = [f"/{cmd.name}"]

    if cmd.args_pattern:
        lines[0] += f" {cmd.args_pattern}"

    lines.append(f"  {cmd.description}")

    if cmd.aliases:
        aliases_str = ", ".join(f"/{alias}" for alias in cmd.aliases)
        lines.append(f"  Aliases: {aliases_str}")

    return "\n".join(lines)


def format_command_list() -> str:
    """Format all commands as a displayable string.

    Returns:
        Formatted string listing all commands with descriptions.
    """
    lines = ["Available Slash Commands:", ""]

    for cmd in SLASH_COMMANDS:
        cmd_str = f"/{cmd.name}"
        if cmd.args_pattern:
            cmd_str += f" {cmd.args_pattern}"

        # Pad for alignment
        lines.append(f"  {cmd_str:<30} {cmd.description}")

        if cmd.aliases:
            aliases_str = ", ".join(f"/{alias}" for alias in cmd.aliases)
            lines.append(f"    {'Aliases:':<28} {aliases_str}")

    return "\n".join(lines)
