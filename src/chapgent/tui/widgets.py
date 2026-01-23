from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Pretty, Static

from .markdown import MarkdownConfig, MarkdownMessage, MarkdownRenderer
from .themes.syntax import get_syntax_theme


class ToolStatus(Enum):
    """Status of a tool execution.

    Attributes:
        WAITING: Tool is queued for execution.
        RUNNING: Tool is currently executing.
        COMPLETED: Tool completed successfully.
        ERROR: Tool execution failed.
        CACHED: Result came from cache.
        PERMISSION_DENIED: User denied permission.
    """

    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CACHED = "cached"
    PERMISSION_DENIED = "permission_denied"


# Status icons for each tool status
STATUS_ICONS: dict[ToolStatus, str] = {
    ToolStatus.WAITING: "⏸",
    ToolStatus.RUNNING: "⏳",
    ToolStatus.COMPLETED: "✅",
    ToolStatus.ERROR: "❌",
    ToolStatus.CACHED: "📦",
    ToolStatus.PERMISSION_DENIED: "🚫",
}


@dataclass
class PaletteCommand:
    """A command that can be executed from the command palette.

    Attributes:
        id: Unique identifier for the command (used as action name).
        name: Human-readable name displayed in the palette.
        description: Short description of what the command does.
        shortcut: Optional keyboard shortcut (for display only).
    """

    id: str
    name: str
    description: str
    shortcut: str | None = None

    def matches(self, query: str) -> bool:
        """Check if this command matches a fuzzy search query.

        Args:
            query: The search query (case-insensitive).

        Returns:
            True if the command matches the query.
        """
        if not query:
            return True

        query_lower = query.lower()
        name_lower = self.name.lower()
        desc_lower = self.description.lower()

        # Check if query is a substring of name or description
        if query_lower in name_lower or query_lower in desc_lower:
            return True

        # Fuzzy match: check if all characters appear in order
        return _fuzzy_match(query_lower, name_lower)


def _fuzzy_match(query: str, text: str) -> bool:
    """Check if all characters in query appear in text in order.

    Args:
        query: The search query.
        text: The text to search in.

    Returns:
        True if all characters match in order.
    """
    query_idx = 0
    for char in text:
        if query_idx < len(query) and char == query[query_idx]:
            query_idx += 1
    return query_idx == len(query)


# Default commands available in the command palette
DEFAULT_COMMANDS: list[PaletteCommand] = [
    PaletteCommand(
        id="new_session",
        name="New Session",
        description="Start a new conversation session",
        shortcut="Ctrl+N",
    ),
    PaletteCommand(
        id="save_session",
        name="Save Session",
        description="Save the current session",
        shortcut="Ctrl+S",
    ),
    PaletteCommand(
        id="toggle_sidebar",
        name="Toggle Sidebar",
        description="Show or hide the sessions sidebar",
        shortcut="Ctrl+B",
    ),
    PaletteCommand(
        id="toggle_permissions",
        name="Toggle Permissions",
        description="Toggle auto-approve for medium risk tools",
    ),
    PaletteCommand(
        id="toggle_tools",
        name="Toggle Tool Panel",
        description="Show or hide the tool panel",
        shortcut="Ctrl+T",
    ),
    PaletteCommand(
        id="clear",
        name="Clear Conversation",
        description="Clear the current conversation",
        shortcut="Ctrl+L",
    ),
    PaletteCommand(
        id="show_theme_picker",
        name="Change Theme",
        description="Select a color theme for the TUI",
    ),
    PaletteCommand(
        id="show_llm_settings",
        name="LLM Settings",
        description="Configure LLM provider, model, and max tokens",
    ),
    PaletteCommand(
        id="show_tui_settings",
        name="TUI Settings",
        description="Configure sidebar, tool panel, and theme",
    ),
    PaletteCommand(
        id="show_help",
        name="Help",
        description="Show help topics and documentation",
    ),
    PaletteCommand(
        id="show_tools",
        name="View Tools",
        description="View available tools by category",
    ),
    PaletteCommand(
        id="quit",
        name="Quit",
        description="Exit the application",
        shortcut="Ctrl+C",
    ),
]


