"""Behavioral tests for TUI modal screens.

These tests verify user-facing behavior, not implementation details.
Each test answers: "When the user does X, what happens?"
"""

import asyncio
from unittest.mock import patch

import pytest

from chapgent.tools.base import ToolCategory
from chapgent.tui.app import ChapgentApp
from chapgent.tui.screens import (
    ConfigShowScreen,
    HelpScreen,
    LLMSettingsScreen,
    SystemPromptScreen,
    ThemePickerScreen,
    ToolsScreen,
    TUISettingsScreen,
)
from chapgent.ux.help import HELP_TOPICS

# =============================================================================
# ThemePickerScreen - User can change the application theme
# =============================================================================


class TestThemePicker:
    """User can select and save a theme."""

    @pytest.mark.asyncio
    async def test_user_can_open_theme_picker(self):
        """Theme picker opens from command palette."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_theme_picker()
            await pilot.pause()
            assert isinstance(app.screen, ThemePickerScreen)

    @pytest.mark.asyncio
    async def test_user_can_select_and_save_theme(self):
        """Selecting a theme and saving persists it."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                mock_save.return_value = ("/path/config.toml", "dracula")

                # Use the app's action which handles the callback
                app.action_show_theme_picker()
                await pilot.pause()

                # Select dracula theme
                picker = app.screen
                picker._select_theme("dracula")
                await pilot.pause()

                # Save
                from textual.widgets import Button

                save_btn = picker.query_one("#btn-save", Button)
                save_btn.press()
                await asyncio.sleep(0.2)
                await pilot.pause()

                # Verify save was called with theme
                mock_save.assert_called_with("tui.theme", "dracula")

    @pytest.mark.asyncio
    async def test_user_can_cancel_theme_selection(self):
        """Canceling reverts to original theme without saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                app.push_screen(ThemePickerScreen(current_theme="textual-dark"))
                await pilot.pause()

                # Select different theme
                picker = app.screen
                picker._select_theme("dracula")
                await pilot.pause()

                # Cancel
                from textual.widgets import Button

                cancel_btn = picker.query_one("#btn-cancel", Button)
                cancel_btn.press()
                await asyncio.sleep(0.1)
                await pilot.pause()

                # Should not have saved
                mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_escape_closes_theme_picker(self):
        """Pressing escape closes without saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ThemePickerScreen())
            await pilot.pause()
            assert isinstance(app.screen, ThemePickerScreen)

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            # Should be back to main screen
            assert not isinstance(app.screen, ThemePickerScreen)


# =============================================================================
# LLMSettingsScreen - User can configure LLM provider and model
# =============================================================================


class TestLLMSettings:
    """User can configure LLM settings."""

    @pytest.mark.asyncio
    async def test_user_can_open_llm_settings(self):
        """LLM settings opens from command palette."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_llm_settings()
            await pilot.pause()
            assert isinstance(app.screen, LLMSettingsScreen)

    @pytest.mark.asyncio
    async def test_user_can_save_llm_settings(self):
        """Saving LLM settings persists provider, model, and max_output_tokens."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            saved_values = {}

            with patch("chapgent.config.writer.save_config_value") as mock_save:

                def capture_save(key, value):
                    saved_values[key] = value
                    return ("/path/config.toml", value)

                mock_save.side_effect = capture_save

                app.action_show_llm_settings()
                await pilot.pause()

                screen = app.screen
                from textual.widgets import Button, Input

                # Change model
                model_input = screen.query_one("#llm-model-input", Input)
                model_input.value = "claude-opus-4-20250514"

                # Change max output tokens
                tokens_input = screen.query_one("#llm-max-output-tokens-input", Input)
                tokens_input.value = "8192"

                # Save
                save_btn = screen.query_one("#btn-save", Button)
                save_btn.press()
                await asyncio.sleep(0.2)
                await pilot.pause()

            assert saved_values.get("llm.model") == "claude-opus-4-20250514"
            assert saved_values.get("llm.max_output_tokens") == "8192"

    @pytest.mark.asyncio
    async def test_invalid_max_output_tokens_shows_error(self):
        """Invalid max_output_tokens value prevents saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                app.action_show_llm_settings()
                await pilot.pause()

                screen = app.screen
                from textual.widgets import Button, Input

                # Enter invalid value
                tokens_input = screen.query_one("#llm-max-output-tokens-input", Input)
                tokens_input.value = "not-a-number"

                # Try to save
                save_btn = screen.query_one("#btn-save", Button)
                save_btn.press()
                await asyncio.sleep(0.2)
                await pilot.pause()

                # Should not save with invalid input
                mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_escape_closes_llm_settings(self):
        """Pressing escape closes without saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(LLMSettingsScreen())
            await pilot.pause()

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, LLMSettingsScreen)


