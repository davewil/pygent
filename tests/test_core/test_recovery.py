"""Tests for the error recovery system."""

from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from chapgent.core.recovery import (
    ERROR_PATTERNS,
    MESSAGE_PATTERNS,
    ErrorRecovery,
    ErrorType,
    RecoveryAction,
)


class TestErrorType:
    """Tests for ErrorType enum."""

    @pytest.mark.parametrize(
        "error_type,expected_value",
        [
            (ErrorType.FILE_NOT_FOUND, "file_not_found"),
            (ErrorType.PERMISSION_DENIED, "permission_denied"),
            (ErrorType.GIT_NOT_A_REPOSITORY, "git_not_a_repository"),
            (ErrorType.TIMEOUT, "timeout"),
            (ErrorType.CONNECTION_ERROR, "connection_error"),
            (ErrorType.UNKNOWN, "unknown"),
        ],
    )
    def test_error_type_values(self, error_type: ErrorType, expected_value: str) -> None:
        """Test that error types have expected values."""
        assert error_type.value == expected_value
        assert isinstance(error_type, str)

    def test_all_error_types_exist(self) -> None:
        """Test all expected error types are defined."""
        expected = {
            "FILE_NOT_FOUND",
            "PERMISSION_DENIED",
            "IS_A_DIRECTORY",
            "FILE_EXISTS",
            "NOT_A_DIRECTORY",
            "GIT_NOT_A_REPOSITORY",
            "GIT_CONFLICT",
            "GIT_NO_REMOTE",
            "MODULE_NOT_FOUND",
            "TIMEOUT",
            "CONNECTION_ERROR",
            "SYNTAX_ERROR",
            "JSON_DECODE_ERROR",
            "INVALID_ARGUMENT",
            "UNKNOWN",
        }
        assert expected == {e.name for e in ErrorType}


class TestRecoveryAction:
    """Tests for RecoveryAction dataclass."""

    def test_recovery_action_defaults(self) -> None:
        """Test default values for RecoveryAction."""
        action = RecoveryAction(error_type=ErrorType.UNKNOWN, should_retry=False)
        assert (
            action.error_type,
            action.should_retry,
            action.suggestions,
            action.modified_args,
            action.similar_paths,
        ) == (ErrorType.UNKNOWN, False, [], None, [])

    def test_recovery_action_with_all_fields(self) -> None:
        """Test RecoveryAction with all optional fields."""
        action = RecoveryAction(
            error_type=ErrorType.FILE_NOT_FOUND,
            should_retry=True,
            suggestions=["Check the path.", "Use find_files."],
            modified_args={"timeout": 60},
            similar_paths=["test.py", "tests.py"],
        )
        assert len(action.suggestions) == 2 and len(action.similar_paths) == 2
        assert action.modified_args == {"timeout": 60}


class TestErrorPatterns:
    """Tests for ERROR_PATTERNS dictionary."""

    @pytest.mark.parametrize(
        "error_name,expected_type,expected_retry",
        [
            ("FileNotFoundError", ErrorType.FILE_NOT_FOUND, False),
            ("PermissionError", ErrorType.PERMISSION_DENIED, False),
            ("TimeoutError", ErrorType.TIMEOUT, True),
            ("ConnectionError", ErrorType.CONNECTION_ERROR, True),
            ("GitError", ErrorType.GIT_NOT_A_REPOSITORY, False),
        ],
    )
    def test_error_patterns(self, error_name: str, expected_type: ErrorType, expected_retry: bool) -> None:
        """Test error patterns have correct type and retry settings."""
        pattern = ERROR_PATTERNS[error_name]
        assert pattern["type"] == expected_type
        assert pattern["auto_retry"] is expected_retry
        assert len(pattern["suggest"]) >= 1

    def test_all_patterns_have_required_keys(self) -> None:
        """Test all patterns have required keys with correct types."""
        for name, pattern in ERROR_PATTERNS.items():
            assert all(key in pattern for key in ("type", "suggest", "auto_retry")), f"{name} missing keys"
            assert isinstance(pattern["type"], ErrorType)
            assert isinstance(pattern["suggest"], list) and isinstance(pattern["auto_retry"], bool)


class TestMessagePatterns:
    """Tests for MESSAGE_PATTERNS list."""

    def test_message_patterns_structure(self) -> None:
        """Test MESSAGE_PATTERNS have correct structure."""
        for pattern, error_type, suggestions in MESSAGE_PATTERNS:
            assert hasattr(pattern, "search"), "Pattern should be compiled regex"
            assert isinstance(error_type, ErrorType)
            assert isinstance(suggestions, list)
            assert len(suggestions) >= 1

    def test_file_not_found_message_pattern(self) -> None:
        """Test 'No such file' message pattern."""
        for pattern, error_type, _ in MESSAGE_PATTERNS:
            if "such file" in pattern.pattern.lower():
                match = pattern.search("No such file or directory: /tmp/test.txt")
                assert match is not None
                assert error_type == ErrorType.FILE_NOT_FOUND
                return
        pytest.fail("No 'file not found' message pattern found")

    def test_git_repository_message_pattern(self) -> None:
        """Test 'not a git repository' message pattern."""
        for pattern, error_type, _ in MESSAGE_PATTERNS:
            if "git repository" in pattern.pattern.lower():
                match = pattern.search("fatal: not a git repository (or any of the parent directories)")
                assert match is not None
                assert error_type == ErrorType.GIT_NOT_A_REPOSITORY
                return
        pytest.fail("No 'git repository' message pattern found")

    def test_timeout_message_pattern(self) -> None:
        """Test timeout message pattern."""
        for pattern, error_type, _ in MESSAGE_PATTERNS:
            if "time" in pattern.pattern.lower() and "out" in pattern.pattern.lower():
                match = pattern.search("Operation timed out after 30 seconds")
                assert match is not None
                assert error_type == ErrorType.TIMEOUT
                return
        pytest.fail("No 'timeout' message pattern found")


