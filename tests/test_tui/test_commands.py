"""Tests for the tui/commands.py module."""

from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.tui.commands import (
    SLASH_COMMANDS,
    SlashCommand,
    format_command_list,
    get_command_help,
    get_slash_command,
    list_slash_commands,
    parse_slash_command,
)


class TestSlashCommand:
    """Tests for SlashCommand dataclass."""

    def test_create_with_defaults(self) -> None:
        """Test creating a SlashCommand with default values."""
        cmd = SlashCommand(name="test")
        assert cmd.name == "test"
        assert cmd.aliases == []
        assert cmd.description == ""
        assert cmd.action == ""
        assert cmd.args_pattern is None

    def test_create_with_all_fields(self) -> None:
        """Test creating a SlashCommand with all fields."""
        cmd = SlashCommand(
            name="test",
            aliases=["t", "tst"],
            description="Test command",
            action="do_test",
            args_pattern="[arg]",
        )
        assert cmd.name == "test"
        assert cmd.aliases == ["t", "tst"]
        assert cmd.description == "Test command"
        assert cmd.action == "do_test"
        assert cmd.args_pattern == "[arg]"

    def test_matches_name(self) -> None:
        """Test matching by name."""
        cmd = SlashCommand(name="test")
        assert cmd.matches("test") is True
        assert cmd.matches("other") is False

    def test_matches_case_insensitive(self) -> None:
        """Test matching is case-insensitive."""
        cmd = SlashCommand(name="test")
        assert cmd.matches("TEST") is True
        assert cmd.matches("Test") is True

    def test_matches_alias(self) -> None:
        """Test matching by alias."""
        cmd = SlashCommand(name="test", aliases=["t", "tst"])
        assert cmd.matches("t") is True
        assert cmd.matches("tst") is True
        assert cmd.matches("other") is False

    def test_matches_alias_case_insensitive(self) -> None:
        """Test alias matching is case-insensitive."""
        cmd = SlashCommand(name="test", aliases=["ABC"])
        assert cmd.matches("abc") is True
        assert cmd.matches("ABC") is True


class TestSlashCommandsConstant:
    """Tests for SLASH_COMMANDS constant."""

    def test_is_list(self) -> None:
        """Test that SLASH_COMMANDS is a list."""
        assert isinstance(SLASH_COMMANDS, list)

    def test_contains_help_command(self) -> None:
        """Test that help command is present."""
        help_cmd = next((c for c in SLASH_COMMANDS if c.name == "help"), None)
        assert help_cmd is not None
        assert "h" in help_cmd.aliases
        assert "?" in help_cmd.aliases

    def test_contains_config_command(self) -> None:
        """Test that config command is present."""
        config_cmd = next((c for c in SLASH_COMMANDS if c.name == "config"), None)
        assert config_cmd is not None
        assert "cfg" in config_cmd.aliases

    def test_contains_session_commands(self) -> None:
        """Test that session commands are present."""
        new_cmd = next((c for c in SLASH_COMMANDS if c.name == "new"), None)
        save_cmd = next((c for c in SLASH_COMMANDS if c.name == "save"), None)
        assert new_cmd is not None
        assert save_cmd is not None

    def test_contains_ui_toggle_commands(self) -> None:
        """Test that UI toggle commands are present."""
        sidebar_cmd = next((c for c in SLASH_COMMANDS if c.name == "sidebar"), None)
        toolpanel_cmd = next((c for c in SLASH_COMMANDS if c.name == "toolpanel"), None)
        assert sidebar_cmd is not None
        assert toolpanel_cmd is not None

    def test_all_commands_have_names(self) -> None:
        """Test that all commands have non-empty names."""
        for cmd in SLASH_COMMANDS:
            assert cmd.name, f"Command has empty name: {cmd}"

    def test_all_commands_have_actions(self) -> None:
        """Test that all commands have non-empty actions."""
        for cmd in SLASH_COMMANDS:
            assert cmd.action, f"Command {cmd.name} has empty action"


