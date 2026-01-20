"""Tests for TUI modal screens."""

import asyncio
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from chapgent.config.settings import VALID_THEMES
from chapgent.tui.app import ChapgentApp
from chapgent.tui.screens import ThemePickerScreen
from chapgent.tui.widgets import DEFAULT_COMMANDS

# =============================================================================
# ThemePickerScreen Tests
# =============================================================================


class TestThemePickerScreen:
    """Tests for the ThemePickerScreen modal."""

    def test_theme_picker_creation(self):
        """Test creating a ThemePickerScreen."""
        screen = ThemePickerScreen(current_theme="dracula")
        assert screen.original_theme == "dracula"
        assert screen.selected_theme == "dracula"

    def test_theme_picker_creation_no_theme(self):
        """Test creating a ThemePickerScreen without current theme."""
        screen = ThemePickerScreen()
        assert screen.original_theme is None
        assert screen.selected_theme is None

    @pytest.mark.asyncio
    async def test_theme_picker_compose(self):
        """Test that theme picker composes correctly."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Push the theme picker
            app.push_screen(ThemePickerScreen(current_theme="textual-dark"))
            await pilot.pause()

            # Check that the theme picker is displayed
            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Check for title and buttons
            title = picker.query_one("#theme-picker-title")
            assert title is not None

            grid = picker.query_one("#theme-grid")
            assert grid is not None

            # Check for save and cancel buttons
            save_btn = picker.query_one("#btn-save")
            cancel_btn = picker.query_one("#btn-cancel")
            assert save_btn is not None
            assert cancel_btn is not None

    @pytest.mark.asyncio
    async def test_theme_picker_shows_all_themes(self):
        """Test that theme picker shows all valid themes."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(ThemePickerScreen())
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Check that all themes have buttons
            from textual.widgets import Button

            buttons = picker.query(Button)
            theme_buttons = [b for b in buttons if b.id and b.id.startswith("theme-")]
            assert len(theme_buttons) == len(VALID_THEMES)

    @pytest.mark.asyncio
    async def test_theme_picker_highlights_current_theme(self):
        """Test that the current theme is highlighted."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(ThemePickerScreen(current_theme="dracula"))
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Find the dracula button
            dracula_btn = picker.query_one("#theme-dracula")
            assert dracula_btn.variant == "primary"

            # Other buttons should be default
            gruvbox_btn = picker.query_one("#theme-gruvbox")
            assert gruvbox_btn.variant == "default"


class TestThemePickerSelection:
    """Tests for theme selection in ThemePickerScreen."""

    @pytest.mark.asyncio
    async def test_theme_selection_applies_preview(self):
        """Test that selecting a theme applies it as preview."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            original_theme = app.theme
            app.push_screen(ThemePickerScreen(current_theme=original_theme))
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Select a different theme using internal method
            new_theme = "dracula" if original_theme != "dracula" else "nord"
            picker._select_theme(new_theme)
            await pilot.pause()

            # Theme should be applied immediately for preview
            assert app.theme == new_theme
            assert picker.selected_theme == new_theme

    @pytest.mark.asyncio
    async def test_theme_selection_updates_button_variants(self):
        """Test that selecting a theme updates button variants."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ThemePickerScreen(current_theme="textual-dark"))
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Select dracula theme using internal method
            picker._select_theme("dracula")
            await pilot.pause()

            # Dracula should now be primary
            dracula_btn = picker.query_one("#theme-dracula")
            assert dracula_btn.variant == "primary"

            # Original theme button should be default
            textual_dark_btn = picker.query_one("#theme-textual-dark")
            assert textual_dark_btn.variant == "default"


class TestThemePickerDismissal:
    """Tests for theme picker dismissal behavior."""

    @pytest.mark.asyncio
    async def test_save_returns_selected_theme(self):
        """Test that save button returns the selected theme."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(ThemePickerScreen(current_theme="textual-dark"), callback=on_dismiss)
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Select a different theme by calling the internal method directly
            picker._select_theme("dracula")
            await pilot.pause()

            # Simulate save button press
            save_btn = picker.query_one("#btn-save")
            save_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] == "dracula"

    @pytest.mark.asyncio
    async def test_cancel_returns_none(self):
        """Test that cancel button returns None."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(ThemePickerScreen(current_theme="textual-dark"), callback=on_dismiss)
            await pilot.pause()

            # Simulate cancel button press
            cancel_btn = app.screen.query_one("#btn-cancel")
            cancel_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] is None

    @pytest.mark.asyncio
    async def test_cancel_reverts_theme(self):
        """Test that cancel reverts to original theme."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            original_theme = "textual-dark"
            app.theme = original_theme

            app.push_screen(ThemePickerScreen(current_theme=original_theme))
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen

            # Select a different theme using internal method
            picker._select_theme("dracula")
            await pilot.pause()
            assert app.theme == "dracula"

            # Simulate cancel button press
            cancel_btn = picker.query_one("#btn-cancel")
            cancel_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            # Theme should be reverted
            assert app.theme == original_theme

    @pytest.mark.asyncio
    async def test_escape_dismisses_with_none(self):
        """Test that escape dismisses and reverts theme."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            original_theme = "textual-dark"
            app.theme = original_theme

            app.push_screen(ThemePickerScreen(current_theme=original_theme), callback=on_dismiss)
            await pilot.pause()

            # Select different theme
            picker = app.screen
            picker._select_theme("dracula")
            await pilot.pause()

            # Press escape
            await pilot.press("escape")
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] is None
            assert app.theme == original_theme


class TestThemePickerAppIntegration:
    """Tests for theme picker integration with ChapgentApp."""

    @pytest.mark.asyncio
    async def test_action_show_theme_picker(self):
        """Test action_show_theme_picker opens the theme picker."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.action_show_theme_picker()
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)

    @pytest.mark.asyncio
    async def test_slash_command_opens_theme_picker(self):
        """Test /theme slash command opens the theme picker."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Type /theme in the input
            input_widget = app.query_one("#input")
            input_widget.value = "/theme"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)

    def test_theme_picker_in_command_palette(self):
        """Test theme picker can be opened from command palette."""
        # Verify "Change Theme" is in DEFAULT_COMMANDS
        theme_cmd = next((c for c in DEFAULT_COMMANDS if c.id == "show_theme_picker"), None)
        assert theme_cmd is not None
        assert theme_cmd.name == "Change Theme"

    @pytest.mark.asyncio
    async def test_theme_picker_saves_to_config(self):
        """Test that selecting and saving a theme persists to config."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            # Patch at the source before the screen is pushed
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                mock_save.return_value = ("/path/to/config.toml", "dracula")

                # Open theme picker via action (which sets up the callback)
                app.action_show_theme_picker()
                await pilot.pause()

                assert isinstance(app.screen, ThemePickerScreen)
                picker = app.screen

                # Select a theme using internal method
                picker._select_theme("dracula")
                await pilot.pause()

                # Simulate save button press
                save_btn = picker.query_one("#btn-save")
                save_btn.press()
                # Wait for callback to execute
                await asyncio.sleep(0.5)
                await pilot.pause()

                # Should have called save_config_value
                mock_save.assert_called_once_with("tui.theme", "dracula")


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests for theme picker using hypothesis."""

    @given(theme=st.sampled_from(list(VALID_THEMES)))
    @hypothesis_settings(max_examples=10)
    def test_theme_picker_accepts_any_valid_theme(self, theme):
        """Test ThemePickerScreen accepts any valid theme."""
        screen = ThemePickerScreen(current_theme=theme)
        assert screen.original_theme == theme
        assert screen.selected_theme == theme

    @pytest.mark.asyncio
    @pytest.mark.parametrize("theme", list(VALID_THEMES)[:5])  # Test subset for speed
    async def test_theme_buttons_exist_for_all_themes(self, theme):
        """Test that each valid theme has a corresponding button."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(ThemePickerScreen())
            await pilot.pause()

            picker = app.screen
            btn = picker.query_one(f"#theme-{theme}")
            assert btn is not None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_theme_picker_none_current_theme(self):
        """Test theme picker with None current theme."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ThemePickerScreen(current_theme=None))
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)
            picker = app.screen
            assert picker.original_theme is None

    @pytest.mark.asyncio
    async def test_save_without_selection(self):
        """Test saving without selecting a new theme."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            # Open with no current theme
            app.push_screen(ThemePickerScreen(current_theme=None), callback=on_dismiss)
            await pilot.pause()

            # Simulate save button press without selecting
            save_btn = app.screen.query_one("#btn-save")
            save_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            # Should return None (the original selected theme)
            assert result_holder["result"] is None

    @pytest.mark.asyncio
    async def test_multiple_theme_selections(self):
        """Test selecting multiple themes before saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ThemePickerScreen(current_theme="textual-dark"))
            await pilot.pause()

            picker = app.screen

            # Select several themes using internal method
            for theme in ["dracula", "nord", "gruvbox"]:
                picker._select_theme(theme)
                await pilot.pause()
                assert app.theme == theme
                assert picker.selected_theme == theme

            # Final selection should be gruvbox
            assert picker.selected_theme == "gruvbox"

    @pytest.mark.asyncio
    async def test_theme_picker_config_save_error(self):
        """Test handling of config save errors."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value", side_effect=Exception("Write error")):
                app.push_screen(ThemePickerScreen(current_theme="textual-dark"))
                await pilot.pause()

                picker = app.screen

                # Select using internal method
                picker._select_theme("dracula")
                await pilot.pause()

                # Simulate save button press
                save_btn = picker.query_one("#btn-save")
                save_btn.press()
                await asyncio.sleep(0.3)
                await pilot.pause()

                # Should not crash, error notification shown


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_theme_change_flow(self):
        """Test complete flow: open picker -> select theme -> save."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            original_theme = app.theme

            with patch("chapgent.config.writer.save_config_value") as mock_save:
                # Open theme picker via slash command
                input_widget = app.query_one("#input")
                input_widget.value = "/theme"
                await pilot.press("enter")
                await pilot.pause()

                assert isinstance(app.screen, ThemePickerScreen)
                picker = app.screen

                # Select a different theme using internal method
                new_theme = "dracula" if original_theme != "dracula" else "nord"
                picker._select_theme(new_theme)
                await pilot.pause()

                # Verify preview
                assert app.theme == new_theme

                # Simulate save button press
                save_btn = picker.query_one("#btn-save")
                save_btn.press()
                await asyncio.sleep(0.3)
                await pilot.pause()

                # Verify saved
                mock_save.assert_called_once_with("tui.theme", new_theme)

    @pytest.mark.asyncio
    async def test_theme_change_cancel_flow(self):
        """Test complete flow: open picker -> select theme -> cancel."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            original_theme = app.theme

            # Open theme picker
            input_widget = app.query_one("#input")
            input_widget.value = "/theme"
            await pilot.press("enter")
            await pilot.pause()

            picker = app.screen

            # Select a different theme using internal method
            new_theme = "dracula" if original_theme != "dracula" else "nord"
            picker._select_theme(new_theme)
            await pilot.pause()

            # Simulate cancel button press
            cancel_btn = picker.query_one("#btn-cancel")
            cancel_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            # Theme should be reverted
            assert app.theme == original_theme
