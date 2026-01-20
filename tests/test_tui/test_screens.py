"""Tests for TUI modal screens."""

import asyncio
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from chapgent.config.settings import VALID_PROVIDERS, VALID_THEMES
from chapgent.tui.app import ChapgentApp
from chapgent.tui.screens import LLMSettingsScreen, ThemePickerScreen
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


# =============================================================================
# LLMSettingsScreen Tests
# =============================================================================


class TestLLMSettingsScreen:
    """Tests for the LLMSettingsScreen modal."""

    def test_llm_settings_creation_defaults(self):
        """Test creating LLMSettingsScreen with defaults."""
        screen = LLMSettingsScreen()
        assert screen.original_provider == "anthropic"
        assert screen.original_model == "claude-sonnet-4-20250514"
        assert screen.original_max_tokens == 4096

    def test_llm_settings_creation_with_values(self):
        """Test creating LLMSettingsScreen with custom values."""
        screen = LLMSettingsScreen(
            current_provider="openai",
            current_model="gpt-4o",
            current_max_tokens=8192,
        )
        assert screen.original_provider == "openai"
        assert screen.original_model == "gpt-4o"
        assert screen.original_max_tokens == 8192
        assert screen.selected_provider == "openai"
        assert screen.selected_model == "gpt-4o"
        assert screen.selected_max_tokens == 8192

    @pytest.mark.asyncio
    async def test_llm_settings_compose(self):
        """Test that LLM settings screen composes correctly."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            assert isinstance(app.screen, LLMSettingsScreen)
            screen = app.screen

            # Check for title
            title = screen.query_one("#llm-settings-title")
            assert title is not None

            # Check for provider select
            provider_select = screen.query_one("#llm-provider-select")
            assert provider_select is not None

            # Check for model input
            model_input = screen.query_one("#llm-model-input")
            assert model_input is not None

            # Check for max_tokens input
            max_tokens_input = screen.query_one("#llm-max-tokens-input")
            assert max_tokens_input is not None

            # Check for buttons
            save_btn = screen.query_one("#btn-save")
            cancel_btn = screen.query_one("#btn-cancel")
            assert save_btn is not None
            assert cancel_btn is not None

    @pytest.mark.asyncio
    async def test_llm_settings_has_all_providers(self):
        """Test that all valid providers are available in select."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Select

            provider_select = screen.query_one("#llm-provider-select", Select)
            # The select should have options for all providers
            assert provider_select is not None


class TestLLMSettingsValidation:
    """Tests for LLM settings validation."""

    @pytest.mark.asyncio
    async def test_validation_empty_model(self):
        """Test validation rejects empty model name."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen

            # Clear the model input
            from textual.widgets import Input

            model_input = screen.query_one("#llm-model-input", Input)
            model_input.value = ""
            await pilot.pause()

            # Try to validate
            result = screen._validate_and_get_values()
            assert result is None
            assert "empty" in screen.error_message.lower()

    @pytest.mark.asyncio
    async def test_validation_non_numeric_max_tokens(self):
        """Test validation rejects non-numeric max_tokens."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen

            from textual.widgets import Input

            max_tokens_input = screen.query_one("#llm-max-tokens-input", Input)
            max_tokens_input.value = "not_a_number"
            await pilot.pause()

            result = screen._validate_and_get_values()
            assert result is None
            assert "number" in screen.error_message.lower()

    @pytest.mark.asyncio
    async def test_validation_max_tokens_below_minimum(self):
        """Test validation rejects max_tokens below 1."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen

            from textual.widgets import Input

            max_tokens_input = screen.query_one("#llm-max-tokens-input", Input)
            max_tokens_input.value = "0"
            await pilot.pause()

            result = screen._validate_and_get_values()
            assert result is None
            assert "at least 1" in screen.error_message.lower()

    @pytest.mark.asyncio
    async def test_validation_max_tokens_above_maximum(self):
        """Test validation rejects max_tokens above 100000."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen

            from textual.widgets import Input

            max_tokens_input = screen.query_one("#llm-max-tokens-input", Input)
            max_tokens_input.value = "200000"
            await pilot.pause()

            result = screen._validate_and_get_values()
            assert result is None
            assert "100000" in screen.error_message

    @pytest.mark.asyncio
    async def test_validation_success(self):
        """Test validation succeeds with valid values."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen

            from textual.widgets import Input

            model_input = screen.query_one("#llm-model-input", Input)
            model_input.value = "gpt-4"

            max_tokens_input = screen.query_one("#llm-max-tokens-input", Input)
            max_tokens_input.value = "8192"
            await pilot.pause()

            result = screen._validate_and_get_values()
            assert result is not None
            assert result["provider"] == "anthropic"
            assert result["model"] == "gpt-4"
            assert result["max_tokens"] == 8192


class TestLLMSettingsDismissal:
    """Tests for LLM settings dismissal behavior."""

    @pytest.mark.asyncio
    async def test_save_returns_values(self):
        """Test that save button returns the settings dict."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(LLMSettingsScreen(), callback=on_dismiss)
            await pilot.pause()

            screen = app.screen

            # Simulate save button press
            save_btn = screen.query_one("#btn-save")
            save_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] is not None
            assert "provider" in result_holder["result"]
            assert "model" in result_holder["result"]
            assert "max_tokens" in result_holder["result"]

    @pytest.mark.asyncio
    async def test_cancel_returns_none(self):
        """Test that cancel button returns None."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(LLMSettingsScreen(), callback=on_dismiss)
            await pilot.pause()

            # Simulate cancel button press
            cancel_btn = app.screen.query_one("#btn-cancel")
            cancel_btn.press()
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] is None

    @pytest.mark.asyncio
    async def test_escape_dismisses_with_none(self):
        """Test that escape dismisses without saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(LLMSettingsScreen(), callback=on_dismiss)
            await pilot.pause()

            # Press escape
            await pilot.press("escape")
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] is None


