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
    - Input for max_tokens with validation (1-100000)
    - Save button: persists settings to config
    - Cancel button: discards changes

    Returns:
        A dict with {"provider": str, "model": str, "max_tokens": int} on save,
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
        current_max_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the LLM settings screen.

        Args:
            current_provider: The currently configured provider.
            current_model: The currently configured model.
            current_max_tokens: The currently configured max_tokens.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.original_provider = current_provider or "anthropic"
        self.original_model = current_model or "claude-sonnet-4-20250514"
        self.original_max_tokens = current_max_tokens or 4096

        # Track current selections
        self.selected_provider = self.original_provider
        self.selected_model = self.original_model
        self.selected_max_tokens = self.original_max_tokens

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

            # Max tokens input
            with Horizontal(classes="llm-setting-row"):
                yield Label("Max Tokens:", classes="llm-setting-label")
                yield Input(
                    value=str(self.selected_max_tokens),
                    placeholder="1-100000",
                    id="llm-max-tokens-input",
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
        elif event.input.id == "llm-max-tokens-input":
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
            Dict with provider, model, max_tokens if valid, or None if invalid.
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

        # Get max_tokens value
        try:
            max_tokens_input = self.query_one("#llm-max-tokens-input", Input)
            max_tokens_str = max_tokens_input.value.strip()
        except Exception:
            max_tokens_str = str(self.selected_max_tokens)

        try:
            max_tokens = int(max_tokens_str)
        except ValueError:
            self._show_error("Max tokens must be a number.")
            return None

        if max_tokens < 1:
            self._show_error("Max tokens must be at least 1.")
            return None

        if max_tokens > 100000:
            self._show_error("Max tokens cannot exceed 100000.")
            return None

        return {
            "provider": self.selected_provider,
            "model": model,
            "max_tokens": max_tokens,
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