class ConversationPanel(Static):
    """Display for the conversation history with markdown rendering.

    This panel renders conversation messages with full markdown support,
    including syntax-highlighted code blocks. Messages are styled based
    on their role (user vs agent) and the current application theme.

    Features:
    - Markdown rendering via Rich
    - Syntax highlighting for code blocks
    - Theme-aware syntax colors
    - Streaming message support (for future use)
    """

    BORDER_TITLE = "💬 Conversation"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the conversation panel."""
        super().__init__(*args, **kwargs)
        self._renderer: MarkdownRenderer | None = None

    def _get_renderer(self) -> MarkdownRenderer:
        """Get or create the markdown renderer with current theme.

        Returns:
            MarkdownRenderer configured for the current app theme.
        """
        if self._renderer is None:
            # Get syntax theme based on current app theme
            try:
                textual_theme = self.app.theme or "textual-dark"
            except Exception:
                textual_theme = "textual-dark"

            syntax_theme = get_syntax_theme(textual_theme)
            config = MarkdownConfig(code_theme=syntax_theme)
            self._renderer = MarkdownRenderer(config=config)

        return self._renderer

    def on_mount(self) -> None:
        """Reset renderer when mounted to pick up theme."""
        self._renderer = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="conversation-messages")

    def append_user_message(self, content: str) -> None:
        """Append a user message to the conversation.

        Args:
            content: The message content (markdown supported).
        """
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        message = MarkdownMessage(
            content,
            role="user",
            renderer=self._get_renderer(),
        )
        scroll.mount(message)
        scroll.scroll_end(animate=False)

    def append_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation.

        Args:
            content: The message content (markdown supported).
        """
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        message = MarkdownMessage(
            content,
            role="agent",
            renderer=self._get_renderer(),
        )
        scroll.mount(message)
        scroll.scroll_end(animate=False)

    def append_streaming_message(self) -> MarkdownMessage:
        """Append an empty assistant message for streaming updates.

        This method creates a placeholder message that can be updated
        incrementally as streaming content arrives.

        Returns:
            The MarkdownMessage widget that can be updated via update_content().
        """
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        message = MarkdownMessage(
            "",
            role="agent",
            renderer=self._get_renderer(),
            id="streaming-message",
        )
        scroll.mount(message)
        scroll.scroll_end(animate=False)
        return message

    def update_streaming_message(self, content: str) -> None:
        """Update the current streaming message content.

        Args:
            content: The new content for the streaming message.
        """
        try:
            message = self.query_one("#streaming-message", MarkdownMessage)
            message.update_content(content)
            scroll = self.query_one("#conversation-messages", VerticalScroll)
            scroll.scroll_end(animate=False)
        except Exception:
            pass  # No streaming message active

    def finalize_streaming_message(self) -> None:
        """Convert streaming message to regular message.

        Removes the special ID from the streaming message so it becomes
        a normal message in the conversation history.
        """
        try:
            message = self.query_one("#streaming-message", MarkdownMessage)
            message.id = None  # type: ignore[assignment]  # Remove special ID
        except Exception:
            pass

    def reset_renderer(self) -> None:
        """Reset the renderer to pick up theme changes.

        Call this when the application theme changes to ensure code blocks
        use appropriate syntax highlighting colors.
        """
        self._renderer = None

    def clear(self) -> None:
        """Clear the conversation history."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        scroll.query("*").remove()

    def get_selected_messages(self) -> list[MarkdownMessage]:
        """Get all selected messages in order.

        Returns:
            List of selected MarkdownMessage widgets.
        """
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        messages = list(scroll.query(MarkdownMessage))
        return [msg for msg in messages if msg.selected]

    def get_selected_content(self) -> str:
        """Get the content of all selected messages.

        Returns:
            Concatenated content of selected messages with role prefixes.
        """
        selected = self.get_selected_messages()
        if not selected:
            return ""

        parts = []
        for msg in selected:
            prefix = "You: " if msg.role == "user" else "Agent: "
            parts.append(f"{prefix}{msg.content}")

        return "\n\n".join(parts)

    def clear_selection(self) -> None:
        """Deselect all messages."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        for msg in scroll.query(MarkdownMessage):
            msg.selected = False

    def select_all(self) -> None:
        """Select all messages."""
        scroll = self.query_one("#conversation-messages", VerticalScroll)
        for msg in scroll.query(MarkdownMessage):
            msg.selected = True


class ToolResultItem(Static):
    """Widget to display a tool result."""

    def __init__(self, content: str, tool_name: str, result: str, **kwargs: Any):
        super().__init__(content, **kwargs)
        self.tool_name = tool_name
        self.result = result


