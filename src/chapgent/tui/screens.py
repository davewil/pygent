"""Modal screens for TUI settings and configuration.

This module provides modal screens for:
- ThemePickerScreen: Select and preview TUI themes
- LLMSettingsScreen: Configure LLM provider and model
- TUISettingsScreen: Configure TUI appearance
- SystemPromptScreen: Configure system prompt
- HelpScreen: Display help topics
- ToolsScreen: Display available tools
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from chapgent.config.settings import VALID_PROVIDERS, VALID_THEMES

if TYPE_CHECKING:
    pass


class ThemePickerScreen(ModalScreen[str | None]):
    """Modal screen for selecting a TUI theme.

    Features:
    - Grid of theme buttons (one for each valid theme)
    - Live preview: clicking a theme applies it immediately
    - Save button: persists the selected theme to config
    - Cancel button: reverts to the original theme

    Returns:
        The selected theme name (str) on save, or None on cancel.
    """

    CSS = """
    ThemePickerScreen {
        align: center middle;
    }

    #theme-picker-container {
        background: $surface;
        border: round $primary;
        padding: 1 2;
        width: 50;
    }

    #theme-picker-title {
        text-align: center;
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }

    #theme-grid {
        grid-size: 2;
        grid-gutter: 1;
        height: auto;
        padding: 1 0;
    }

    .theme-button {
        width: 100%;
    }

    #theme-picker-buttons {
        align: center middle;
        padding: 1 0 0 0;
    }

    #theme-picker-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, current_theme: str | None = None, **kwargs: Any) -> None:
        """Initialize the theme picker.

        Args:
            current_theme: The currently active theme (for reverting on cancel).
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.original_theme = current_theme
        self.selected_theme = current_theme

    def compose(self) -> ComposeResult:
        """Create child widgets for the theme picker."""
        with Static(id="theme-picker-container"):
            yield Static("Select Theme", id="theme-picker-title")
            with Grid(id="theme-grid"):
                for theme in sorted(VALID_THEMES):
                    yield Button(
                        theme,
                        id=f"theme-{theme}",
                        classes="theme-button",
                        variant="primary" if theme == self.selected_theme else "default",
                    )
            with Horizontal(id="theme-picker-buttons"):
                yield Button("Save", variant="success", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button press event.
        """
        button_id = event.button.id

        if button_id == "btn-save":
            # Save the currently selected theme
            self.dismiss(self.selected_theme)

        elif button_id == "btn-cancel":
            # Revert to original theme and dismiss
            if self.original_theme:
                self.app.theme = self.original_theme
            self.dismiss(None)

        elif button_id and button_id.startswith("theme-"):
            # Theme button clicked - apply preview immediately
            theme_name = button_id[6:]  # Remove "theme-" prefix
            self._select_theme(theme_name)

    def _select_theme(self, theme_name: str) -> None:
        """Select a theme and update the preview.

        Args:
            theme_name: The theme to select.
        """
        self.selected_theme = theme_name

        # Apply theme immediately for preview
        self.app.theme = theme_name

        # Update button variants to show selection
        grid = self.query_one("#theme-grid", Grid)
        for button in grid.query(Button):
            if button.id == f"theme-{theme_name}":
                button.variant = "primary"
            else:
                button.variant = "default"

    def action_cancel(self) -> None:
        """Handle escape key - revert and dismiss."""
        if self.original_theme:
            self.app.theme = self.original_theme
        self.dismiss(None)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]


