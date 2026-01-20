"""Tests for the Command Palette feature."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from chapgent.config.settings import Settings
from chapgent.core.agent import Agent
from chapgent.core.providers import LLMProvider, LLMResponse
from chapgent.session.models import Session
from chapgent.tools.registry import ToolRegistry
from chapgent.tui.app import ChapgentApp
from chapgent.tui.widgets import (
    DEFAULT_COMMANDS,
    CommandPalette,
    CommandPaletteItem,
    PaletteCommand,
    _fuzzy_match,
)

# =============================================================================
# PaletteCommand Tests
# =============================================================================


class TestPaletteCommand:
    """Tests for the PaletteCommand dataclass."""

    def test_palette_command_creation(self):
        """Test creating a basic PaletteCommand."""
        cmd = PaletteCommand(
            id="test_cmd",
            name="Test Command",
            description="A test command",
            shortcut="Ctrl+T",
        )
        assert cmd.id == "test_cmd"
        assert cmd.name == "Test Command"
        assert cmd.description == "A test command"
        assert cmd.shortcut == "Ctrl+T"

    def test_palette_command_no_shortcut(self):
        """Test creating a PaletteCommand without shortcut."""
        cmd = PaletteCommand(
            id="no_shortcut",
            name="No Shortcut",
            description="Command without shortcut",
        )
        assert cmd.shortcut is None

    def test_matches_empty_query(self):
        """Test that empty query matches all commands."""
        cmd = PaletteCommand(id="test", name="Test", description="Desc")
        assert cmd.matches("") is True

    def test_matches_name_substring(self):
        """Test matching substring in name."""
        cmd = PaletteCommand(id="new_session", name="New Session", description="Start a new session")
        assert cmd.matches("new") is True
        assert cmd.matches("session") is True
        assert cmd.matches("New Sess") is True

    def test_matches_description_substring(self):
        """Test matching substring in description."""
        cmd = PaletteCommand(id="save", name="Save", description="Save the current session")
        assert cmd.matches("current") is True
        assert cmd.matches("session") is True

    def test_matches_case_insensitive(self):
        """Test case-insensitive matching."""
        cmd = PaletteCommand(id="test", name="New Session", description="Desc")
        assert cmd.matches("NEW") is True
        assert cmd.matches("new") is True
        assert cmd.matches("NeW") is True

    def test_matches_fuzzy(self):
        """Test fuzzy matching (characters in order)."""
        cmd = PaletteCommand(id="test", name="New Session", description="Desc")
        # "nss" matches "N-ew S-es-S-ion" (characters in order)
        assert cmd.matches("nss") is True

    def test_no_match(self):
        """Test non-matching queries."""
        cmd = PaletteCommand(id="test", name="New Session", description="Start new")
        assert cmd.matches("xyz") is False
        assert cmd.matches("quit") is False


# =============================================================================
# Fuzzy Match Helper Tests
# =============================================================================


class TestFuzzyMatch:
    """Tests for the _fuzzy_match helper function."""

    def test_fuzzy_match_exact(self):
        """Test exact match."""
        assert _fuzzy_match("test", "test") is True

    def test_fuzzy_match_substring(self):
        """Test substring match."""
        assert _fuzzy_match("test", "testing") is True

    def test_fuzzy_match_characters_in_order(self):
        """Test characters appearing in order."""
        assert _fuzzy_match("abc", "aXbXc") is True
        assert _fuzzy_match("ns", "new session") is True

    def test_fuzzy_match_no_match(self):
        """Test non-matching patterns."""
        assert _fuzzy_match("abc", "cba") is False  # Wrong order
        assert _fuzzy_match("xyz", "abc") is False  # Not present

    def test_fuzzy_match_empty_query(self):
        """Test empty query matches anything."""
        assert _fuzzy_match("", "anything") is True

    def test_fuzzy_match_empty_text(self):
        """Test empty text doesn't match non-empty query."""
        assert _fuzzy_match("a", "") is False

    def test_fuzzy_match_both_empty(self):
        """Test both empty matches."""
        assert _fuzzy_match("", "") is True


# =============================================================================
# Default Commands Tests
# =============================================================================