# =============================================================================
# TUISettingsScreen - User can configure TUI appearance
# =============================================================================


class TestTUISettings:
    """User can configure TUI appearance settings."""

    @pytest.mark.asyncio
    async def test_user_can_open_tui_settings(self):
        """TUI settings opens from command palette."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_tui_settings()
            await pilot.pause()
            assert isinstance(app.screen, TUISettingsScreen)

    @pytest.mark.asyncio
    async def test_user_can_toggle_sidebar_setting(self):
        """User can toggle sidebar visibility setting."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(TUISettingsScreen(show_sidebar=True, show_tool_panel=True))
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Checkbox

            sidebar_checkbox = screen.query_one("#tui-show-sidebar", Checkbox)
            assert sidebar_checkbox.value is True

            # Toggle off
            sidebar_checkbox.toggle()
            await pilot.pause()
            assert screen.selected_show_sidebar is False

    @pytest.mark.asyncio
    async def test_user_can_toggle_tool_panel_setting(self):
        """User can toggle tool panel visibility setting."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(TUISettingsScreen(show_sidebar=True, show_tool_panel=True))
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Checkbox

            tool_panel_checkbox = screen.query_one("#tui-show-tool-panel", Checkbox)
            assert tool_panel_checkbox.value is True

            # Toggle off
            tool_panel_checkbox.toggle()
            await pilot.pause()
            assert screen.selected_show_tool_panel is False

    @pytest.mark.asyncio
    async def test_user_can_save_tui_settings(self):
        """Saving TUI settings persists sidebar and tool panel visibility."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            saved_values = {}

            with patch("chapgent.config.writer.save_config_value") as mock_save:

                def capture_save(key, value):
                    saved_values[key] = value
                    return ("/path/config.toml", value)

                mock_save.side_effect = capture_save

                app.action_show_tui_settings()
                await pilot.pause()

                screen = app.screen
                from textual.widgets import Button, Checkbox

                # Toggle both off
                screen.query_one("#tui-show-sidebar", Checkbox).toggle()
                screen.query_one("#tui-show-tool-panel", Checkbox).toggle()
                await pilot.pause()

                # Save
                save_btn = screen.query_one("#btn-save", Button)
                save_btn.press()
                await asyncio.sleep(0.2)
                await pilot.pause()

            assert saved_values.get("tui.show_sidebar") == "false"
            assert saved_values.get("tui.show_tool_panel") == "false"

    @pytest.mark.asyncio
    async def test_escape_closes_tui_settings(self):
        """Pressing escape closes without saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(TUISettingsScreen())
            await pilot.pause()

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, TUISettingsScreen)

    @pytest.mark.asyncio
    async def test_cancel_closes_without_saving(self):
        """Cancel button closes without saving."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                app.push_screen(TUISettingsScreen())
                await pilot.pause()

                screen = app.screen
                from textual.widgets import Button

                cancel_btn = screen.query_one("#btn-cancel", Button)
                cancel_btn.press()
                await asyncio.sleep(0.1)
                await pilot.pause()

                mock_save.assert_not_called()
                assert not isinstance(app.screen, TUISettingsScreen)

    @pytest.mark.asyncio
    async def test_theme_button_opens_theme_picker(self):
        """Theme button opens the theme picker modal."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value"):
                app.push_screen(TUISettingsScreen(current_theme="textual-dark"))
                await pilot.pause()

                screen = app.screen
                from textual.widgets import Button

                theme_btn = screen.query_one("#tui-theme-button", Button)
                theme_btn.press()
                await asyncio.sleep(0.1)
                await pilot.pause()

                # Should now have theme picker on top
                assert isinstance(app.screen, ThemePickerScreen)


# =============================================================================
# HelpScreen - User can browse help documentation
# =============================================================================


class TestHelpScreen:
    """User can browse help topics."""

    @pytest.mark.asyncio
    async def test_user_can_open_help(self):
        """Help screen opens via /help command."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_help()
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_help_shows_all_topics(self):
        """Help screen lists all available topics."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Static

            content = screen.query_one("#help-content")
            topic_items = [s for s in content.query(Static) if s.id and s.id.startswith("topic-")]

            assert len(topic_items) == len(HELP_TOPICS)

    @pytest.mark.asyncio
    async def test_user_can_view_specific_topic(self):
        """Opening help with topic shows that topic directly."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(HelpScreen(topic="tools"))
            await pilot.pause()

            screen = app.screen
            assert screen.current_topic == "tools"

    @pytest.mark.asyncio
    async def test_user_can_navigate_back_to_topic_list(self):
        """Back button returns from topic view to list."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(HelpScreen(topic="tools"))
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Button

            back_btn = screen.query_one("#btn-back", Button)
            back_btn.press()
            await pilot.pause()

            assert screen.current_topic is None

    @pytest.mark.asyncio
    async def test_escape_closes_help(self):
        """Pressing escape closes help screen."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_invalid_topic_shows_list(self):
        """Invalid topic falls back to showing topic list."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(HelpScreen(topic="nonexistent"))
            await pilot.pause()

            screen = app.screen
            assert screen.current_topic is None


# =============================================================================
# ToolsScreen - User can browse available tools
# =============================================================================


class TestToolsScreen:
    """User can browse and filter tools."""

    @pytest.mark.asyncio
    async def test_user_can_open_tools(self):
        """Tools screen opens via /tools command."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_tools()
            await pilot.pause()
            assert isinstance(app.screen, ToolsScreen)

    @pytest.mark.asyncio
    async def test_tools_shows_all_categories(self):
        """Tools screen shows tools grouped by category."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ToolsScreen())
            await pilot.pause()

            screen = app.screen
            tools = screen._get_all_tools()

            # Should have tools from multiple categories
            categories = {t.category for t in tools}
            assert len(categories) >= 5  # filesystem, git, search, shell, etc.

    @pytest.mark.asyncio
    async def test_user_can_filter_by_category(self):
        """Filtering by category shows only matching tools."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ToolsScreen(category="git"))
            await pilot.pause()

            screen = app.screen
            tools = screen._get_tools()

            for tool in tools:
                assert tool.category == ToolCategory.GIT

    @pytest.mark.asyncio
    async def test_user_can_search_tools(self):
        """Search filters tools by name or description."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ToolsScreen())
            await pilot.pause()

            screen = app.screen
            from textual.widgets import Input

            search = screen.query_one("#tools-search", Input)
            search.value = "file"
            await pilot.pause()

            tools = screen._get_tools()
            for tool in tools:
                assert "file" in tool.name.lower() or "file" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_escape_closes_tools(self):
        """Pressing escape closes tools screen."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ToolsScreen())
            await pilot.pause()

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, ToolsScreen)


