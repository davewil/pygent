"""Tests for UX error messages module."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.ux.messages import (
    ERROR_MESSAGES,
    classify_error,
    format_error_message,
    get_error_message,
    get_suggestion_for_error,
)


class TestErrorMessagesConstant:
    """Tests for ERROR_MESSAGES constant."""

    def test_error_messages_structure(self) -> None:
        """ERROR_MESSAGES should be a dict with string keys/values and common codes."""
        assert isinstance(ERROR_MESSAGES, dict) and len(ERROR_MESSAGES) > 0
        for key, value in ERROR_MESSAGES.items():
            assert isinstance(key, str) and isinstance(value, str)
            assert len(value.strip()) > 10, f"Error {key} message too short"
        expected_codes = [
            "no_api_key",
            "invalid_api_key",
            "model_not_found",
            "rate_limit",
            "network_error",
            "file_not_found",
            "permission_denied",
            "git_not_repo",
        ]
        for code in expected_codes:
            assert code in ERROR_MESSAGES, f"Missing error code: {code}"


class TestGetErrorMessage:
    """Tests for get_error_message function."""

    @pytest.mark.parametrize(
        "code,expected_substring",
        [("no_api_key", "API key"), ("file_not_found", "File not found"), ("git_not_repo", "git")],
    )
    def test_get_existing_message(self, code: str, expected_substring: str) -> None:
        """Should return message for existing code with expected content."""
        result = get_error_message(code)
        assert result is not None and expected_substring.lower() in result.lower()

    def test_get_nonexistent_message(self) -> None:
        """Should return None for nonexistent code."""
        assert get_error_message("nonexistent_error_code") is None


class TestFormatErrorMessage:
    """Tests for format_error_message function."""

    @pytest.mark.parametrize(
        "code,kwargs,expected_in_result",
        [
            ("no_api_key", {}, "API key"),
            ("file_not_found", {"path": "/foo/bar.txt"}, "/foo/bar.txt"),
            ("model_not_found", {"model": "gpt-5-turbo"}, "gpt-5-turbo"),
            ("timeout", {"timeout": "60"}, "60"),
        ],
    )
    def test_format_with_placeholders(self, code: str, kwargs: dict, expected_in_result: str) -> None:
        """Should substitute placeholders or return template."""
        result = format_error_message(code, **kwargs)
        assert expected_in_result in result

    def test_format_nonexistent_code(self) -> None:
        """Should return generic message for unknown code."""
        result = format_error_message("totally_unknown_code")
        assert "error occurred" in result.lower() and "totally_unknown_code" in result

    def test_format_handles_missing_and_extra_kwargs(self) -> None:
        """Should handle missing placeholders and ignore extra kwargs."""
        result1 = format_error_message("file_not_found")
        assert "{path}" in result1 or "File not found" in result1
        result2 = format_error_message("no_api_key", extra_param="ignored")
        assert "API key" in result2


class TestClassifyError:
    """Tests for classify_error function."""

    @pytest.mark.parametrize(
        "error,expected_code,has_path",
        [
            (FileNotFoundError("/path/to/file"), "file_not_found", True),
            (PermissionError("/protected/file"), "permission_denied", True),
            (TimeoutError("Request timed out"), "timeout", False),
        ],
    )
    def test_classify_builtin_errors(self, error: Exception, expected_code: str, has_path: bool) -> None:
        """Should classify builtin error types."""
        code, context = classify_error(error)
        assert code == expected_code
        if has_path:
            assert "path" in context

    @pytest.mark.parametrize(
        "message,expected_code",
        [
            ("No api_key found", "no_api_key"),
            ("Invalid API key", "invalid_api_key"),
            ("Rate limit exceeded", "rate_limit"),
            ("Connection error: network unreachable", "network_error"),
            ("fatal: not a git repository", "git_not_repo"),
        ],
    )
    def test_classify_by_message(self, message: str, expected_code: str) -> None:
        """Should classify errors by message content."""
        code, _ = classify_error(Exception(message))
        assert code == expected_code

    def test_classify_unknown_error(self) -> None:
        """Should return config_invalid for unknown errors."""
        code, context = classify_error(Exception("Some random error"))
        assert code == "config_invalid" and "error" in context


class TestGetSuggestionForError:
    """Tests for get_suggestion_for_error function."""

    @pytest.mark.parametrize(
        "code,expected_substring",
        [("no_api_key", "ANTHROPIC_API_KEY"), ("git_not_repo", "git init"), ("rate_limit", "wait")],
    )
    def test_get_known_suggestions(self, code: str, expected_substring: str) -> None:
        """Should return appropriate suggestions."""
        suggestion = get_suggestion_for_error(code)
        assert suggestion is not None and expected_substring.lower() in suggestion.lower()

    def test_get_suggestion_unknown_code(self) -> None:
        """Should return None for unknown code."""
        assert get_suggestion_for_error("unknown_error_xyz") is None

    def test_suggestions_are_concise(self) -> None:
        """Suggestions should be under 100 chars."""
        for code in ["no_api_key", "file_not_found", "git_not_repo"]:
            suggestion = get_suggestion_for_error(code)
            if suggestion:
                assert len(suggestion) < 100


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_get_error_message_never_raises(self, code: str) -> None:
        """get_error_message should never raise an exception."""
        # Should not raise
        result = get_error_message(code)
        assert result is None or isinstance(result, str)

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_format_error_message_never_raises(self, code: str) -> None:
        """format_error_message should never raise an exception."""
        # Should not raise
        result = format_error_message(code)
        assert isinstance(result, str)
        assert len(result) > 0

    @given(st.text(min_size=1, max_size=100).filter(lambda x: "{" not in x and "}" not in x))
    @settings(max_examples=50)
    def test_format_with_arbitrary_kwargs(self, path: str) -> None:
        """format_error_message should handle arbitrary kwargs."""
        result = format_error_message("file_not_found", path=path)
        assert isinstance(result, str)


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_error_code(self) -> None:
        """Should handle empty error code."""
        result = get_error_message("")
        assert result is None

    def test_format_empty_code(self) -> None:
        """Should handle empty error code in format."""
        result = format_error_message("")
        assert "error occurred" in result.lower()

    def test_classify_none_message_error(self) -> None:
        """Should handle errors with None message."""
        error = Exception(None)
        code, _ = classify_error(error)
        assert isinstance(code, str)

    def test_error_messages_no_trailing_newlines_excessive(self) -> None:
        """Error messages shouldn't have excessive trailing newlines."""
        for code, message in ERROR_MESSAGES.items():
            # Allow one trailing newline but not multiple
            stripped = message.rstrip("\n")
            trailing_newlines = len(message) - len(stripped)
            assert trailing_newlines <= 1, f"Error {code} has {trailing_newlines} trailing newlines"

    def test_unicode_in_error_message(self) -> None:
        """Should handle unicode in error context."""
        result = format_error_message("file_not_found", path="/path/to/\u00e9\u00e8\u00e0.txt")
        assert "\u00e9" in result or "\\u" in result or "path" in result.lower()


class TestIntegration:
    """Integration tests."""

    def test_full_error_flow(self) -> None:
        """Test classifying an error and formatting the message."""
        # Create a file not found error
        error = FileNotFoundError("/tmp/missing.txt")

        # Classify it
        code, context = classify_error(error)

        # Format the message
        message = format_error_message(code, **context)

        # Get suggestion
        suggestion = get_suggestion_for_error(code)

        # All should work together
        assert "file" in message.lower() or "File" in message
        assert suggestion is not None

    def test_network_error_flow(self) -> None:
        """Test network error classification and messaging."""
        error = Exception("Connection refused: network timeout")

        code, context = classify_error(error)
        message = format_error_message(code, **context)

        assert "network" in message.lower() or "connect" in message.lower()