class LLMSettingsScreen(ModalScreen[dict[str, Any] | None]):
    """Modal screen for configuring LLM settings.

    Features:
    - Select widget for provider (from VALID_PROVIDERS)
    - Input for model name
    - Input for max_output_tokens with validation (1-100000)
    - Save button: persists settings to config
    - Cancel button: discards changes

    Returns:
        A dict with {"provider": str, "model": str, "max_output_tokens": int} on save,
        or None on cancel.
    """

    CSS = """
    LLMSettingsScreen {
        align: center middle;
    }

    #llm-settings-container {
        background: $surface;
        border: round $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }

    #llm-settings-title {
        text-align: center;
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }

    .llm-setting-row {
        height: auto;
        padding: 0 0 1 0;
    }

    .llm-setting-label {
        width: 15;
        padding: 0 1 0 0;
    }

    .llm-setting-input {
        width: 1fr;
    }

    #llm-provider-select {
        width: 1fr;
    }

    #llm-error-message {
        color: $error;
        text-style: italic;
        padding: 0 0 1 0;
        height: auto;
    }

    #llm-settings-buttons {
        align: center middle;
        padding: 1 0 0 0;
    }

    #llm-settings-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        current_provider: str | None = None,
        current_model: str | None = None,
        current_max_output_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the LLM settings screen.

        Args:
            current_provider: The currently configured provider.
            current_model: The currently configured model.
            current_max_output_tokens: The currently configured max output tokens.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.original_provider = current_provider or "anthropic"
        self.original_model = current_model or "claude-sonnet-4-20250514"
        self.original_max_output_tokens = current_max_output_tokens or 4096

        # Track current selections
        self.selected_provider = self.original_provider
        self.selected_model = self.original_model
        self.selected_max_output_tokens = self.original_max_output_tokens

        self.error_message = ""

    def compose(self) -> ComposeResult:
        """Create child widgets for the LLM settings screen."""
        with Static(id="llm-settings-container"):
            yield Static("LLM Settings", id="llm-settings-title")

            # Provider selection
            with Horizontal(classes="llm-setting-row"):
                yield Label("Provider:", classes="llm-setting-label")
                provider_options = [(p, p) for p in sorted(VALID_PROVIDERS)]
                yield Select(
                    provider_options,
                    value=self.selected_provider,
                    id="llm-provider-select",
                )

            # Model input
            with Horizontal(classes="llm-setting-row"):
                yield Label("Model:", classes="llm-setting-label")
                yield Input(
                    value=self.selected_model,
                    placeholder="e.g., claude-sonnet-4-20250514",
                    id="llm-model-input",
                    classes="llm-setting-input",
                )

            # Max output tokens input
            with Horizontal(classes="llm-setting-row"):
                yield Label("Max Output Tokens:", classes="llm-setting-label")
                yield Input(
                    value=str(self.selected_max_output_tokens),
                    placeholder="1-100000",
                    id="llm-max-output-tokens-input",
                    classes="llm-setting-input",
                )

            # Error message area
            yield Static("", id="llm-error-message")

            # Buttons
            with Horizontal(id="llm-settings-buttons"):
                yield Button("Save", variant="success", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle provider selection changes.

        Args:
            event: The select changed event.
        """
        if event.select.id == "llm-provider-select" and event.value != Select.BLANK:
            self.selected_provider = str(event.value)
            self._clear_error()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes.

        Args:
            event: The input changed event.
        """
        if event.input.id == "llm-model-input":
            self.selected_model = event.value
            self._clear_error()
        elif event.input.id == "llm-max-output-tokens-input":
            self._clear_error()

    def _clear_error(self) -> None:
        """Clear the error message."""
        self.error_message = ""
        try:
            self.query_one("#llm-error-message", Static).update("")
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        """Show an error message.

        Args:
            message: The error message to display.
        """
        self.error_message = message
        try:
            self.query_one("#llm-error-message", Static).update(message)
        except Exception:
            pass

    def _validate_and_get_values(self) -> dict[str, Any] | None:
        """Validate inputs and return the settings dict.

        Returns:
            Dict with provider, model, max_output_tokens if valid, or None if invalid.
        """
        # Get model value
        try:
            model_input = self.query_one("#llm-model-input", Input)
            model = model_input.value.strip()
        except Exception:
            model = self.selected_model

        if not model:
            self._show_error("Model name cannot be empty.")
            return None

        # Get max_output_tokens value
        try:
            max_output_tokens_input = self.query_one("#llm-max-output-tokens-input", Input)
            max_output_tokens_str = max_output_tokens_input.value.strip()
        except Exception:
            max_output_tokens_str = str(self.selected_max_output_tokens)

        try:
            max_output_tokens = int(max_output_tokens_str)
        except ValueError:
            self._show_error("Max output tokens must be a number.")
            return None

        if max_output_tokens < 1:
            self._show_error("Max output tokens must be at least 1.")
            return None

        if max_output_tokens > 100000:
            self._show_error("Max output tokens cannot exceed 100000.")
            return None

        return {
            "provider": self.selected_provider,
            "model": model,
            "max_output_tokens": max_output_tokens,
        }

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button press event.
        """
        button_id = event.button.id

        if button_id == "btn-save":
            # Validate and save
            values = self._validate_and_get_values()
            if values is not None:
                self.dismiss(values)

        elif button_id == "btn-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key - dismiss without saving."""
        self.dismiss(None)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]