class TestGetSlashCommand:
    """Tests for get_slash_command function."""

    def test_finds_by_name(self) -> None:
        """Test finding command by name."""
        cmd = get_slash_command("help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_finds_by_alias(self) -> None:
        """Test finding command by alias."""
        cmd = get_slash_command("h")
        assert cmd is not None
        assert cmd.name == "help"

    def test_case_insensitive(self) -> None:
        """Test case-insensitive lookup."""
        cmd = get_slash_command("HELP")
        assert cmd is not None
        assert cmd.name == "help"

    def test_returns_none_for_unknown(self) -> None:
        """Test that unknown command returns None."""
        cmd = get_slash_command("unknown_command_xyz")
        assert cmd is None


class TestParseSlashCommand:
    """Tests for parse_slash_command function."""

    def test_parses_simple_command(self) -> None:
        """Test parsing a simple command without arguments."""
        cmd, args = parse_slash_command("/help")
        assert cmd is not None
        assert cmd.name == "help"
        assert args == []

    def test_parses_command_with_one_arg(self) -> None:
        """Test parsing a command with one argument."""
        cmd, args = parse_slash_command("/help tools")
        assert cmd is not None
        assert cmd.name == "help"
        assert args == ["tools"]

    def test_parses_command_with_multiple_args(self) -> None:
        """Test parsing a command with multiple arguments."""
        cmd, args = parse_slash_command("/config set llm.model gpt-4")
        assert cmd is not None
        assert cmd.name == "config"
        assert args == ["set", "llm.model", "gpt-4"]

    def test_parses_alias(self) -> None:
        """Test parsing by alias."""
        cmd, args = parse_slash_command("/h")
        assert cmd is not None
        assert cmd.name == "help"

    def test_returns_none_for_non_slash_input(self) -> None:
        """Test that non-slash input returns None."""
        cmd, args = parse_slash_command("hello world")
        assert cmd is None
        assert args == []

    def test_returns_none_for_unknown_command(self) -> None:
        """Test that unknown command returns None."""
        cmd, args = parse_slash_command("/unknown_xyz")
        assert cmd is None
        assert args == []

    def test_handles_leading_whitespace(self) -> None:
        """Test handling leading whitespace."""
        cmd, args = parse_slash_command("  /help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_handles_empty_input(self) -> None:
        """Test handling empty input."""
        cmd, args = parse_slash_command("")
        assert cmd is None
        assert args == []

    def test_handles_slash_only(self) -> None:
        """Test handling '/' only."""
        cmd, args = parse_slash_command("/")
        assert cmd is None
        assert args == []


class TestListSlashCommands:
    """Tests for list_slash_commands function."""

    def test_returns_list_of_tuples(self) -> None:
        """Test that function returns list of tuples."""
        result = list_slash_commands()
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)

    def test_tuple_structure(self) -> None:
        """Test that each tuple has (name, description, args_pattern)."""
        result = list_slash_commands()
        for item in result:
            assert len(item) == 3
            name, desc, pattern = item
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert pattern is None or isinstance(pattern, str)

    def test_includes_all_commands(self) -> None:
        """Test that all commands are included."""
        result = list_slash_commands()
        names = [name for name, _, _ in result]
        for cmd in SLASH_COMMANDS:
            assert cmd.name in names


class TestGetCommandHelp:
    """Tests for get_command_help function."""

    def test_returns_help_for_valid_command(self) -> None:
        """Test that help is returned for valid command."""
        help_text = get_command_help("help")
        assert help_text is not None
        assert "/help" in help_text

    def test_includes_description(self) -> None:
        """Test that help includes description."""
        help_text = get_command_help("new")
        assert help_text is not None
        assert "session" in help_text.lower()

    def test_includes_aliases(self) -> None:
        """Test that help includes aliases."""
        help_text = get_command_help("help")
        assert help_text is not None
        assert "/h" in help_text or "Aliases" in help_text

    def test_includes_args_pattern(self) -> None:
        """Test that help includes args pattern."""
        help_text = get_command_help("help")
        assert help_text is not None
        assert "[topic]" in help_text

    def test_returns_none_for_unknown(self) -> None:
        """Test that unknown command returns None."""
        help_text = get_command_help("unknown_xyz")
        assert help_text is None


class TestFormatCommandList:
    """Tests for format_command_list function."""

    def test_returns_string(self) -> None:
        """Test that function returns a string."""
        result = format_command_list()
        assert isinstance(result, str)

    def test_includes_header(self) -> None:
        """Test that result includes header."""
        result = format_command_list()
        assert "Available" in result or "Commands" in result

    def test_includes_all_commands(self) -> None:
        """Test that all commands are listed."""
        result = format_command_list()
        for cmd in SLASH_COMMANDS:
            assert f"/{cmd.name}" in result

    def test_includes_descriptions(self) -> None:
        """Test that descriptions are included."""
        result = format_command_list()
        for cmd in SLASH_COMMANDS:
            if cmd.description:
                # At least part of the description should be present
                words = cmd.description.split()
                if words:
                    assert any(word in result for word in words[:3])


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=["L", "Nd"])))
    @settings(max_examples=20)
    def test_slash_command_matches_self(self, name: str) -> None:
        """Test that a SlashCommand always matches its own name."""
        cmd = SlashCommand(name=name)
        assert cmd.matches(name) is True

    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=["L", "Nd"])),
        st.lists(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=["L", "Nd"])),
            max_size=3,
        ),
    )
    @settings(max_examples=20)
    def test_slash_command_matches_aliases(self, name: str, aliases: list[str]) -> None:
        """Test that a SlashCommand matches all its aliases."""
        cmd = SlashCommand(name=name, aliases=aliases)
        for alias in aliases:
            assert cmd.matches(alias) is True

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=20)
    def test_parse_never_crashes(self, user_input: str) -> None:
        """Test that parse_slash_command never crashes."""
        # Should not raise any exception
        result = parse_slash_command(user_input)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_name_slash_command(self) -> None:
        """Test SlashCommand with empty name."""
        cmd = SlashCommand(name="")
        assert cmd.matches("") is True

    def test_slash_command_with_special_chars_in_name(self) -> None:
        """Test SlashCommand with special characters."""
        cmd = SlashCommand(name="test-cmd")
        assert cmd.matches("test-cmd") is True

    def test_parse_command_with_extra_whitespace(self) -> None:
        """Test parsing command with extra whitespace."""
        cmd, args = parse_slash_command("/help   tools   ")
        assert cmd is not None
        assert args == ["tools"]  # Extra whitespace in args should be stripped

    def test_parse_command_with_tabs(self) -> None:
        """Test parsing command with tabs."""
        cmd, args = parse_slash_command("/help\ttools")
        assert cmd is not None
        assert "tools" in args

    def test_unicode_in_arguments(self) -> None:
        """Test unicode characters in arguments."""
        cmd, args = parse_slash_command("/help 日本語")
        assert cmd is not None
        assert "日本語" in args


class TestIntegration:
    """Integration tests."""

    def test_parse_and_lookup_workflow(self) -> None:
        """Test the full parse-and-lookup workflow."""
        # Parse a command
        cmd, args = parse_slash_command("/help tools")

        # Verify parsing worked
        assert cmd is not None
        assert cmd.name == "help"
        assert args == ["tools"]

        # Look up the same command
        looked_up = get_slash_command("help")
        assert looked_up == cmd

    def test_all_commands_can_be_parsed(self) -> None:
        """Test that all registered commands can be parsed."""
        for cmd in SLASH_COMMANDS:
            parsed, args = parse_slash_command(f"/{cmd.name}")
            assert parsed is not None
            assert parsed.name == cmd.name

            # Also test aliases
            for alias in cmd.aliases:
                parsed, args = parse_slash_command(f"/{alias}")
                assert parsed is not None
                assert parsed.name == cmd.name
