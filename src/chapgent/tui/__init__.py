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
from chapgent.tui.highlighter import (
    HighlightedCode,
    PygmentsHighlighter,
    SyntaxHighlighter,
    get_highlighter,
)
from chapgent.tui.markdown import (
    MarkdownConfig,
    MarkdownMessage,
    MarkdownRenderer,
)
from chapgent.tui.screens import (
    ConfigShowScreen,
    HelpScreen,
    LLMSettingsScreen,
    SystemPromptScreen,
    ThemePickerScreen,
    ToolsScreen,
    TUISettingsScreen,
)
from chapgent.tui.themes import (
    DEFAULT_DARK_THEME,
    DEFAULT_LIGHT_THEME,
    THEME_MAPPING,
    get_syntax_theme,
    is_dark_theme,
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
    # Markdown
    "MarkdownConfig",
    "MarkdownMessage",
    "MarkdownRenderer",
    # Commands
    "SLASH_COMMANDS",
    "SlashCommand",
    "format_command_list",
    "get_command_help",
    "get_slash_command",
    "list_slash_commands",
    "parse_slash_command",
    # Screens
    "ConfigShowScreen",
    "HelpScreen",
    "LLMSettingsScreen",
    "SystemPromptScreen",
    "ThemePickerScreen",
    "ToolsScreen",
    "TUISettingsScreen",
    # Themes
    "DEFAULT_DARK_THEME",
    "DEFAULT_LIGHT_THEME",
    "THEME_MAPPING",
    "get_syntax_theme",
    "is_dark_theme",
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