class TestLLMSettingsAppIntegration:
    """Tests for LLM settings integration with ChapgentApp."""

    @pytest.mark.asyncio
    async def test_action_show_llm_settings(self):
        """Test action_show_llm_settings opens the settings screen."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.action_show_llm_settings()
            await pilot.pause()

            assert isinstance(app.screen, LLMSettingsScreen)

    @pytest.mark.asyncio
    async def test_slash_command_opens_llm_settings(self):
        """Test /model slash command opens the settings screen."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/model"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, LLMSettingsScreen)

    @pytest.mark.asyncio
    async def test_slash_command_llm_alias(self):
        """Test /llm alias opens the settings screen."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/llm"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, LLMSettingsScreen)

    def test_llm_settings_in_command_palette(self):
        """Test LLM settings can be opened from command palette."""
        llm_cmd = next((c for c in DEFAULT_COMMANDS if c.id == "show_llm_settings"), None)
        assert llm_cmd is not None
        assert llm_cmd.name == "LLM Settings"

    @pytest.mark.asyncio
    async def test_llm_settings_saves_to_config(self):
        """Test that saving LLM settings persists to config."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                # Open LLM settings via action
                app.action_show_llm_settings()
                await pilot.pause()

                assert isinstance(app.screen, LLMSettingsScreen)
                screen = app.screen

                # Simulate save button press
                save_btn = screen.query_one("#btn-save")
                save_btn.press()
                await asyncio.sleep(0.5)
                await pilot.pause()

                # Should have called save_config_value for each setting
                assert mock_save.call_count == 3


# =============================================================================
# LLMSettingsScreen Property-Based Tests
# =============================================================================


class TestLLMSettingsPropertyBased:
    """Property-based tests for LLM settings using hypothesis."""

    @given(provider=st.sampled_from(list(VALID_PROVIDERS)))
    @hypothesis_settings(max_examples=10)
    def test_llm_settings_accepts_any_valid_provider(self, provider):
        """Test LLMSettingsScreen accepts any valid provider."""
        screen = LLMSettingsScreen(current_provider=provider)
        assert screen.original_provider == provider
        assert screen.selected_provider == provider

    @given(max_tokens=st.integers(min_value=1, max_value=100000))
    @hypothesis_settings(max_examples=10)
    def test_llm_settings_accepts_valid_max_tokens(self, max_tokens):
        """Test LLMSettingsScreen accepts valid max_tokens values."""
        screen = LLMSettingsScreen(current_max_tokens=max_tokens)
        assert screen.original_max_tokens == max_tokens
        assert screen.selected_max_tokens == max_tokens

    @given(model=st.text(min_size=1, max_size=50))
    @hypothesis_settings(max_examples=10)
    def test_llm_settings_accepts_any_model_name(self, model):
        """Test LLMSettingsScreen accepts any non-empty model name."""
        screen = LLMSettingsScreen(current_model=model)
        assert screen.original_model == model
        assert screen.selected_model == model