# =============================================================================
# Slash Command Integration - User can access screens via commands
# =============================================================================


class TestSlashCommands:
    """User can open screens via slash commands."""

    @pytest.mark.asyncio
    async def test_slash_help_opens_help_screen(self):
        """/help opens the help screen."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/help"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_slash_help_with_topic(self):
        """/help tools opens help to tools topic."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/help tools"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, HelpScreen)
            assert app.screen.current_topic == "tools"

    @pytest.mark.asyncio
    async def test_slash_tools_opens_tools_screen(self):
        """/tools opens the tools screen."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/tools"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ToolsScreen)

    @pytest.mark.asyncio
    async def test_slash_tools_with_category(self):
        """/tools git opens tools filtered by git category."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/tools git"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ToolsScreen)
            assert app.screen.current_category == "git"

    @pytest.mark.asyncio
    async def test_slash_theme_opens_theme_picker(self):
        """/theme opens the theme picker."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/theme"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ThemePickerScreen)

    @pytest.mark.asyncio
    async def test_slash_model_opens_llm_settings(self):
        """/model opens the LLM settings."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/model"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, LLMSettingsScreen)

    @pytest.mark.asyncio
    async def test_slash_tui_opens_tui_settings(self):
        """/tui opens the TUI settings."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/tui"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, TUISettingsScreen)

    @pytest.mark.asyncio
    async def test_slash_ui_alias_opens_tui_settings(self):
        """/ui alias opens the TUI settings."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/ui"
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, TUISettingsScreen)

    @pytest.mark.asyncio
    async def test_slash_prompt_opens_system_prompt_screen(self):
        """/prompt opens the system prompt screen."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/prompt"
            await pilot.press("enter")
            await pilot.pause()

            from chapgent.tui.screens import SystemPromptScreen

            assert isinstance(app.screen, SystemPromptScreen)

    @pytest.mark.asyncio
    async def test_slash_config_show_opens_config_screen(self):
        """/config show opens the config display screen."""
        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            input_widget = app.query_one("#input")
            input_widget.value = "/config show"
            await pilot.press("enter")
            await pilot.pause()

            from chapgent.tui.screens import ConfigShowScreen

            assert isinstance(app.screen, ConfigShowScreen)


# =============================================================================
# SystemPromptScreen - User can configure system prompt
# =============================================================================


class TestSystemPromptScreen:
    """User can configure system prompt settings."""

    @pytest.mark.asyncio
    async def test_user_can_open_prompt_settings(self):
        """System prompt screen opens from command palette."""
        from chapgent.tui.screens import SystemPromptScreen

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_prompt_settings()
            await pilot.pause()
            assert isinstance(app.screen, SystemPromptScreen)

    @pytest.mark.asyncio
    async def test_user_can_edit_prompt_content(self):
        """User can edit the prompt content in the text area."""
        from chapgent.tui.screens import SystemPromptScreen
        from textual.widgets import TextArea

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(SystemPromptScreen(current_content="Initial content"))
            await pilot.pause()

            screen = app.screen
            text_area = screen.query_one("#prompt-content-area", TextArea)
            assert text_area.text == "Initial content"

    @pytest.mark.asyncio
    async def test_user_can_toggle_mode_to_replace(self):
        """User can switch mode from append to replace."""
        from chapgent.tui.screens import SystemPromptScreen
        from textual.widgets import RadioButton

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(SystemPromptScreen(current_mode="append"))
            await pilot.pause()

            screen = app.screen
            replace_btn = screen.query_one("#mode-replace", RadioButton)
            replace_btn.toggle()
            await pilot.pause()

            assert screen.selected_mode == "replace"

    @pytest.mark.asyncio
    async def test_user_can_set_file_path(self):
        """User can specify a file path for the prompt."""
        from chapgent.tui.screens import SystemPromptScreen
        from textual.widgets import Input

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(SystemPromptScreen())
            await pilot.pause()

            screen = app.screen
            file_input = screen.query_one("#prompt-file-input", Input)
            file_input.value = "~/.config/chapgent/prompt.md"
            await pilot.pause()

            assert screen.selected_file == "~/.config/chapgent/prompt.md"

    @pytest.mark.asyncio
    async def test_user_can_save_prompt_settings(self):
        """Saving prompt settings persists content, mode, and file."""
        from chapgent.tui.screens import SystemPromptScreen
        from textual.widgets import Button, TextArea

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            saved_values = {}

            with patch("chapgent.config.writer.save_config_value") as mock_save:

                def capture_save(key, value):
                    saved_values[key] = value
                    return ("/path/config.toml", value)

                mock_save.side_effect = capture_save

                app.action_show_prompt_settings()
                await pilot.pause()

                screen = app.screen
                # Edit the content
                text_area = screen.query_one("#prompt-content-area", TextArea)
                text_area.clear()
                text_area.insert("Custom prompt content")
                await pilot.pause()

                # Save
                save_btn = screen.query_one("#btn-save", Button)
                save_btn.press()
                await asyncio.sleep(0.2)
                await pilot.pause()

            assert saved_values.get("system_prompt.content") == "Custom prompt content"
            assert saved_values.get("system_prompt.mode") == "append"

    @pytest.mark.asyncio
    async def test_escape_closes_prompt_settings(self):
        """Pressing escape closes without saving."""
        from chapgent.tui.screens import SystemPromptScreen

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(SystemPromptScreen())
            await pilot.pause()

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, SystemPromptScreen)

    @pytest.mark.asyncio
    async def test_cancel_closes_without_saving(self):
        """Cancel button closes without saving."""
        from chapgent.tui.screens import SystemPromptScreen
        from textual.widgets import Button

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            with patch("chapgent.config.writer.save_config_value") as mock_save:
                app.push_screen(SystemPromptScreen())
                await pilot.pause()

                screen = app.screen
                cancel_btn = screen.query_one("#btn-cancel", Button)
                cancel_btn.press()
                await asyncio.sleep(0.1)
                await pilot.pause()

                mock_save.assert_not_called()
                assert not isinstance(app.screen, SystemPromptScreen)


# =============================================================================
# ConfigShowScreen - User can view current configuration
# =============================================================================


class TestConfigShowScreen:
    """User can view current configuration."""

    @pytest.mark.asyncio
    async def test_user_can_open_config_show(self):
        """Config show screen opens from command palette."""
        from chapgent.tui.screens import ConfigShowScreen

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.action_show_config()
            await pilot.pause()
            assert isinstance(app.screen, ConfigShowScreen)

    @pytest.mark.asyncio
    async def test_config_shows_llm_settings(self):
        """Config screen displays LLM settings when provided."""
        from chapgent.config.settings import Settings
        from chapgent.tui.screens import ConfigShowScreen
        from textual.containers import VerticalScroll
        from textual.widgets import Static

        settings = Settings()
        settings.llm.model = "test-model"
        settings.llm.provider = "anthropic"

        app = ChapgentApp(settings=settings)
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ConfigShowScreen(settings=settings))
            await pilot.pause()

            screen = app.screen
            content = screen.query_one("#config-content", VerticalScroll)

            # Should have populated content (multiple Static widgets)
            statics = content.query(Static)
            # With settings, we should have section headers and items (more than 10 items)
            assert len(statics) > 10

    @pytest.mark.asyncio
    async def test_config_shows_tui_settings(self):
        """Config screen mounts correctly with TUI settings."""
        from chapgent.config.settings import Settings
        from chapgent.tui.screens import ConfigShowScreen
        from textual.containers import VerticalScroll
        from textual.widgets import Static

        settings = Settings()
        settings.tui.theme = "dracula"

        app = ChapgentApp(settings=settings)
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ConfigShowScreen(settings=settings))
            await pilot.pause()

            screen = app.screen
            # Verify the screen has the expected structure
            assert screen.query_one("#config-title")
            assert screen.query_one("#config-content")
            assert screen.query_one("#btn-close")

    @pytest.mark.asyncio
    async def test_config_shows_no_settings_message(self):
        """Config screen shows minimal content when no settings available."""
        from chapgent.tui.screens import ConfigShowScreen
        from textual.containers import VerticalScroll
        from textual.widgets import Static

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ConfigShowScreen(settings=None))
            await pilot.pause()

            screen = app.screen
            content = screen.query_one("#config-content", VerticalScroll)

            # Query for all Static widgets in the content
            statics = content.query(Static)
            # With no settings, we should have just one Static with the "no config" message
            assert len(statics) == 1

    @pytest.mark.asyncio
    async def test_escape_closes_config_show(self):
        """Pressing escape closes config show screen."""
        from chapgent.tui.screens import ConfigShowScreen

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ConfigShowScreen())
            await pilot.pause()

            await pilot.press("escape")
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, ConfigShowScreen)

    @pytest.mark.asyncio
    async def test_close_button_closes_screen(self):
        """Close button closes config show screen."""
        from chapgent.tui.screens import ConfigShowScreen
        from textual.widgets import Button

        app = ChapgentApp()
        async with app.run_test(size=(100, 50)) as pilot:
            app.push_screen(ConfigShowScreen())
            await pilot.pause()

            screen = app.screen
            close_btn = screen.query_one("#btn-close", Button)
            close_btn.press()
            await asyncio.sleep(0.1)
            await pilot.pause()

            assert not isinstance(app.screen, ConfigShowScreen)
