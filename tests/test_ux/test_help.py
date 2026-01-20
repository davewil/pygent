"""Tests for UX help system module."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.ux.help import (
    HELP_TOPICS,
    HelpTopic,
    format_help_topic,
    get_help_topic,
    get_topic_names,
    list_help_topics,
    search_help,
)


class TestHelpTopicAndConstants:
    """Tests for HelpTopic dataclass and HELP_TOPICS constant."""

    def test_help_topic_creation(self) -> None:
        """Should create HelpTopic with all required fields."""
        topic = HelpTopic(name="test", title="Test Topic", summary="A test", content="Content")
        assert (topic.name, topic.title, topic.summary, topic.content) == ("test", "Test Topic", "A test", "Content")

    def test_help_topics_structure(self) -> None:
        """HELP_TOPICS should be dict with HelpTopic values and required topics."""
        assert isinstance(HELP_TOPICS, dict) and len(HELP_TOPICS) > 0
        for key, topic in HELP_TOPICS.items():
            assert isinstance(topic, HelpTopic) and topic.name == key
            assert len(topic.content.strip()) > 50 and len(topic.title.strip()) > 0
        for required in ["tools", "config", "shortcuts", "permissions"]:
            assert required in HELP_TOPICS


class TestGetHelpTopic:
    """Tests for get_help_topic function."""

    @pytest.mark.parametrize(
        "name,expected_content_keyword",
        [
            ("tools", None),
            ("config", "config"),
            ("shortcuts", "key"),
            ("permissions", "permission"),
        ],
    )
    def test_get_topic_by_name(self, name: str, expected_content_keyword: str | None) -> None:
        """Should return topic and content for known topics."""
        topic = get_help_topic(name)
        assert topic is not None and topic.name == name
        if expected_content_keyword:
            assert expected_content_keyword in topic.content.lower()

    def test_get_nonexistent_topic(self) -> None:
        """Should return None for nonexistent name."""
        assert get_help_topic("nonexistent_topic") is None

    def test_get_topic_case_insensitive(self) -> None:
        """Should handle case-insensitive lookup."""
        assert get_help_topic("TOOLS") == get_help_topic("Tools") == get_help_topic("tools")


class TestListHelpTopics:
    """Tests for list_help_topics function."""

    def test_list_structure(self) -> None:
        """Should return non-empty list of (name, summary) tuples matching topics."""
        result = list_help_topics()
        assert isinstance(result, list) and len(result) > 0
        for name, summary in result:
            assert isinstance(name, str) and isinstance(summary, str)
            topic = get_help_topic(name)
            assert topic is not None and topic.summary == summary


class TestSearchHelp:
    """Tests for search_help function."""

    def test_search_behavior(self) -> None:
        """Test search returns list, finds matches, is case-insensitive."""
        assert isinstance(search_help("git"), list)
        result = search_help("keyboard")
        assert len(result) > 0 and "shortcuts" in [t.name for t in result]
        assert set(t.name for t in search_help("GIT")) == set(t.name for t in search_help("git"))

    def test_search_edge_cases(self) -> None:
        """Empty query returns all, nonexistent returns empty."""
        assert len(search_help("")) == len(HELP_TOPICS)
        assert search_help("xyznonexistentqueryzyx") == []


class TestFormatHelpTopic:
    """Tests for format_help_topic function."""

    def test_format_includes_content_and_decorations(self) -> None:
        """Formatted output should include title, content, and decorations."""
        topic = get_help_topic("tools")
        assert topic is not None
        result = format_help_topic(topic)
        assert isinstance(result, str) and topic.title in result and topic.content in result
        assert "=" in result or "-" in result

    def test_format_custom_width(self) -> None:
        """Should respect custom width parameter."""
        topic = HelpTopic(name="test", title="Test", summary="Sum", content="Content")
        assert "=" * 40 in format_help_topic(topic, width=40)


class TestGetTopicNames:
    """Tests for get_topic_names function."""

    def test_returns_sorted_list_with_expected(self) -> None:
        """Should return sorted list with expected topics."""
        result = get_topic_names()
        assert isinstance(result, list) and result == sorted(result)
        for expected in ["tools", "config", "shortcuts"]:
            assert expected in result


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
