"""Error recovery system for intelligent error handling.

This module provides intelligent error handling with retry suggestions,
parsing common error patterns and suggesting fixes for known issues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorType(str, Enum):
    """Classification of common error types."""

    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    IS_A_DIRECTORY = "is_a_directory"
    FILE_EXISTS = "file_exists"
    NOT_A_DIRECTORY = "not_a_directory"
    GIT_NOT_A_REPOSITORY = "git_not_a_repository"
    GIT_CONFLICT = "git_conflict"
    GIT_NO_REMOTE = "git_no_remote"
    MODULE_NOT_FOUND = "module_not_found"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    SYNTAX_ERROR = "syntax_error"
    JSON_DECODE_ERROR = "json_decode_error"
    INVALID_ARGUMENT = "invalid_argument"
    UNKNOWN = "unknown"


@dataclass
class RecoveryAction:
    """Suggested recovery action for a tool error.

    Attributes:
        error_type: Classified error type.
        should_retry: Whether the tool should be retried.
        suggestions: List of suggestions for the user.
        modified_args: Modified arguments for retry (if applicable).
        similar_paths: Similar paths found (for file not found errors).
    """

    error_type: ErrorType
    should_retry: bool
    suggestions: list[str] = field(default_factory=list)
    modified_args: dict[str, Any] | None = None
    similar_paths: list[str] = field(default_factory=list)


# Error patterns with suggestions and auto_retry flags
ERROR_PATTERNS: dict[str, dict[str, Any]] = {
    "FileNotFoundError": {
        "type": ErrorType.FILE_NOT_FOUND,
        "suggest": [
            "Check if the file path is correct.",
            "Use list_files or find_files to see available files.",
            "The file may have been moved or deleted.",
        ],
        "auto_retry": False,
    },
    "PermissionError": {
        "type": ErrorType.PERMISSION_DENIED,
        "suggest": [
            "File permissions issue. Check file ownership and permissions.",
            "Try running with appropriate permissions.",
            "The file may be locked by another process.",
        ],
        "auto_retry": False,
    },
    "IsADirectoryError": {
        "type": ErrorType.IS_A_DIRECTORY,
        "suggest": [
            "The path is a directory, not a file.",
            "Use list_files to see directory contents.",
            "Specify a file path instead of a directory path.",
        ],
        "auto_retry": False,
    },
    "FileExistsError": {
        "type": ErrorType.FILE_EXISTS,
        "suggest": [
            "A file already exists at this location.",
            "Use a different filename or path.",
            "Use edit_file to modify the existing file instead.",
        ],
        "auto_retry": False,
    },
    "NotADirectoryError": {
        "type": ErrorType.NOT_A_DIRECTORY,
        "suggest": [
            "A component of the path is not a directory.",
            "Check that parent directories exist.",
        ],
        "auto_retry": False,
    },
    "GitError": {
        "type": ErrorType.GIT_NOT_A_REPOSITORY,
        "suggest": [
            "Not inside a git repository.",
            "Initialize with 'git init' or navigate to a git repository.",
            "Use git_status to verify repository state.",
        ],
        "auto_retry": False,
    },
    "TimeoutError": {
        "type": ErrorType.TIMEOUT,
        "suggest": [
            "The operation timed out.",
            "Try increasing the timeout value.",
            "The target may be slow or unresponsive.",
        ],
        "auto_retry": True,
    },
    "asyncio.TimeoutError": {
        "type": ErrorType.TIMEOUT,
        "suggest": [
            "The async operation timed out.",
            "Try increasing the timeout value.",
        ],
        "auto_retry": True,
    },
    "ConnectionError": {
        "type": ErrorType.CONNECTION_ERROR,
        "suggest": [
            "Failed to establish a connection.",
            "Check network connectivity.",
            "The target host may be down or unreachable.",
        ],
        "auto_retry": True,
    },
    "httpx.ConnectError": {
        "type": ErrorType.CONNECTION_ERROR,
        "suggest": [
            "Failed to connect to the URL.",
            "Check if the URL is correct and accessible.",
            "The server may be down or blocking requests.",
        ],
        "auto_retry": True,
    },
    "httpx.TimeoutException": {
        "type": ErrorType.TIMEOUT,
        "suggest": [
            "HTTP request timed out.",
            "Try increasing the timeout parameter.",
            "The server may be slow to respond.",
        ],
        "auto_retry": True,
    },
    "json.JSONDecodeError": {
        "type": ErrorType.JSON_DECODE_ERROR,
        "suggest": [
            "Invalid JSON format.",
            "Check that the input is valid JSON.",
            "The response may not be JSON content.",
        ],
        "auto_retry": False,
    },
    "SyntaxError": {
        "type": ErrorType.SYNTAX_ERROR,
        "suggest": [
            "Syntax error in the code or input.",
            "Check for missing brackets, quotes, or other syntax issues.",
        ],
        "auto_retry": False,
    },
    "ValueError": {
        "type": ErrorType.INVALID_ARGUMENT,
        "suggest": [
            "Invalid value provided.",
            "Check the argument requirements.",
        ],
        "auto_retry": False,
    },
    "TypeError": {
        "type": ErrorType.INVALID_ARGUMENT,
        "suggest": [
            "Incorrect type provided.",
            "Check the expected argument types.",
        ],
        "auto_retry": False,
    },
}

# Regex patterns for error message analysis
MESSAGE_PATTERNS: list[tuple[re.Pattern[str], ErrorType, list[str]]] = [
    (
        re.compile(r"No such file or directory", re.IGNORECASE),
        ErrorType.FILE_NOT_FOUND,
        ["The specified path does not exist.", "Use find_files to locate the file."],
    ),
    (
        re.compile(r"Permission denied", re.IGNORECASE),
        ErrorType.PERMISSION_DENIED,
        ["Insufficient permissions.", "Check file permissions."],
    ),
    (
        re.compile(r"not a git repository", re.IGNORECASE),
        ErrorType.GIT_NOT_A_REPOSITORY,
        ["Not inside a git repository.", "Run git init or navigate to a repo."],
    ),
    (
        re.compile(r"CONFLICT|merge conflict", re.IGNORECASE),
        ErrorType.GIT_CONFLICT,
        ["Git merge conflict detected.", "Resolve conflicts before proceeding."],
    ),
    (
        re.compile(r"No (such )?remote", re.IGNORECASE),
        ErrorType.GIT_NO_REMOTE,
        ["No remote repository configured.", "Add a remote with: git remote add origin <url>"],
    ),
    (
        re.compile(r"No module named ['\"]?(\w+)", re.IGNORECASE),
        ErrorType.MODULE_NOT_FOUND,
        ["Python module not installed.", "Install with: pip install {module}"],
    ),
    (
        re.compile(r"ModuleNotFoundError", re.IGNORECASE),
        ErrorType.MODULE_NOT_FOUND,
        ["Required module not found.", "Install missing dependencies."],
    ),
    (
        re.compile(r"timed? ?out", re.IGNORECASE),
        ErrorType.TIMEOUT,
        ["Operation timed out.", "Try again or increase timeout."],
    ),
    (
        re.compile(r"Connection (refused|reset|closed)", re.IGNORECASE),
        ErrorType.CONNECTION_ERROR,
        ["Connection failed.", "Check network and target availability."],
    ),
    (
        re.compile(r"ECONNREFUSED|ENOTFOUND|EHOSTUNREACH", re.IGNORECASE),
        ErrorType.CONNECTION_ERROR,
        ["Network connection error.", "Verify the target address."],
    ),
    (
        re.compile(r"Invalid JSON|JSON.*invalid|Expecting.*JSON", re.IGNORECASE),
        ErrorType.JSON_DECODE_ERROR,
        ["Invalid JSON data.", "Verify JSON format."],
    ),
]


class ErrorRecovery:
    """Intelligent error handling with retry suggestions.

    Analyzes errors from tool execution and provides actionable
    recovery suggestions based on known error patterns.
    """

    def __init__(self) -> None:
        """Initialize the error recovery system."""
        self._error_patterns = ERROR_PATTERNS.copy()
        self._message_patterns = MESSAGE_PATTERNS.copy()

    def handle_tool_error(
        self,
        tool_name: str,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> RecoveryAction:
        """Determine recovery action for a tool error.

        Args:
            tool_name: Name of the tool that failed.
            error: The exception that was raised.
            context: Optional context dict with tool arguments and other info.

        Returns:
            RecoveryAction with suggestions and retry flag.
        """
        context = context or {}
        error_class = type(error).__name__
        error_msg = str(error)

        # First, try to match by exception class name
        if error_class in self._error_patterns:
            pattern = self._error_patterns[error_class]
            suggestions = self._contextualize_suggestions(pattern["suggest"].copy(), tool_name, error_msg, context)
            return RecoveryAction(
                error_type=pattern["type"],
                should_retry=pattern["auto_retry"],
                suggestions=suggestions,
            )

        # Try matching parent classes
        for exc_class_name, pattern in self._error_patterns.items():
            try:
                # Check if error is instance of the exception class
                exc_class = self._resolve_exception_class(exc_class_name)
                if exc_class and isinstance(error, exc_class):
                    suggestions = self._contextualize_suggestions(
                        pattern["suggest"].copy(), tool_name, error_msg, context
                    )
                    return RecoveryAction(
                        error_type=pattern["type"],
                        should_retry=pattern["auto_retry"],
                        suggestions=suggestions,
                    )
            except (ImportError, AttributeError):
                continue

        # Try matching error message patterns
        for regex, error_type, base_suggestions in self._message_patterns:
            match = regex.search(error_msg)
            if match:
                suggestions = self._contextualize_suggestions(
                    base_suggestions.copy(), tool_name, error_msg, context, match
                )
                # Determine retry based on error type
                should_retry = error_type in (ErrorType.TIMEOUT, ErrorType.CONNECTION_ERROR)
                return RecoveryAction(
                    error_type=error_type,
                    should_retry=should_retry,
                    suggestions=suggestions,
                )

        # Unknown error - provide generic suggestions
        return RecoveryAction(
            error_type=ErrorType.UNKNOWN,
            should_retry=False,
            suggestions=[
                f"Error in {tool_name}: {error_msg}",
                "Check the tool arguments and try again.",
                "Review the error message for more details.",
            ],
        )

    def _resolve_exception_class(self, class_name: str) -> type | None:
        """Resolve exception class from string name.

        Args:
            class_name: Fully qualified or simple class name.

        Returns:
            Exception class or None if not found.
        """
        # Handle dotted names like "httpx.ConnectError"
        if "." in class_name:
            module_path, class_name_only = class_name.rsplit(".", 1)
            try:
                import importlib

                module = importlib.import_module(module_path)
                return getattr(module, class_name_only, None)
            except (ImportError, AttributeError):
                return None

        # Try builtins
        builtins_dict = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
        return builtins_dict.get(class_name)

    def _contextualize_suggestions(
        self,
        suggestions: list[str],
        tool_name: str,
        error_msg: str,
        context: dict[str, Any],
        match: re.Match[str] | None = None,
    ) -> list[str]:
        """Add context-specific information to suggestions.

        Args:
            suggestions: Base suggestion strings.
            tool_name: Name of the failed tool.
            error_msg: The error message.
            context: Tool execution context.
            match: Regex match object if pattern matched.

        Returns:
            Contextualized suggestion list.
        """
        result = []

        for suggestion in suggestions:
            # Replace placeholders
            suggestion = suggestion.replace("{tool}", tool_name)

            # Handle module placeholder from regex match
            if "{module}" in suggestion and match:
                groups = match.groups()
                if groups:
                    suggestion = suggestion.replace("{module}", groups[0])

            # Add path context if available
            if "{path}" in suggestion:
                path = context.get("path") or context.get("file_path") or context.get("paths", [""])[0]
                suggestion = suggestion.replace("{path}", str(path))

            result.append(suggestion)

        # Add tool-specific suggestions
        if tool_name.startswith("git_") and "repository" in error_msg.lower():
            if "Initialize with" not in "".join(result):
                result.append("Ensure you're in a git repository directory.")

        return result

    def add_error_pattern(
        self,
        exception_name: str,
        error_type: ErrorType,
        suggestions: list[str],
        auto_retry: bool = False,
    ) -> None:
        """Register a custom error pattern.

        Args:
            exception_name: Exception class name to match.
            error_type: Classification for this error.
            suggestions: Suggestion strings.
            auto_retry: Whether to suggest automatic retry.
        """
        self._error_patterns[exception_name] = {
            "type": error_type,
            "suggest": suggestions,
            "auto_retry": auto_retry,
        }

    def add_message_pattern(
        self,
        pattern: str,
        error_type: ErrorType,
        suggestions: list[str],
    ) -> None:
        """Register a custom message pattern.

        Args:
            pattern: Regex pattern to match in error messages.
            error_type: Classification for this error.
            suggestions: Suggestion strings.
        """
        self._message_patterns.append((re.compile(pattern, re.IGNORECASE), error_type, suggestions))