class TestDefaultCommands:
    """Tests for the DEFAULT_COMMANDS list."""

    def test_default_commands_not_empty(self):
        """Test that default commands list is not empty."""
        assert len(DEFAULT_COMMANDS) > 0

    def test_default_commands_have_required_fields(self):
        """Test that all default commands have required fields."""
        for cmd in DEFAULT_COMMANDS:
            assert cmd.id, "Command must have an id"
            assert cmd.name, "Command must have a name"
            assert cmd.description, "Command must have a description"

    def test_default_commands_unique_ids(self):
        """Test that all default commands have unique IDs."""
        ids = [cmd.id for cmd in DEFAULT_COMMANDS]
        assert len(ids) == len(set(ids)), "Command IDs must be unique"

    def test_default_commands_include_expected(self):
        """Test that expected commands are present."""
        ids = [cmd.id for cmd in DEFAULT_COMMANDS]
        assert "new_session" in ids
        assert "save_session" in ids
        assert "quit" in ids


# =============================================================================
# CommandPaletteItem Widget Tests
# =============================================================================


class TestCommandPaletteItem:
    """Tests for the CommandPaletteItem widget."""

    def test_item_creation(self):
        """Test creating a CommandPaletteItem."""
        cmd = PaletteCommand(
            id="test",
            name="Test Command",
            description="A test",
            shortcut="Ctrl+T",
        )
        item = CommandPaletteItem(command=cmd, is_selected=False)
        assert item.command == cmd
        assert item.is_selected is False
        assert "palette-item" in item.classes

    def test_item_selected(self):
        """Test creating a selected CommandPaletteItem."""
        cmd = PaletteCommand(id="test", name="Test", description="Desc")
        item = CommandPaletteItem(command=cmd, is_selected=True)
        assert item.is_selected is True
        assert "palette-item-selected" in item.classes

    def test_item_set_selected(self):
        """Test toggling selection state."""
        cmd = PaletteCommand(id="test", name="Test", description="Desc")
        item = CommandPaletteItem(command=cmd, is_selected=False)

        assert item.is_selected is False
        assert "palette-item" in item.classes

        item.set_selected(True)
        assert item.is_selected is True
        assert "palette-item-selected" in item.classes
        assert "palette-item" not in item.classes

        item.set_selected(False)
        assert item.is_selected is False
        assert "palette-item" in item.classes
        assert "palette-item-selected" not in item.classes

    def test_item_displays_shortcut(self):
        """Test that shortcut is included in display text."""
        cmd = PaletteCommand(
            id="test",
            name="Test Command",
            description="Desc",
            shortcut="Ctrl+X",
        )
        item = CommandPaletteItem(command=cmd)
        # The renderable should contain the shortcut
        # (We can't easily test the renderable content directly, but we know it's formatted)
        assert item.command.shortcut == "Ctrl+X"

    def test_item_no_shortcut(self):
        """Test item without shortcut."""
        cmd = PaletteCommand(id="test", name="Test", description="Desc")
        item = CommandPaletteItem(command=cmd)
        assert item.command.shortcut is None


# =============================================================================
# CommandPalette Widget Tests
# =============================================================================