def _format_elapsed_time(start_time: datetime, end_time: datetime | None = None) -> str:
    """Format elapsed time as a human-readable string.

    Args:
        start_time: When the execution started.
        end_time: When the execution ended (None for current time).

    Returns:
        Formatted elapsed time string (e.g., "1.2s", "5.0s").
    """
    end = end_time or datetime.now()
    elapsed = (end - start_time).total_seconds()

    if elapsed < 0.1:
        return "<0.1s"
    elif elapsed < 60:
        return f"{elapsed:.1f}s"
    else:
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        return f"{minutes}m {seconds:.1f}s"


class ToolProgressItem(Static):
    """Widget to display tool execution progress with status and elapsed time.

    Features:
    - Shows tool name and current status (waiting/running/completed/error/cached)
    - Displays elapsed time since execution started
    - Updates in-place when status changes
    - Visual indicator for each status state

    Attributes:
        tool_id: Unique ID for this tool execution.
        tool_name: Name of the tool being executed.
        status: Current execution status.
        start_time: When execution started.
        end_time: When execution ended (if finished).
        result: The result string (if available).
        is_error: Whether the result is an error.
    """

    def __init__(
        self,
        tool_id: str,
        tool_name: str,
        status: ToolStatus = ToolStatus.RUNNING,
        start_time: datetime | None = None,
        **kwargs: Any,
    ):
        """Initialize a tool progress item.

        Args:
            tool_id: Unique ID for this tool execution.
            tool_name: Name of the tool being executed.
            status: Initial execution status.
            start_time: When execution started (defaults to now).
            **kwargs: Additional arguments passed to Static.
        """
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.status = status
        self.start_time = start_time or datetime.now()
        self.end_time: datetime | None = None
        self.result: str | None = None
        self.is_error: bool = False

        # Build initial display
        display_text = self._build_display_text()

        # Set CSS class based on status
        classes = kwargs.pop("classes", "")
        classes = f"{classes} tool-progress tool-progress-{status.value}".strip()

        super().__init__(display_text, classes=classes, **kwargs)

    def _build_display_text(self) -> str:
        """Build the display text for the current state.

        Returns:
            Formatted display string.
        """
        icon = STATUS_ICONS.get(self.status, "?")
        elapsed = _format_elapsed_time(self.start_time, self.end_time)

        if self.status == ToolStatus.RUNNING:
            return f"{icon} {self.tool_name} [{elapsed}]"
        elif self.status in (ToolStatus.COMPLETED, ToolStatus.CACHED):
            # Show truncated result
            result_preview = ""
            if self.result:
                preview = self.result[:100].replace("\n", " ")
                if len(self.result) > 100:
                    preview += "..."
                result_preview = f": {preview}"
            return f"{icon} {self.tool_name} [{elapsed}]{result_preview}"
        elif self.status == ToolStatus.ERROR:
            error_preview = ""
            if self.result:
                preview = self.result[:100].replace("\n", " ")
                if len(self.result) > 100:
                    preview += "..."
                error_preview = f": {preview}"
            return f"{icon} {self.tool_name} [{elapsed}]{error_preview}"
        elif self.status == ToolStatus.PERMISSION_DENIED:
            return f"{icon} {self.tool_name} [Permission Denied]"
        else:
            return f"{icon} {self.tool_name}"

    def _update_css_class(self) -> None:
        """Update CSS classes based on current status."""
        # Remove old status classes
        for s in ToolStatus:
            self.remove_class(f"tool-progress-{s.value}")

        # Add current status class
        self.add_class(f"tool-progress-{self.status.value}")

    def update_status(
        self,
        status: ToolStatus,
        result: str | None = None,
        is_error: bool = False,
        cached: bool = False,
    ) -> None:
        """Update the tool execution status.

        Args:
            status: New status.
            result: Result string (if available).
            is_error: Whether the result is an error.
            cached: Whether the result came from cache.
        """
        # Handle cached results
        if cached and status == ToolStatus.COMPLETED:
            self.status = ToolStatus.CACHED
        else:
            self.status = status

        self.result = result
        self.is_error = is_error

        # Set end time for completed states
        if status in (
            ToolStatus.COMPLETED,
            ToolStatus.ERROR,
            ToolStatus.CACHED,
            ToolStatus.PERMISSION_DENIED,
        ):
            self.end_time = datetime.now()

        # Update display
        self._update_css_class()
        self.update(self._build_display_text())

    def refresh_elapsed_time(self) -> None:
        """Refresh the elapsed time display for running tools.

        Call this periodically for running tools to update the timer.
        """
        if self.status == ToolStatus.RUNNING and self.end_time is None:
            self.update(self._build_display_text())


