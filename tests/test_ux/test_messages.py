"""Tests for UX error messages module."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pygent.ux.messages import (
    ERROR_MESSAGES,
    classify_error,
    format_error_message,
    get_error_message,
    get_suggestion_for_error,
)


class TestErrorMessages:
    """Tests for ERROR_MESSAGES constant."""

    def test_error_messages_is_dict(self) -> None:
        """ERROR_MESSAGES should be a dictionary."""
        assert isinstance(ERROR_MESSAGES, dict)

    def test_error_messages_not_empty(self) -> None:
        """ERROR_MESSAGES should contain entries."""
        assert len(ERROR_MESSAGES) > 0

    def test_error_messages_keys_are_strings(self) -> None:
        """All keys should be strings."""
        for key in ERROR_MESSAGES.keys():
            assert isinstance(key, str)

    def test_error_messages_values_are_strings(self) -> None:
        """All values should be strings."""
        for value in ERROR_MESSAGES.values():
            assert isinstance(value, str)

    def test_common_error_codes_exist(self) -> None:
        """Common error codes should exist."""
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

    def test_error_messages_have_content(self) -> None:
        """All error messages should have meaningful content."""
        for code, message in ERROR_MESSAGES.items():
            assert len(message.strip()) > 10, f"Error {code} message too short"


class TestGetErrorMessage:
    """Tests for get_error_message function."""

    def test_get_existing_message(self) -> None:
        """Should return message for existing code."""
        result = get_error_message("no_api_key")
        assert result is not None
        assert "API key" in result

    def test_get_nonexistent_message(self) -> None:
        """Should return None for nonexistent code."""
        result = get_error_message("nonexistent_error_code")
        assert result is None

    def test_get_file_not_found_message(self) -> None:
        """Should return file not found message."""
        result = get_error_message("file_not_found")
        assert result is not None
        assert "File not found" in result

    def test_get_git_not_repo_message(self) -> None:
        """Should return git not repo message."""
        result = get_error_message("git_not_repo")
        assert result is not None
        assert "git" in result.lower()


class TestFormatErrorMessage:
    """Tests for format_error_message function."""

    def test_format_with_no_placeholders(self) -> None:
        """Should work with messages that have no placeholders."""
        result = format_error_message("no_api_key")
        assert "API key" in result

    def test_format_with_path_placeholder(self) -> None:
        """Should substitute path placeholder."""
        result = format_error_message("file_not_found", path="/foo/bar.txt")
        assert "/foo/bar.txt" in result

    def test_format_with_model_placeholder(self) -> None:
        """Should substitute model placeholder."""
        result = format_error_message("model_not_found", model="gpt-5-turbo")
        assert "gpt-5-turbo" in result

    def test_format_with_timeout_placeholder(self) -> None:
        """Should substitute timeout placeholder."""
        result = format_error_message("timeout", timeout="60")
        assert "60" in result

    def test_format_nonexistent_code(self) -> None:
        """Should return generic message for unknown code."""
        result = format_error_message("totally_unknown_code")
        assert "error occurred" in result.lower()
        assert "totally_unknown_code" in result

    def test_format_with_missing_placeholder(self) -> None:
        """Should handle missing placeholder values gracefully."""
        result = format_error_message("file_not_found")
        # Should return template as-is if placeholder missing
        assert "{path}" in result or "File not found" in result

    def test_format_with_extra_kwargs(self) -> None:
        """Should ignore extra kwargs."""
        result = format_error_message("no_api_key", extra_param="ignored")
        assert "API key" in result


class TestClassifyError:
    """Tests for classify_error function."""

    def test_classify_file_not_found(self) -> None:
        """Should classify FileNotFoundError."""
        error = FileNotFoundError("/path/to/file")
        code, context = classify_error(error)
        assert code == "file_not_found"
        assert "path" in context

    def test_classify_permission_error(self) -> None:
        """Should classify PermissionError."""
        error = PermissionError("/protected/file")
        code, context = classify_error(error)
        assert code == "permission_denied"
        assert "path" in context

    def test_classify_timeout_error(self) -> None:
        """Should classify TimeoutError."""
        error = TimeoutError("Request timed out")
        code, context = classify_error(error)
        assert code == "timeout"

    def test_classify_api_key_error(self) -> None:
        """Should classify API key related errors."""
        error = Exception("No api_key found")
        code, _ = classify_error(error)
        assert code == "no_api_key"

    def test_classify_invalid_api_key_error(self) -> None:
        """Should classify invalid API key errors."""
        error = Exception("Invalid API key")
        code, _ = classify_error(error)
        assert code == "invalid_api_key"

    def test_classify_rate_limit_error(self) -> None:
        """Should classify rate limit errors."""
        error = Exception("Rate limit exceeded")
        code, _ = classify_error(error)
        assert code == "rate_limit"

    def test_classify_network_error(self) -> None:
        """Should classify network errors."""
        error = Exception("Connection error: network unreachable")
        code, _ = classify_error(error)
        assert code == "network_error"

    def test_classify_git_not_repo(self) -> None:
        """Should classify git not a repository errors."""
        error = Exception("fatal: not a git repository")
        code, _ = classify_error(error)
        assert code == "git_not_repo"

    def test_classify_unknown_error(self) -> None:
        """Should return config_invalid for unknown errors."""
        error = Exception("Some random error")
        code, context = classify_error(error)
        assert code == "config_invalid"
        assert "error" in context


class TestGetSuggestionForError:
    """Tests for get_suggestion_for_error function."""

    def test_get_suggestion_for_no_api_key(self) -> None:
        """Should return suggestion for no API key."""
        suggestion = get_suggestion_for_error("no_api_key")
        assert suggestion is not None
        assert "ANTHROPIC_API_KEY" in suggestion

    def test_get_suggestion_for_git_not_repo(self) -> None:
        """Should return suggestion for git not repo."""
        suggestion = get_suggestion_for_error("git_not_repo")
        assert suggestion is not None
        assert "git init" in suggestion

    def test_get_suggestion_for_rate_limit(self) -> None:
        """Should return suggestion for rate limit."""
        suggestion = get_suggestion_for_error("rate_limit")
        assert suggestion is not None
        assert "wait" in suggestion.lower()

    def test_get_suggestion_for_unknown_code(self) -> None:
        """Should return None for unknown code."""
        suggestion = get_suggestion_for_error("unknown_error_xyz")
        assert suggestion is None

    def test_suggestions_are_concise(self) -> None:
        """Suggestions should be concise."""
        for code in ["no_api_key", "file_not_found", "git_not_repo"]:
            suggestion = get_suggestion_for_error(code)
            if suggestion:
                assert len(suggestion) < 100, f"Suggestion for {code} too long"


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