class HelpScreen(ModalScreen[None]):
    """Modal screen for displaying help topics.

    Features:
    - Shows list of available topics when no topic specified
    - Shows specific topic content when topic is provided
    - Clickable topic list for navigation
    - Close button to dismiss

    Returns:
        None (informational screen).
    """

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-container {
        background: $surface;
        border: round $primary;
        padding: 1 2;
        width: 80;
        height: 80%;
        max-height: 40;
    }

    #help-title {
        text-align: center;
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }

    #help-content {
        height: 1fr;
        padding: 1 0;
    }

    .help-topic-item {
        padding: 0 1;
    }

    .help-topic-item:hover {
        background: $primary 20%;
    }

    .help-topic-name {
        text-style: bold;
        color: $primary;
    }

    .help-topic-summary {
        color: $text-muted;
        padding-left: 2;
    }

    #help-back-button {
        margin: 1 0 0 0;
    }

    #help-buttons {
        align: center middle;
        padding: 1 0 0 0;
    }

    #help-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, topic: str | None = None, **kwargs: Any) -> None:
        """Initialize the help screen.

        Args:
            topic: Optional topic name to display directly.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.initial_topic = topic
        self.current_topic: str | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the help screen."""
        from textual.containers import VerticalScroll

        with Static(id="help-container"):
            yield Static("Help", id="help-title")
            yield VerticalScroll(id="help-content")
            with Horizontal(id="help-buttons"):
                yield Button("Back", variant="default", id="btn-back")
                yield Button("Close", variant="primary", id="btn-close")

    def on_mount(self) -> None:
        """Handle mount event."""
        # Hide back button initially
        try:
            back_btn = self.query_one("#btn-back", Button)
            back_btn.display = False
        except Exception:
            pass

        if self.initial_topic:
            self._show_topic(self.initial_topic)
        else:
            self._show_topic_list()

    def _show_topic_list(self) -> None:
        """Show the list of available topics."""
        from textual.containers import VerticalScroll

        from chapgent.ux.help import HELP_TOPICS

        self.current_topic = None

        # Update title
        try:
            self.query_one("#help-title", Static).update("Help Topics")
        except Exception:
            pass

        # Hide back button
        try:
            back_btn = self.query_one("#btn-back", Button)
            back_btn.display = False
        except Exception:
            pass

        # Clear and populate content
        content = self.query_one("#help-content", VerticalScroll)
        content.query("*").remove()

        for topic_name in sorted(HELP_TOPICS.keys()):
            topic = HELP_TOPICS[topic_name]
            # Create clickable topic item
            item = Static(
                f"[bold]{topic.name}[/bold]\n  {topic.summary}",
                classes="help-topic-item",
                id=f"topic-{topic.name}",
            )
            content.mount(item)

    def _show_topic(self, topic_name: str) -> None:
        """Show a specific topic's content.

        Args:
            topic_name: The name of the topic to show.
        """
        from textual.containers import VerticalScroll

        from chapgent.ux.help import get_help_topic

        topic = get_help_topic(topic_name)
        if topic is None:
            # Topic not found, show list instead
            self._show_topic_list()
            return

        self.current_topic = topic_name

        # Update title
        try:
            self.query_one("#help-title", Static).update(topic.title)
        except Exception:
            pass

        # Show back button
        try:
            back_btn = self.query_one("#btn-back", Button)
            back_btn.display = True
        except Exception:
            pass

        # Clear and populate content
        content = self.query_one("#help-content", VerticalScroll)
        content.query("*").remove()

        # Display topic content
        content.mount(Static(topic.content))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button press event.
        """
        button_id = event.button.id

        if button_id == "btn-close":
            self.dismiss(None)
        elif button_id == "btn-back":
            self._show_topic_list()

    def on_click(self, event: Any) -> None:
        """Handle click events on topic items."""
        from textual.containers import VerticalScroll

        # Only handle clicks when showing topic list
        if self.current_topic is not None:
            return

        content = self.query_one("#help-content", VerticalScroll)
        for item in content.query(Static):
            if item.id and item.id.startswith("topic-") and item.is_mouse_over:
                topic_name = item.id[6:]  # Remove "topic-" prefix
                self._show_topic(topic_name)
                return

    def action_close(self) -> None:
        """Handle escape key - dismiss."""
        self.dismiss(None)

    BINDINGS = [
        ("escape", "close", "Close"),
    ]


class ToolsScreen(ModalScreen[None]):
    """Modal screen for displaying available tools.

    Features:
    - Shows tools grouped by category
    - Search/filter input at top
    - Category filtering
    - Tool name, description, and risk level display
    - Close button to dismiss

    Returns:
        None (informational screen).
    """

    CSS = """
    ToolsScreen {
        align: center middle;
    }

    #tools-container {
        background: $surface;
        border: round $primary;
        padding: 1 2;
        width: 80;
        height: 80%;
        max-height: 45;
    }

    #tools-title {
        text-align: center;
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }

    #tools-filter-row {
        height: auto;
        padding: 0 0 1 0;
    }

    #tools-search {
        width: 1fr;
    }

    #tools-category-select {
        width: 20;
        margin-left: 1;
    }

    #tools-content {
        height: 1fr;
        padding: 1 0;
    }

    .tools-category-header {
        text-style: bold;
        color: $primary;
        padding: 1 0 0 0;
    }

    .tool-item {
        padding: 0 1;
    }

    .tool-name {
        text-style: bold;
    }

    .tool-risk-low {
        color: $success;
    }

    .tool-risk-medium {
        color: $warning;
    }

    .tool-risk-high {
        color: $error;
    }

    #tools-buttons {
        align: center middle;
        padding: 1 0 0 0;
    }
    """

    def __init__(self, category: str | None = None, **kwargs: Any) -> None:
        """Initialize the tools screen.

        Args:
            category: Optional category to filter by initially.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.initial_category = category
        self.current_filter = ""
        self.current_category: str | None = category

    def compose(self) -> ComposeResult:
        """Create child widgets for the tools screen."""
        from textual.containers import VerticalScroll

        from chapgent.tools.base import ToolCategory

        # Validate initial category
        valid_categories = {cat.value for cat in ToolCategory}
        select_value = ""
        if self.initial_category and self.initial_category in valid_categories:
            select_value = self.initial_category
        else:
            # Invalid category, fall back to showing all
            if self.initial_category:
                self.current_category = None

        with Static(id="tools-container"):
            yield Static("Available Tools", id="tools-title")

            with Horizontal(id="tools-filter-row"):
                yield Input(
                    placeholder="Search tools...",
                    id="tools-search",
                )
                # Category filter
                category_options = [("All Categories", "")] + [(cat.value.title(), cat.value) for cat in ToolCategory]
                yield Select(
                    category_options,
                    value=select_value,
                    id="tools-category-select",
                )

            yield VerticalScroll(id="tools-content")

            with Horizontal(id="tools-buttons"):
                yield Button("Close", variant="primary", id="btn-close")

    def on_mount(self) -> None:
        """Handle mount event."""
        self._update_tools_list()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes.

        Args:
            event: The input changed event.
        """
        if event.input.id == "tools-search":
            self.current_filter = event.value.lower()
            self._update_tools_list()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle category selection changes.

        Args:
            event: The select changed event.
        """
        if event.select.id == "tools-category-select":
            value = event.value
            self.current_category = str(value) if value and value != Select.BLANK else None
            self._update_tools_list()

    def _get_tools(self) -> list[Any]:
        """Get tools from the registry, optionally filtered.

        Returns:
            List of tool definitions.
        """
        from chapgent.tools.base import ToolCategory

        # Build a simple registry with all tools
        tools = self._get_all_tools()

        # Filter by category if specified
        if self.current_category:
            try:
                category = ToolCategory(self.current_category)
                tools = [t for t in tools if t.category == category]
            except ValueError:
                pass

        # Filter by search query
        if self.current_filter:
            query = self.current_filter.lower()
            tools = [t for t in tools if query in t.name.lower() or query in t.description.lower()]

        return tools

    def _get_all_tools(self) -> list[Any]:
        """Get all available tools.

        Returns:
            List of all tool definitions.
        """
        from typing import cast

        from chapgent.tools.base import ToolFunction

        # Import all tool modules to ensure they're registered
        from chapgent.tools.filesystem import (
            copy_file,
            create_file,
            delete_file,
            edit_file,
            list_files,
            move_file,
            read_file,
        )
        from chapgent.tools.git import (
            git_add,
            git_branch,
            git_checkout,
            git_commit,
            git_diff,
            git_log,
            git_pull,
            git_push,
            git_status,
        )
        from chapgent.tools.scaffold import (
            add_component,
            create_project,
            list_components,
            list_templates,
        )
        from chapgent.tools.search import find_definition, find_files, grep_search
        from chapgent.tools.shell import shell
        from chapgent.tools.testing import run_tests
        from chapgent.tools.web import web_fetch

        # Collect all tool definitions
        # Use cast to tell mypy these are ToolFunctions with _tool_definition
        tool_functions: list[ToolFunction[Any, Any]] = [
            cast(ToolFunction[Any, Any], read_file),
            cast(ToolFunction[Any, Any], list_files),
            cast(ToolFunction[Any, Any], edit_file),
            cast(ToolFunction[Any, Any], create_file),
            cast(ToolFunction[Any, Any], delete_file),
            cast(ToolFunction[Any, Any], move_file),
            cast(ToolFunction[Any, Any], copy_file),
            # Search
            cast(ToolFunction[Any, Any], grep_search),
            cast(ToolFunction[Any, Any], find_files),
            cast(ToolFunction[Any, Any], find_definition),
            # Git
            cast(ToolFunction[Any, Any], git_status),
            cast(ToolFunction[Any, Any], git_diff),
            cast(ToolFunction[Any, Any], git_log),
            cast(ToolFunction[Any, Any], git_branch),
            cast(ToolFunction[Any, Any], git_add),
            cast(ToolFunction[Any, Any], git_commit),
            cast(ToolFunction[Any, Any], git_checkout),
            cast(ToolFunction[Any, Any], git_push),
            cast(ToolFunction[Any, Any], git_pull),
            # Shell
            cast(ToolFunction[Any, Any], shell),
            # Web
            cast(ToolFunction[Any, Any], web_fetch),
            # Testing
            cast(ToolFunction[Any, Any], run_tests),
            # Scaffold
            cast(ToolFunction[Any, Any], list_templates),
            cast(ToolFunction[Any, Any], create_project),
            cast(ToolFunction[Any, Any], list_components),
            cast(ToolFunction[Any, Any], add_component),
        ]

        return [f._tool_definition for f in tool_functions]

    def _update_tools_list(self) -> None:
        """Update the tools list based on current filters."""
        from textual.containers import VerticalScroll

        from chapgent.tools.base import ToolCategory

        tools = self._get_tools()

        # Clear content
        content = self.query_one("#tools-content", VerticalScroll)
        content.query("*").remove()

        if not tools:
            content.mount(Static("No tools found matching your criteria."))
            return

        # Group by category
        tools_by_category: dict[ToolCategory, list[Any]] = {}
        for tool in tools:
            if tool.category not in tools_by_category:
                tools_by_category[tool.category] = []
            tools_by_category[tool.category].append(tool)

        # Display grouped tools
        for category in sorted(tools_by_category.keys(), key=lambda c: c.value):
            # Category header
            content.mount(
                Static(
                    f"[bold]{category.value.upper()}[/bold]",
                    classes="tools-category-header",
                )
            )

            # Tools in category
            for tool in sorted(tools_by_category[category], key=lambda t: t.name):
                risk_class = f"tool-risk-{tool.risk.value}"
                risk_badge = f"[{tool.risk.value.upper()}]"

                # Format: name [RISK] - description
                tool_text = (
                    f"  [bold]{tool.name}[/bold] [{risk_class}]{risk_badge}[/{risk_class}]\n    {tool.description}"
                )
                content.mount(Static(tool_text, classes="tool-item"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button press event.
        """
        if event.button.id == "btn-close":
            self.dismiss(None)

    def action_close(self) -> None:
        """Handle escape key - dismiss."""
        self.dismiss(None)

    BINDINGS = [
        ("escape", "close", "Close"),
    ]