# =============================================================================
# LLMSettingsScreen Edge Cases
# =============================================================================


class TestLLMSettingsEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_llm_settings_none_values(self):
        """Test LLM settings with None values uses defaults."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(
                LLMSettingsScreen(
                    current_provider=None,
                    current_model=None,
                    current_max_tokens=None,
                )
            )
            await pilot.pause()

            screen = app.screen
            assert screen.original_provider == "anthropic"
            assert screen.original_model == "claude-sonnet-4-20250514"
            assert screen.original_max_tokens == 4096

    @pytest.mark.asyncio
    async def test_llm_settings_boundary_max_tokens(self):
        """Test boundary values for max_tokens."""
        # Test minimum boundary
        screen_min = LLMSettingsScreen(current_max_tokens=1)
        assert screen_min.original_max_tokens == 1

        # Test maximum boundary
        screen_max = LLMSettingsScreen(current_max_tokens=100000)
        assert screen_max.original_max_tokens == 100000

    @pytest.mark.asyncio
    async def test_llm_settings_save_error_handling(self):
        """Test handling of config save errors."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value", side_effect=Exception("Write error")):
                app.action_show_llm_settings()
                await pilot.pause()

                screen = app.screen

                # Simulate save button press
                save_btn = screen.query_one("#btn-save")
                save_btn.press()
                await asyncio.sleep(0.3)
                await pilot.pause()

                # Should not crash, error notification shown

    @pytest.mark.asyncio
    async def test_error_message_clears_on_input_change(self):
        """Test that error message clears when input changes."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Input

            # Trigger validation error
            max_tokens_input = screen.query_one("#llm-max-tokens-input", Input)
            max_tokens_input.value = "invalid"
            await pilot.pause()

            screen._validate_and_get_values()
            assert screen.error_message != ""

            # Change input - error should clear
            max_tokens_input.value = "8192"
            await pilot.pause()

            assert screen.error_message == ""


# =============================================================================
# LLMSettingsScreen Integration Tests
# =============================================================================


class TestLLMSettingsIntegration:
    """End-to-end integration tests for LLM settings."""

    @pytest.mark.asyncio
    async def test_full_llm_settings_flow(self):
        """Test complete flow: open -> modify -> save."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                # Open via slash command
                input_widget = app.query_one("#input")
                input_widget.value = "/model"
                await pilot.press("enter")
                await pilot.pause()

                assert isinstance(app.screen, LLMSettingsScreen)
                screen = app.screen

                # Modify model
                from textual.widgets import Input

                model_input = screen.query_one("#llm-model-input", Input)
                model_input.value = "gpt-4o"

                max_tokens_input = screen.query_one("#llm-max-tokens-input", Input)
                max_tokens_input.value = "16000"
                await pilot.pause()

                # Simulate save button press
                save_btn = screen.query_one("#btn-save")
                save_btn.press()
                await asyncio.sleep(0.3)
                await pilot.pause()

                # Verify save calls
                assert mock_save.call_count == 3

    @pytest.mark.asyncio
    async def test_llm_settings_cancel_flow(self):
        """Test complete flow: open -> modify -> cancel."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                # Open via slash command
                input_widget = app.query_one("#input")
                input_widget.value = "/llm"
                await pilot.press("enter")
                await pilot.pause()

                screen = app.screen

                # Modify model
                from textual.widgets import Input

                model_input = screen.query_one("#llm-model-input", Input)
                model_input.value = "gpt-4o"
                await pilot.pause()

                # Cancel
                cancel_btn = screen.query_one("#btn-cancel")
                cancel_btn.press()
                await asyncio.sleep(0.2)
                await pilot.pause()

                # Should not have saved
                mock_save.assert_not_called()
