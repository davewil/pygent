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
from textual.widgets import Button, Static

from chapgent.config.settings import VALID_THEMES

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
