"""Tests for UX help system module."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pygent.ux.help import (
    HELP_TOPICS,
    HelpTopic,
    format_help_topic,
    get_help_topic,
    get_topic_names,
    list_help_topics,
    search_help,
)


class TestHelpTopic:
    """Tests for HelpTopic dataclass."""

    def test_create_help_topic(self) -> None:
        """Should create a HelpTopic."""
        topic = HelpTopic(
            name="test",
            title="Test Topic",
            summary="A test topic",
            content="Detailed content here.",
        )
        assert topic.name == "test"
        assert topic.title == "Test Topic"
        assert topic.summary == "A test topic"
        assert topic.content == "Detailed content here."

    def test_help_topic_fields(self) -> None:
        """HelpTopic should have all required fields."""
        topic = HelpTopic(name="a", title="b", summary="c", content="d")
        assert hasattr(topic, "name")
        assert hasattr(topic, "title")
        assert hasattr(topic, "summary")
        assert hasattr(topic, "content")


class TestHelpTopics:
    """Tests for HELP_TOPICS constant."""

    def test_help_topics_is_dict(self) -> None:
        """HELP_TOPICS should be a dictionary."""
        assert isinstance(HELP_TOPICS, dict)

    def test_help_topics_not_empty(self) -> None:
        """HELP_TOPICS should contain entries."""
        assert len(HELP_TOPICS) > 0

    def test_required_topics_exist(self) -> None:
        """Required help topics should exist."""
        required = ["tools", "config", "shortcuts", "permissions"]
        for topic in required:
            assert topic in HELP_TOPICS, f"Missing required topic: {topic}"

    def test_all_topics_are_help_topic_instances(self) -> None:
        """All values should be HelpTopic instances."""
        for name, topic in HELP_TOPICS.items():
            assert isinstance(topic, HelpTopic), f"Topic {name} is not a HelpTopic"

    def test_topic_names_match_keys(self) -> None:
        """Topic names should match dictionary keys."""
        for key, topic in HELP_TOPICS.items():
            assert topic.name == key, f"Topic {key} has mismatched name: {topic.name}"

    def test_all_topics_have_content(self) -> None:
        """All topics should have meaningful content."""
        for name, topic in HELP_TOPICS.items():
            assert len(topic.content.strip()) > 50, f"Topic {name} content too short"
            assert len(topic.title.strip()) > 0, f"Topic {name} has empty title"
            assert len(topic.summary.strip()) > 0, f"Topic {name} has empty summary"


class TestGetHelpTopic:
    """Tests for get_help_topic function."""

    def test_get_existing_topic(self) -> None:
        """Should return topic for existing name."""
        topic = get_help_topic("tools")
        assert topic is not None
        assert topic.name == "tools"

    def test_get_nonexistent_topic(self) -> None:
        """Should return None for nonexistent name."""
        topic = get_help_topic("nonexistent_topic")
        assert topic is None

    def test_get_topic_case_insensitive(self) -> None:
        """Should handle case-insensitive lookup."""
        topic1 = get_help_topic("TOOLS")
        topic2 = get_help_topic("Tools")
        topic3 = get_help_topic("tools")
        # All should return same topic (lowercase lookup)
        assert topic1 == topic2 == topic3

    def test_get_config_topic(self) -> None:
        """Should return config topic."""
        topic = get_help_topic("config")
        assert topic is not None
        assert "configuration" in topic.content.lower() or "config" in topic.content.lower()

    def test_get_shortcuts_topic(self) -> None:
        """Should return shortcuts topic."""
        topic = get_help_topic("shortcuts")
        assert topic is not None
        assert "ctrl" in topic.content.lower() or "key" in topic.content.lower()

    def test_get_permissions_topic(self) -> None:
        """Should return permissions topic."""
        topic = get_help_topic("permissions")
        assert topic is not None
        assert "permission" in topic.content.lower() or "risk" in topic.content.lower()


class TestListHelpTopics:
    """Tests for list_help_topics function."""

    def test_list_returns_list(self) -> None:
        """Should return a list."""
        result = list_help_topics()
        assert isinstance(result, list)

    def test_list_not_empty(self) -> None:
        """Should return non-empty list."""
        result = list_help_topics()
        assert len(result) > 0

    def test_list_contains_tuples(self) -> None:
        """Should return list of tuples."""
        result = list_help_topics()
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_list_tuples_are_name_summary(self) -> None:
        """Tuples should be (name, summary)."""
        result = list_help_topics()
        for name, summary in result:
            assert isinstance(name, str)
            assert isinstance(summary, str)
            # Verify it matches actual topic
            topic = get_help_topic(name)
            assert topic is not None
            assert topic.summary == summary


class TestSearchHelp:
    """Tests for search_help function."""

    def test_search_returns_list(self) -> None:
        """Should return a list."""
        result = search_help("git")
        assert isinstance(result, list)

    def test_search_finds_matching_topics(self) -> None:
        """Should find topics containing the query."""
        result = search_help("keyboard")
        assert len(result) > 0
        # shortcuts topic should mention keyboard
        names = [t.name for t in result]
        assert "shortcuts" in names

    def test_search_case_insensitive(self) -> None:
        """Search should be case-insensitive."""
        result1 = search_help("GIT")
        result2 = search_help("git")
        result3 = search_help("Git")
        # All should find same results
        assert set(t.name for t in result1) == set(t.name for t in result2)
        assert set(t.name for t in result2) == set(t.name for t in result3)

    def test_search_empty_query(self) -> None:
        """Empty query should return all topics."""
        result = search_help("")
        assert len(result) == len(HELP_TOPICS)

    def test_search_no_results(self) -> None:
        """Should return empty list for no matches."""
        result = search_help("xyznonexistentqueryzyx")
        assert result == []


class TestFormatHelpTopic:
    """Tests for format_help_topic function."""

    def test_format_returns_string(self) -> None:
        """Should return a string."""
        topic = get_help_topic("tools")
        assert topic is not None
        result = format_help_topic(topic)
        assert isinstance(result, str)

    def test_format_includes_title(self) -> None:
        """Formatted output should include title."""
        topic = get_help_topic("tools")
        assert topic is not None
        result = format_help_topic(topic)
        assert topic.title in result

    def test_format_includes_content(self) -> None:
        """Formatted output should include content."""
        topic = get_help_topic("tools")
        assert topic is not None
        result = format_help_topic(topic)
        assert topic.content in result

    def test_format_includes_decorations(self) -> None:
        """Formatted output should include visual decorations."""
        topic = get_help_topic("tools")
        assert topic is not None
        result = format_help_topic(topic)
        # Should have separators
        assert "=" in result or "-" in result

    def test_format_custom_width(self) -> None:
        """Should respect custom width parameter."""
        topic = HelpTopic(name="test", title="Test", summary="Sum", content="Content")
        result = format_help_topic(topic, width=40)
        # Separator should be 40 chars
        assert "=" * 40 in result


class TestGetTopicNames:
    """Tests for get_topic_names function."""

    def test_returns_list(self) -> None:
        """Should return a list."""
        result = get_topic_names()
        assert isinstance(result, list)

    def test_returns_sorted(self) -> None:
        """Should return sorted list."""
        result = get_topic_names()
        assert result == sorted(result)

    def test_contains_expected_topics(self) -> None:
        """Should contain expected topic names."""
        result = get_topic_names()
        assert "tools" in result
        assert "config" in result
        assert "shortcuts" in result


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_get_help_topic_never_raises(self, name: str) -> None:
        """get_help_topic should never raise an exception."""
        result = get_help_topic(name)
        assert result is None or isinstance(result, HelpTopic)

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50)
    def test_search_help_never_raises(self, query: str) -> None:
        """search_help should never raise an exception."""
        result = search_help(query)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, HelpTopic)

    @given(st.integers(min_value=20, max_value=200))
    @settings(max_examples=20)
    def test_format_with_various_widths(self, width: int) -> None:
        """format_help_topic should work with various widths."""
        topic = HelpTopic(name="t", title="Title", summary="Sum", content="Content")
        result = format_help_topic(topic, width=width)
        assert isinstance(result, str)
        assert len(result) > 0


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_topic_name(self) -> None:
        """Should handle empty topic name."""
        result = get_help_topic("")
        assert result is None

    def test_whitespace_topic_name(self) -> None:
        """Should handle whitespace topic name."""
        result = get_help_topic("   ")
        assert result is None

    def test_special_characters_in_search(self) -> None:
        """Should handle special characters in search."""
        result = search_help("$@#!")
        assert isinstance(result, list)

    def test_unicode_in_search(self) -> None:
        """Should handle unicode in search."""
        result = search_help("\u00e9\u00e8\u00e0")
        assert isinstance(result, list)

    def test_very_long_search_query(self) -> None:
        """Should handle very long search query."""
        result = search_help("a" * 1000)
        assert isinstance(result, list)


class TestIntegration:
    """Integration tests."""

    def test_list_then_get_topics(self) -> None:
        """Should be able to list topics then get each one."""
        topics = list_help_topics()
        for name, _ in topics:
            topic = get_help_topic(name)
            assert topic is not None, f"Could not get topic: {name}"

    def test_search_then_format(self) -> None:
        """Should be able to search and format results."""
        results = search_help("tools")
        assert len(results) > 0

        for topic in results:
            formatted = format_help_topic(topic)
            assert topic.title in formatted

    def test_all_topics_have_valid_content(self) -> None:
        """All topics should have valid, useful content."""
        for name in get_topic_names():
            topic = get_help_topic(name)
            assert topic is not None

            # Content should have multiple lines
            lines = topic.content.strip().split("\n")
            assert len(lines) > 5, f"Topic {name} has too few lines"

            # Content should have some sections or structure
            assert any(line.isupper() or line.startswith("  ") for line in lines), f"Topic {name} lacks structure"