class TestErrorRecovery:
    """Tests for ErrorRecovery class."""

    @pytest.fixture
    def recovery(self) -> ErrorRecovery:
        """Create ErrorRecovery instance."""
        return ErrorRecovery()

    @pytest.mark.parametrize(
        "error_class,error_msg,tool_name,expected_type,expected_retry",
        [
            (FileNotFoundError, "File not found: /tmp/test.txt", "read_file", ErrorType.FILE_NOT_FOUND, False),
            (PermissionError, "Permission denied: /etc/passwd", "edit_file", ErrorType.PERMISSION_DENIED, False),
            (IsADirectoryError, "Is a directory: /tmp", "read_file", ErrorType.IS_A_DIRECTORY, False),
            (FileExistsError, "File already exists: /tmp/test.txt", "create_file", ErrorType.FILE_EXISTS, False),
            (TimeoutError, "Operation timed out", "shell", ErrorType.TIMEOUT, True),
            (ConnectionError, "Connection refused", "web_fetch", ErrorType.CONNECTION_ERROR, True),
            (ValueError, "Invalid value provided", "some_tool", ErrorType.INVALID_ARGUMENT, False),
            (TypeError, "Expected str, got int", "some_tool", ErrorType.INVALID_ARGUMENT, False),
        ],
    )
    def test_handle_builtin_errors(
        self,
        recovery: ErrorRecovery,
        error_class: type,
        error_msg: str,
        tool_name: str,
        expected_type: ErrorType,
        expected_retry: bool,
    ) -> None:
        """Test handling of builtin error types."""
        error = error_class(error_msg)
        action = recovery.handle_tool_error(tool_name, error)
        assert action.error_type == expected_type
        assert action.should_retry is expected_retry
        assert len(action.suggestions) >= 1

    def test_handle_json_decode_error(self, recovery: ErrorRecovery) -> None:
        """Test handling json.JSONDecodeError (subclass of ValueError)."""
        error = json.JSONDecodeError("Invalid JSON", "{invalid", 0)
        action = recovery.handle_tool_error("web_fetch", error)
        assert action.error_type in (ErrorType.JSON_DECODE_ERROR, ErrorType.INVALID_ARGUMENT)

    def test_handle_unknown_error(self, recovery: ErrorRecovery) -> None:
        """Test handling unknown error type includes tool name."""

        class CustomError(Exception):
            pass

        error = CustomError("Something went wrong")
        action = recovery.handle_tool_error("custom_tool", error)
        assert action.error_type == ErrorType.UNKNOWN and "custom_tool" in action.suggestions[0]

    @pytest.mark.parametrize(
        "error_msg,expected_type",
        [
            ("fatal: not a git repository", ErrorType.GIT_NOT_A_REPOSITORY),
            ("No module named 'requests'", ErrorType.MODULE_NOT_FOUND),
            ("Connection refused by host", ErrorType.CONNECTION_ERROR),
        ],
    )
    def test_message_pattern_matching(self, recovery: ErrorRecovery, error_msg: str, expected_type: ErrorType) -> None:
        """Test message pattern matching for various error messages."""

        class GenericError(Exception):
            pass

        error = GenericError(error_msg)
        action = recovery.handle_tool_error("test_tool", error)
        assert action.error_type == expected_type


class TestErrorRecoveryCustomPatterns:
    """Tests for custom error pattern registration."""

    @pytest.fixture
    def recovery(self) -> ErrorRecovery:
        """Create ErrorRecovery instance."""
        return ErrorRecovery()

    def test_add_error_and_message_patterns(self, recovery: ErrorRecovery) -> None:
        """Test adding custom error and message patterns."""
        # Add error pattern
        recovery.add_error_pattern(
            "CustomDatabaseError", ErrorType.UNKNOWN, ["Database connection failed."], auto_retry=True
        )

        class CustomDatabaseError(Exception):
            pass

        action = recovery.handle_tool_error("db_query", CustomDatabaseError("timeout"))
        assert "Database" in action.suggestions[0]

        # Add message pattern
        recovery.add_message_pattern(r"rate limit exceeded", ErrorType.TIMEOUT, ["Rate limited."])

        class APIError(Exception):
            pass

        action = recovery.handle_tool_error("api_call", APIError("Error 429: rate limit exceeded"))
        assert action.error_type == ErrorType.TIMEOUT

    def test_class_based_pattern_priority_over_message(self, recovery: ErrorRecovery) -> None:
        """Test class-based patterns have priority over message patterns."""
        recovery.add_message_pattern(r"special error", ErrorType.CONNECTION_ERROR, ["Special."])
        error = FileNotFoundError("special error in file")
        action = recovery.handle_tool_error("read_file", error)
        assert action.error_type == ErrorType.FILE_NOT_FOUND  # Class wins

    def test_module_placeholder_replacement(self, recovery: ErrorRecovery) -> None:
        """Test module placeholder is replaced in suggestions."""

        class ModuleError(Exception):
            pass

        error = ModuleError("No module named 'pandas'")
        action = recovery.handle_tool_error("shell", error)
        assert action.error_type == ErrorType.MODULE_NOT_FOUND
        suggestions_text = " ".join(action.suggestions).lower()
        assert "pandas" in suggestions_text or "module" in suggestions_text