class ToolPanel(Static):
    """Display for tool activity with progress tracking.

    Features:
    - Tracks tool executions by tool_id
    - Updates progress items in-place when results arrive
    - Shows elapsed time for running tools
    - Displays cached vs fresh results
    """

    BORDER_TITLE = "🔧 Tools"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the tool panel."""
        super().__init__(**kwargs)
        # Map tool_id -> ToolProgressItem for in-place updates
        self._progress_items: dict[str, ToolProgressItem] = {}

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="tool-output")

    def append_tool_call(
        self,
        tool_name: str,
        tool_id: str,
        start_time: datetime | None = None,
    ) -> None:
        """Add a new tool execution to the panel.

        Args:
            tool_name: Name of the tool being executed.
            tool_id: Unique ID for this tool execution.
            start_time: When execution started (defaults to now).
        """
        scroll = self.query_one("#tool-output", VerticalScroll)

        # Create progress item
        item = ToolProgressItem(
            tool_id=tool_id,
            tool_name=tool_name,
            status=ToolStatus.RUNNING,
            start_time=start_time,
        )

        # Track by tool_id for later updates
        self._progress_items[tool_id] = item

        scroll.mount(item)
        scroll.scroll_end(animate=False)

    def update_tool_result(
        self,
        tool_id: str,
        tool_name: str,
        result: str,
        is_error: bool = False,
        cached: bool = False,
    ) -> None:
        """Update a tool execution with its result.

        If the tool_id is found, updates the existing item in-place.
        If not found (e.g., for tools that completed before the UI started),
        creates a new completed item.

        Args:
            tool_id: Unique ID for this tool execution.
            tool_name: Name of the tool.
            result: The result string.
            is_error: Whether the result is an error.
            cached: Whether the result came from cache.
        """
        if tool_id in self._progress_items:
            # Update existing item in-place
            item = self._progress_items[tool_id]

            if is_error:
                status = ToolStatus.ERROR
            else:
                status = ToolStatus.COMPLETED

            item.update_status(
                status=status,
                result=result,
                is_error=is_error,
                cached=cached,
            )
        else:
            # Create a new completed item (fallback for missed tool_call events)
            scroll = self.query_one("#tool-output", VerticalScroll)

            if cached:
                status = ToolStatus.CACHED
            elif is_error:
                status = ToolStatus.ERROR
            else:
                status = ToolStatus.COMPLETED

            item = ToolProgressItem(
                tool_id=tool_id,
                tool_name=tool_name,
                status=status,
            )
            item.result = result
            item.is_error = is_error
            item.end_time = datetime.now()

            # Update display for the new status
            item._update_css_class()
            item.update(item._build_display_text())

            self._progress_items[tool_id] = item
            scroll.mount(item)
            scroll.scroll_end(animate=False)

    def update_permission_denied(self, tool_id: str, tool_name: str) -> None:
        """Update a tool execution to show permission denied.

        Args:
            tool_id: Unique ID for this tool execution.
            tool_name: Name of the tool.
        """
        if tool_id in self._progress_items:
            item = self._progress_items[tool_id]
            item.update_status(
                status=ToolStatus.PERMISSION_DENIED,
                result="Permission denied by user",
                is_error=True,
            )
        else:
            # Create a new item showing permission denied
            scroll = self.query_one("#tool-output", VerticalScroll)

            item = ToolProgressItem(
                tool_id=tool_id,
                tool_name=tool_name,
                status=ToolStatus.PERMISSION_DENIED,
            )
            item.result = "Permission denied by user"
            item.is_error = True
            item.end_time = datetime.now()

            item._update_css_class()
            item.update(item._build_display_text())

            self._progress_items[tool_id] = item
            scroll.mount(item)
            scroll.scroll_end(animate=False)

    def append_tool_result(self, tool_name: str, result: str) -> None:
        """Append a tool result to the panel (legacy method for backwards compatibility).

        Deprecated: Use update_tool_result() instead for proper progress tracking.

        Args:
            tool_name: Name of the tool.
            result: The result string.
        """
        # Generate a fake tool_id for legacy calls
        import uuid

        tool_id = str(uuid.uuid4())

        self.update_tool_result(
            tool_id=tool_id,
            tool_name=tool_name,
            result=result,
            is_error=False,
            cached=False,
        )

    def refresh_running_tools(self) -> None:
        """Refresh elapsed time display for all running tools.

        Call this periodically (e.g., every second) to update timers.
        """
        for item in self._progress_items.values():
            if item.status == ToolStatus.RUNNING:
                item.refresh_elapsed_time()

    def get_running_count(self) -> int:
        """Get the number of currently running tools.

        Returns:
            Count of tools with RUNNING status.
        """
        return sum(1 for item in self._progress_items.values() if item.status == ToolStatus.RUNNING)

    def clear(self) -> None:
        """Clear the tool activity."""
        scroll = self.query_one("#tool-output", VerticalScroll)
        scroll.query("*").remove()
        self._progress_items.clear()


class MessageInput(Input):
    """Input widget for user messages."""

    def on_mount(self) -> None:
        self.placeholder = "Type your message..."


class PermissionPrompt(ModalScreen[bool]):
    """Modal to ask for permission."""

    def __init__(self, tool_name: str, args: dict[str, Any]):
        super().__init__()
        self.tool_name = tool_name
        self.args = args

    def compose(self) -> ComposeResult:
        yield Static(f"Allow execution of tool '{self.tool_name}'?")
        yield Pretty(self.args)
        with Horizontal(classes="buttons"):
            yield Button("Yes", variant="success", id="btn-yes")
            yield Button("No", variant="error", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class CommandPaletteItem(Static):
    """Widget to display a single command in the command palette."""

    def __init__(
        self,
        command: PaletteCommand,
        is_selected: bool = False,
        **kwargs: Any,
    ):
        """Initialize a command palette item.

        Args:
            command: The command to display.
            is_selected: Whether this item is currently selected.
            **kwargs: Additional arguments passed to Static.
        """
        # Format: name (shortcut) - description
        shortcut_str = f" ({command.shortcut})" if command.shortcut else ""
        display_text = f"{command.name}{shortcut_str}"

        # Add CSS classes
        classes = kwargs.pop("classes", "")
        if is_selected:
            classes = f"{classes} palette-item-selected".strip()
        else:
            classes = f"{classes} palette-item".strip()

        super().__init__(display_text, classes=classes, **kwargs)
        self.command = command
        self.is_selected = is_selected

    def set_selected(self, selected: bool) -> None:
        """Update the selected state of this item.

        Args:
            selected: Whether to select this item.
        """
        self.is_selected = selected
        if selected:
            self.add_class("palette-item-selected")
            self.remove_class("palette-item")
        else:
            self.add_class("palette-item")
            self.remove_class("palette-item-selected")


class CommandPalette(ModalScreen[str | None]):
    """Modal command palette for quick command access.

    Features:
    - Fuzzy search input
    - List of available commands
    - Keyboard navigation (up/down arrows)
    - Enter to execute selected command
    - Escape to dismiss
    """

    BINDINGS = [
        ("escape", "dismiss_palette", "Close"),
        ("up", "move_up", "Previous"),
        ("down", "move_down", "Next"),
        ("enter", "select_command", "Execute"),
    ]

    def __init__(
        self,
        commands: list[PaletteCommand] | None = None,
        **kwargs: Any,
    ):
        """Initialize the command palette.

        Args:
            commands: List of commands to display. Uses DEFAULT_COMMANDS if None.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.commands = commands if commands is not None else DEFAULT_COMMANDS.copy()
        self.filtered_commands: list[PaletteCommand] = []
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        """Create child widgets for the palette."""
        yield Static("Command Palette", id="palette-title")
        yield Input(placeholder="Type to search commands...", id="palette-input")
        yield VerticalScroll(id="palette-commands")

    def on_mount(self) -> None:
        """Handle mount event."""
        self._update_command_list("")
        self.query_one("#palette-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for filtering."""
        self._update_command_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter pressed in the input field."""
        self.action_select_command()

    def _update_command_list(self, query: str) -> None:
        """Update the list of displayed commands based on the query.

        Args:
            query: The search query.
        """
        # Filter commands based on query
        self.filtered_commands = [cmd for cmd in self.commands if cmd.matches(query)]
        self.selected_index = 0 if self.filtered_commands else -1

        # Clear and rebuild the command list
        scroll = self.query_one("#palette-commands", VerticalScroll)
        scroll.query(CommandPaletteItem).remove()

        for i, cmd in enumerate(self.filtered_commands):
            item = CommandPaletteItem(command=cmd, is_selected=(i == 0))
            scroll.mount(item)

    def action_dismiss_palette(self) -> None:
        """Dismiss the palette without selecting a command."""
        self.dismiss(None)

    def action_move_up(self) -> None:
        """Move selection up."""
        if not self.filtered_commands:
            return

        self._set_selected(max(0, self.selected_index - 1))

    def action_move_down(self) -> None:
        """Move selection down."""
        if not self.filtered_commands:
            return

        self._set_selected(min(len(self.filtered_commands) - 1, self.selected_index + 1))

    def _set_selected(self, new_index: int) -> None:
        """Update the selected item.

        Args:
            new_index: The new selected index.
        """
        scroll = self.query_one("#palette-commands", VerticalScroll)
        items = list(scroll.query(CommandPaletteItem))

        if 0 <= self.selected_index < len(items):
            items[self.selected_index].set_selected(False)

        self.selected_index = new_index

        if 0 <= new_index < len(items):
            items[new_index].set_selected(True)
            # Scroll to keep selected item visible
            items[new_index].scroll_visible()

    def action_select_command(self) -> None:
        """Execute the selected command."""
        if 0 <= self.selected_index < len(self.filtered_commands):
            command = self.filtered_commands[self.selected_index]
            self.dismiss(command.id)
        else:
            self.dismiss(None)

    def on_click(self, event: Any) -> None:
        """Handle click events on command items."""
        # Find if click was on a CommandPaletteItem
        scroll = self.query_one("#palette-commands", VerticalScroll)
        items = list(scroll.query(CommandPaletteItem))

        for i, item in enumerate(items):
            # Check if this widget was clicked (approximate using geometry)
            if item.is_mouse_over:
                self._set_selected(i)
                self.action_select_command()
                return


class SessionItem(Static):
    """Widget to display a single session item in the sidebar."""

    def __init__(self, session_id: str, message_count: int, is_active: bool = False, **kwargs: Any):
        """Initialize a session item.

        Args:
            session_id: The session ID.
            message_count: Number of messages in the session.
            is_active: Whether this is the currently active session.
            **kwargs: Additional arguments passed to Static.
        """
        # Display format: arrow for active, truncated ID, message count
        prefix = "▸ " if is_active else "  "
        display_text = f"{prefix}{session_id[:8]}… ({message_count} msgs)"

        # Add CSS class for active styling
        classes = kwargs.pop("classes", "")
        if is_active:
            classes = f"{classes} session-active".strip()

        super().__init__(display_text, classes=classes, **kwargs)
        self.session_id = session_id
        self.is_active = is_active
        self.message_count = message_count


class SessionsSidebar(Static):
    """Sidebar widget showing saved sessions.

    Features:
    - List recent sessions with truncated IDs
    - Shows message count per session
    - Highlights active session
    - Click to switch between sessions
    """

    BORDER_TITLE = "📋 Sessions"

    def compose(self) -> ComposeResult:
        """Create child widgets for the sidebar."""
        yield VerticalScroll(id="sessions-list")

    def add_session(
        self,
        session_id: str,
        message_count: int = 0,
        is_active: bool = False,
    ) -> None:
        """Add a session to the sidebar list.

        Args:
            session_id: The session ID.
            message_count: Number of messages in the session.
            is_active: Whether this is the currently active session.
        """
        scroll = self.query_one("#sessions-list", VerticalScroll)
        item = SessionItem(
            session_id=session_id,
            message_count=message_count,
            is_active=is_active,
            classes="session-item",
        )
        scroll.mount(item)

    def update_active_session(self, active_session_id: str) -> None:
        """Update which session is marked as active.

        Args:
            active_session_id: The ID of the currently active session.
        """
        scroll = self.query_one("#sessions-list", VerticalScroll)

        # Check if the new active session exists in the list
        session_exists = any(item.session_id == active_session_id for item in scroll.query(SessionItem))

        # Only update if the session exists (don't deactivate all if session not found)
        if not session_exists:
            return

        for item in scroll.query(SessionItem):
            was_active = item.is_active
            is_now_active = item.session_id == active_session_id

            if was_active != is_now_active:
                item.is_active = is_now_active
                # Update display text
                prefix = "▸ " if is_now_active else "  "
                item.update(f"{prefix}{item.session_id[:8]}… ({item.message_count} msgs)")

                # Update CSS classes
                if is_now_active:
                    item.add_class("session-active")
                else:
                    item.remove_class("session-active")

    def clear(self) -> None:
        """Clear all sessions from the sidebar."""
        scroll = self.query_one("#sessions-list", VerticalScroll)
        scroll.query(SessionItem).remove()

    def get_session_count(self) -> int:
        """Get the number of sessions in the sidebar.

        Returns:
            Number of session items.
        """
        scroll = self.query_one("#sessions-list", VerticalScroll)
        return len(scroll.query(SessionItem))