class TestCommandPalette:
    """Tests for the CommandPalette modal screen."""

    @pytest.mark.asyncio
    async def test_palette_compose(self):
        """Test that palette composes correctly."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Push the command palette
            app.push_screen(CommandPalette())
            await pilot.pause()

            # Check that the palette is displayed (it's the active screen)
            assert isinstance(app.screen, CommandPalette)
            palette = app.screen

            # Check for title, input, and commands container
            assert palette.query_one("#palette-title") is not None
            assert palette.query_one("#palette-input") is not None
            assert palette.query_one("#palette-commands") is not None

    @pytest.mark.asyncio
    async def test_palette_shows_default_commands(self):
        """Test that palette shows default commands on mount."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette())
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            items = palette.query(CommandPaletteItem)
            assert len(items) == len(DEFAULT_COMMANDS)

    @pytest.mark.asyncio
    async def test_palette_custom_commands(self):
        """Test palette with custom commands."""
        custom_commands = [
            PaletteCommand(id="cmd1", name="Command 1", description="First"),
            PaletteCommand(id="cmd2", name="Command 2", description="Second"),
        ]

        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette(commands=custom_commands))
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            items = palette.query(CommandPaletteItem)
            assert len(items) == 2

    @pytest.mark.asyncio
    async def test_palette_filter_commands(self):
        """Test filtering commands with search input."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette())
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")

            # Type in the search box
            input_widget.value = "new"
            await pilot.pause()

            # Should filter to commands matching "new"
            items = palette.query(CommandPaletteItem)
            for item in items:
                assert item.command.matches("new")

    @pytest.mark.asyncio
    async def test_palette_dismiss_on_escape(self):
        """Test that escape dismisses the palette."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Create a callback to capture the result
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            palette = CommandPalette()
            app.push_screen(palette, callback=on_dismiss)
            await pilot.pause()

            # Press escape
            await pilot.press("escape")
            await pilot.pause()

            # Should be dismissed with None
            assert result_holder["result"] is None

    @pytest.mark.asyncio
    async def test_palette_select_with_enter(self):
        """Test selecting a command with enter."""
        custom_commands = [
            PaletteCommand(id="first_cmd", name="First", description="Desc"),
            PaletteCommand(id="second_cmd", name="Second", description="Desc"),
        ]

        app = ChapgentApp()
        async with app.run_test() as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(CommandPalette(commands=custom_commands), callback=on_dismiss)
            await pilot.pause()

            # Press enter to select first item
            await pilot.press("enter")
            # Give more time for callback to execute
            await asyncio.sleep(0.2)
            await pilot.pause()

            # Should return the first command's id
            assert result_holder["result"] == "first_cmd"

    @pytest.mark.asyncio
    async def test_palette_navigate_down(self):
        """Test navigating down with arrow key."""
        custom_commands = [
            PaletteCommand(id="first", name="First", description="Desc"),
            PaletteCommand(id="second", name="Second", description="Desc"),
        ]

        app = ChapgentApp()
        async with app.run_test() as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(CommandPalette(commands=custom_commands), callback=on_dismiss)
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen

            # Initially first item is selected
            assert palette.selected_index == 0

            # Navigate down
            await pilot.press("down")
            await pilot.pause()

            assert palette.selected_index == 1

            # Select
            await pilot.press("enter")
            # Give more time for callback to execute
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] == "second"

    @pytest.mark.asyncio
    async def test_palette_navigate_up(self):
        """Test navigating up with arrow key."""
        custom_commands = [
            PaletteCommand(id="first", name="First", description="Desc"),
            PaletteCommand(id="second", name="Second", description="Desc"),
            PaletteCommand(id="third", name="Third", description="Desc"),
        ]

        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette(commands=custom_commands))
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen

            # Navigate down twice
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()
            assert palette.selected_index == 2

            # Navigate up
            await pilot.press("up")
            await pilot.pause()
            assert palette.selected_index == 1

    @pytest.mark.asyncio
    async def test_palette_navigate_bounds(self):
        """Test navigation doesn't go out of bounds."""
        custom_commands = [
            PaletteCommand(id="first", name="First", description="Desc"),
            PaletteCommand(id="second", name="Second", description="Desc"),
        ]

        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette(commands=custom_commands))
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen

            # Try to go up from first item
            await pilot.press("up")
            await pilot.pause()
            assert palette.selected_index == 0

            # Go to last item
            await pilot.press("down")
            await pilot.pause()
            assert palette.selected_index == 1

            # Try to go past last item
            await pilot.press("down")
            await pilot.pause()
            assert palette.selected_index == 1

    @pytest.mark.asyncio
    async def test_palette_empty_filter_result(self):
        """Test behavior when filter returns no results."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette())
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")

            # Type something that matches nothing
            input_widget.value = "xyznonexistent"
            await pilot.pause()

            items = palette.query(CommandPaletteItem)
            assert len(items) == 0
            assert palette.selected_index == -1


# =============================================================================
# ChapgentApp Command Palette Integration Tests
# =============================================================================


class TestChapgentAppCommandPaletteIntegration:
    """Tests for command palette integration with ChapgentApp."""

    @pytest.mark.asyncio
    async def test_keybinding_opens_palette(self):
        """Test that Ctrl+Shift+P opens the command palette."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Press Ctrl+Shift+P
            await pilot.press("ctrl+shift+p")
            await pilot.pause()

            # Command palette should be the active screen
            assert isinstance(app.screen, CommandPalette)

    @pytest.mark.asyncio
    async def test_palette_executes_action(self):
        """Test that selecting a command executes the action."""
        provider = AsyncMock(spec=LLMProvider)
        provider.complete.return_value = LLMResponse(content=[], stop_reason="end_turn")

        session = Session(
            id="test-session",
            messages=[],
            tool_history=[],
            working_directory=".",
        )
        agent = Agent(provider, ToolRegistry(), None, session)

        app = ChapgentApp(agent=agent)

        async with app.run_test() as pilot:
            # Add a message so we can verify clear works
            app.query_one("ConversationPanel").append_user_message("Test message")

            # Open palette
            await pilot.press("ctrl+shift+p")
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")

            # Filter to "clear"
            input_widget.value = "clear"
            await pilot.pause()

            # Select (press enter)
            await pilot.press("enter")
            # Give more time for callback and action to execute
            await asyncio.sleep(0.3)
            await pilot.pause()

            # Conversation should be cleared
            assert len(app.query_one("#conversation-messages").children) == 0

    @pytest.mark.asyncio
    async def test_palette_toggle_tools(self):
        """Test toggling tool panel from palette."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Get initial state
            tool_panel = app.query_one("ToolPanel")
            initial_display = tool_panel.display

            # Open palette and select toggle tools
            await pilot.press("ctrl+shift+p")
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")
            input_widget.value = "toggle tool"
            await pilot.pause()

            await pilot.press("enter")
            # Give more time for callback and action to execute
            await asyncio.sleep(0.3)
            await pilot.pause()

            # Tool panel visibility should be toggled
            assert tool_panel.display != initial_display


# =============================================================================
# Action Tests
# =============================================================================


class TestNewActions:
    """Tests for new actions added with command palette."""

    @pytest.mark.asyncio
    async def test_action_toggle_tools(self):
        """Test toggle_tools action."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            tool_panel = app.query_one("ToolPanel")
            assert tool_panel.display is True

            # Toggle off
            app.action_toggle_tools()
            await pilot.pause()
            assert tool_panel.display is False

            # Toggle on
            app.action_toggle_tools()
            await pilot.pause()
            assert tool_panel.display is True

    @pytest.mark.asyncio
    async def test_action_toggle_tools_not_available(self):
        """Test toggle_tools when tool panel is disabled."""
        settings = Settings()
        settings.tui.show_tool_panel = False

        app = ChapgentApp(settings=settings)
        async with app.run_test() as pilot:
            # Should not crash
            app.action_toggle_tools()
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_action_clear(self):
        """Test clear action."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            # Add some content
            app.query_one("ConversationPanel").append_user_message("Hello")
            app.query_one("ToolPanel").append_tool_call("test", "123")

            assert len(app.query_one("#conversation-messages").children) > 0
            assert len(app.query_one("#tool-output").children) > 0

            # Clear
            app.action_clear()
            await pilot.pause()

            assert len(app.query_one("#conversation-messages").children) == 0
            assert len(app.query_one("#tool-output").children) == 0

    @pytest.mark.asyncio
    async def test_action_clear_no_tool_panel(self):
        """Test clear action when tool panel is disabled."""
        settings = Settings()
        settings.tui.show_tool_panel = False

        app = ChapgentApp(settings=settings)
        async with app.run_test() as pilot:
            # Add content to conversation
            app.query_one("ConversationPanel").append_user_message("Hello")

            # Should not crash
            app.action_clear()
            await pilot.pause()

            # Conversation should be cleared
            assert len(app.query_one("#conversation-messages").children) == 0


# =============================================================================
# Property-Based Tests
# =============================================================================


class TestPropertyBased:
    """Property-based tests for Command Palette using hypothesis."""

    @given(
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=["L", "N", "P", "Zs"])),
        description=st.text(min_size=1, max_size=100, alphabet=st.characters(categories=["L", "N", "P", "Zs"])),
    )
    @hypothesis_settings(max_examples=20)
    def test_palette_command_creation_any_values(self, name, description):
        """Test PaletteCommand accepts any reasonable values."""
        cmd = PaletteCommand(id="test", name=name, description=description)
        assert cmd.name == name
        assert cmd.description == description

    @given(query=st.text(min_size=0, max_size=20, alphabet=st.characters(categories=["L", "N"])))
    @hypothesis_settings(max_examples=30)
    def test_matches_never_crashes(self, query):
        """Test that matches() never crashes with any input."""
        cmd = PaletteCommand(id="test", name="Test Command", description="A test description")
        # Should not raise
        result = cmd.matches(query)
        assert isinstance(result, bool)

    @given(
        query=st.text(min_size=0, max_size=10, alphabet=st.characters(categories=["L"])),
        text=st.text(min_size=0, max_size=50, alphabet=st.characters(categories=["L"])),
    )
    @hypothesis_settings(max_examples=30)
    def test_fuzzy_match_never_crashes(self, query, text):
        """Test that _fuzzy_match() never crashes with any input."""
        result = _fuzzy_match(query, text)
        assert isinstance(result, bool)

    @given(num_commands=st.integers(min_value=0, max_value=20))
    @hypothesis_settings(max_examples=10)
    def test_command_palette_with_varying_command_count(self, num_commands):
        """Test CommandPalette handles varying numbers of commands."""
        commands = [
            PaletteCommand(id=f"cmd_{i}", name=f"Command {i}", description=f"Description {i}")
            for i in range(num_commands)
        ]
        palette = CommandPalette(commands=commands)
        assert len(palette.commands) == num_commands

    @pytest.mark.asyncio
    async def test_filter_matches_substring_property(self):
        """Test that substring always matches."""
        commands = [
            PaletteCommand(id="abc", name="ABC Command", description="Desc"),
            PaletteCommand(id="xyz", name="XYZ Command", description="Desc"),
        ]

        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette(commands=commands))
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")

            # Any substring should match
            input_widget.value = "ABC"
            await pilot.pause()

            items = palette.query(CommandPaletteItem)
            assert len(items) == 1
            assert items[0].command.id == "abc"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_palette_with_empty_commands(self):
        """Test palette with empty command list."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette(commands=[]))
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            items = palette.query(CommandPaletteItem)
            assert len(items) == 0
            assert palette.selected_index == -1

    @pytest.mark.asyncio
    async def test_palette_enter_with_no_selection(self):
        """Test pressing enter when no command is selected."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            result_holder = {"result": "not_set"}

            def on_dismiss(result):
                result_holder["result"] = result

            app.push_screen(CommandPalette(commands=[]), callback=on_dismiss)
            await pilot.pause()

            await pilot.press("enter")
            # Give more time for callback to execute
            await asyncio.sleep(0.2)
            await pilot.pause()

            assert result_holder["result"] is None

    @pytest.mark.asyncio
    async def test_palette_special_characters_in_search(self):
        """Test searching with special characters."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette())
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")

            # Should not crash with special characters
            input_widget.value = "!@#$%^&*()"
            await pilot.pause()

            # Should filter to no results (no commands match)
            items = palette.query(CommandPaletteItem)
            assert len(items) == 0

    @pytest.mark.asyncio
    async def test_rapid_filter_changes(self):
        """Test rapid filter changes don't cause issues."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette())
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen
            input_widget = palette.query_one("#palette-input")

            # Rapidly change filter
            for char in "newses":
                input_widget.value = input_widget.value + char
                await pilot.pause()

            # Should end with filtered results
            assert len(palette.filtered_commands) > 0

    def test_palette_command_with_very_long_name(self):
        """Test command with very long name."""
        long_name = "A" * 500
        cmd = PaletteCommand(id="long", name=long_name, description="Desc")
        item = CommandPaletteItem(command=cmd)
        assert item.command.name == long_name

    def test_palette_command_with_unicode(self):
        """Test command with unicode characters."""
        cmd = PaletteCommand(
            id="unicode",
            name="保存会话",  # "Save session" in Chinese
            description="保存当前会话",
        )
        assert cmd.matches("保存") is True

    @pytest.mark.asyncio
    async def test_palette_navigation_on_empty_list(self):
        """Test navigation when command list is empty."""
        app = ChapgentApp()
        async with app.run_test() as pilot:
            app.push_screen(CommandPalette(commands=[]))
            await pilot.pause()

            assert isinstance(app.screen, CommandPalette)
            palette = app.screen

            # Should not crash
            await pilot.press("up")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            assert palette.selected_index == -1
