"""TUI module for Chapgent."""

from chapgent.tui.app import ChapgentApp
from chapgent.tui.commands import (
    SLASH_COMMANDS,
    SlashCommand,
    format_command_list,
    get_command_help,
    get_slash_command,
    list_slash_commands,
    parse_slash_command,
)
from chapgent.tui.screens import (
    ThemePickerScreen,
)
from chapgent.tui.widgets import (
    CommandPalette,
    CommandPaletteItem,
    ConversationPanel,
    MessageInput,
    PaletteCommand,
    PermissionPrompt,
    SessionItem,
    SessionsSidebar,
    ToolPanel,
    ToolProgressItem,
    ToolResultItem,
    ToolStatus,
)

__all__ = [
    # App
    "ChapgentApp",
    # Commands
    "SLASH_COMMANDS",
    "SlashCommand",
    "format_command_list",
    "get_command_help",
    "get_slash_command",
    "list_slash_commands",
    "parse_slash_command",
    # Screens
    "ThemePickerScreen",
    # Widgets
    "CommandPalette",
    "CommandPaletteItem",
    "ConversationPanel",
    "MessageInput",
    "PaletteCommand",
    "PermissionPrompt",
    "SessionItem",
    "SessionsSidebar",
    "ToolPanel",
    "ToolProgressItem",
    "ToolResultItem",
    "ToolStatus",
]