class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @settings(max_examples=50)
    @given(tool_name=st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,49}", fullmatch=True))
    def test_unknown_error_always_returns_action(self, tool_name: str) -> None:
        """Test that unknown errors always return a RecoveryAction."""
        recovery = ErrorRecovery()

        class RandomError(Exception):
            pass

        error = RandomError("random error")
        action = recovery.handle_tool_error(tool_name, error)

        assert isinstance(action, RecoveryAction)
        assert isinstance(action.error_type, ErrorType)
        assert isinstance(action.should_retry, bool)
        assert isinstance(action.suggestions, list)

    @settings(max_examples=50)
    @given(error_msg=st.text(min_size=1, max_size=200))
    def test_error_message_handling(self, error_msg: str) -> None:
        """Test that any error message is handled gracefully."""
        recovery = ErrorRecovery()

        error = Exception(error_msg)
        action = recovery.handle_tool_error("test_tool", error)

        assert isinstance(action, RecoveryAction)
        assert len(action.suggestions) >= 1

    @settings(max_examples=30)
    @given(
        st.sampled_from(list(ERROR_PATTERNS.keys())).filter(
            lambda x: "." not in x  # Skip dotted names that need imports
        )
    )
    def test_all_builtin_patterns_match(self, pattern_name: str) -> None:
        """Test that builtin exception patterns are recognized."""
        recovery = ErrorRecovery()

        # Create exception instance
        builtins_dict = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
        exc_class = builtins_dict.get(pattern_name)
        if exc_class is None:
            pytest.skip(f"Exception {pattern_name} not found in builtins")

        try:
            error = exc_class("test error")
        except TypeError:
            # Some exceptions require specific args
            pytest.skip(f"Cannot instantiate {pattern_name}")

        action = recovery.handle_tool_error("test_tool", error)

        expected_type = ERROR_PATTERNS[pattern_name]["type"]
        assert action.error_type == expected_type


class TestIntegration:
    """Integration tests for error recovery in tool execution context."""

    @pytest.fixture
    def recovery(self) -> ErrorRecovery:
        """Create ErrorRecovery instance."""
        return ErrorRecovery()

    def test_filesystem_error_flow(self, recovery: ErrorRecovery) -> None:
        """Test error recovery flow for filesystem operations."""
        # Simulate read_file error
        error = FileNotFoundError("No such file: /home/user/project/missing.py")
        context = {"path": "/home/user/project/missing.py"}

        action = recovery.handle_tool_error("read_file", error, context)

        assert action.error_type == ErrorType.FILE_NOT_FOUND
        assert action.should_retry is False
        assert any("find_files" in s or "list_files" in s for s in action.suggestions)

    def test_git_error_flow(self, recovery: ErrorRecovery) -> None:
        """Test error recovery flow for git operations."""
        # Import GitError for testing
        from chapgent.tools.git import GitError

        error = GitError("Not a git repository (or any parent up to mount point)")
        action = recovery.handle_tool_error("git_commit", error)

        assert action.error_type == ErrorType.GIT_NOT_A_REPOSITORY
        assert action.should_retry is False
        suggestions_text = " ".join(action.suggestions).lower()
        assert "git" in suggestions_text

    def test_web_timeout_flow(self, recovery: ErrorRecovery) -> None:
        """Test error recovery flow for web timeouts."""
        error = TimeoutError("Request timed out after 30 seconds")
        context = {"url": "https://example.com/api", "timeout": 30}

        action = recovery.handle_tool_error("web_fetch", error, context)

        assert action.error_type == ErrorType.TIMEOUT
        assert action.should_retry is True
        assert any("timeout" in s.lower() for s in action.suggestions)

    def test_shell_module_not_found_flow(self, recovery: ErrorRecovery) -> None:
        """Test error recovery for missing Python module in shell."""

        class ShellError(Exception):
            pass

        error = ShellError("ModuleNotFoundError: No module named 'nonexistent_module'")
        action = recovery.handle_tool_error("shell", error)

        assert action.error_type == ErrorType.MODULE_NOT_FOUND
        suggestions_text = " ".join(action.suggestions).lower()
        assert "module" in suggestions_text or "install" in suggestions_text
