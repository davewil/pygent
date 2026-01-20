"""TUI module for Chapgent."""

from chapgent.tui.app import ChapgentApp
from chapgent.tui.highlighter import (
    HighlightedCode,
    PygmentsHighlighter,
    SyntaxHighlighter,
    get_highlighter,
)
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
    HelpScreen,
    LLMSettingsScreen,
    ThemePickerScreen,
    ToolsScreen,
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
    # Highlighter
    "HighlightedCode",
    "PygmentsHighlighter",
    "SyntaxHighlighter",
    "get_highlighter",
    # Commands
    "SLASH_COMMANDS",
    "SlashCommand",
    "format_command_list",
    "get_command_help",
    "get_slash_command",
    "list_slash_commands",
    "parse_slash_command",
    # Screens
    "HelpScreen",
    "LLMSettingsScreen",
    "ThemePickerScreen",
    "ToolsScreen",
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
