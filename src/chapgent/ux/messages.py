"""Friendly error messages for common errors.

This module provides user-friendly error messages that help users
understand what went wrong and how to fix it.
"""

from __future__ import annotations

from typing import Any

# Error message templates with placeholders
ERROR_MESSAGES: dict[str, str] = {
    "no_api_key": """No API key configured.

Set your API key in one of these ways:
1. Environment variable: export ANTHROPIC_API_KEY=your-key
2. Config file: chapgent config set llm.api_key your-key

Get an API key at: https://console.anthropic.com/
""",
    "invalid_api_key": """Invalid API key format.

API keys typically look like:
- Anthropic: sk-ant-api03-...
- OpenAI: sk-...

Check that you've copied the full key without extra spaces.
Get a new key at: https://console.anthropic.com/
""",
    "model_not_found": """Model '{model}' not found or not accessible.

Available models:
- claude-sonnet-4-20250514 (recommended)
- claude-3-5-haiku-20241022 (faster, cheaper)
- claude-opus-4-20250514 (most capable)

Check your API key permissions at: https://console.anthropic.com/
""",
    "rate_limit": """Rate limit exceeded. Please wait and try again.

Tips to avoid rate limits:
- Wait a few seconds between requests
- Use a model with higher rate limits
- Check your usage at: https://console.anthropic.com/
""",
    "network_error": """Network error: Could not connect to the API.

Possible causes:
- No internet connection
- API service is down
- Firewall blocking the connection

Check your internet connection and try again.
""",
    "timeout": """Request timed out after {timeout} seconds.

This usually happens with:
- Very large files or complex operations
- Slow network connections
- API server being busy

Try again or reduce the scope of your request.
""",
    "file_not_found": """File not found: {path}

Check that:
- The file path is correct
- The file exists
- You have read permissions

Use 'list_files' to see available files in the directory.
""",
    "permission_denied": """Permission denied: {path}

You don't have permission to access this file.

Try:
- Checking file permissions (ls -la)
- Running with appropriate permissions
- Choosing a different file
""",
    "git_not_repo": """Not a git repository.

Initialize a git repository first:
  git init

Or navigate to a directory that contains a git repository.
""",
    "git_conflict": """Git merge conflict detected.

To resolve:
1. Open the conflicting files
2. Edit to resolve conflicts (look for <<<<<<< markers)
3. Stage the resolved files: git add <files>
4. Complete the merge: git commit
""",
    "tool_not_found": """Tool '{tool}' not found.

Use 'chapgent tools' to see all available tools.
Use 'chapgent tools -c <category>' to filter by category.
""",
    "config_invalid": """Invalid configuration: {error}

Check your configuration file:
  chapgent config path    # Show config file location
  chapgent config edit    # Open config in editor

Or reset to defaults:
  chapgent config init --force
""",
    "session_not_found": """Session '{session_id}' not found.

Use 'chapgent sessions' to see all saved sessions.
""",
    "invalid_command": """Unknown command: {command}

Use 'chapgent --help' to see all available commands.
""",
    "template_not_found": """Template '{template}' not found.

Use 'list_templates' tool to see available project templates.
Available templates: python-cli, python-lib, fastapi
""",
    "no_test_framework": """No test framework detected in this project.

Supported test frameworks:
- Python: pytest, unittest
- JavaScript: jest, vitest, mocha
- Go: go test
- Rust: cargo test

Install a test framework and try again.
""",
    "provider_not_supported": """Provider '{provider}' is not supported.

Supported providers:
- anthropic (recommended)
- openai
- azure
- bedrock
- vertex_ai
- ollama (for local models)

Configure with: chapgent config set llm.provider <provider>
""",
    "max_output_tokens_exceeded": """Max output tokens ({max_output_tokens}) exceeded.

The response was too long for the configured limit.

Increase the limit:
  chapgent config set llm.max_output_tokens 8192

Or ask for a shorter response.
""",
    "first_run": """Welcome to Chapgent!

It looks like this is your first time running chapgent.
Let's get you set up.

Run: chapgent setup
""",
}


def get_error_message(error_code: str) -> str | None:
    """Get an error message by code.

    Args:
        error_code: The error code (key in ERROR_MESSAGES).

    Returns:
        The error message template, or None if not found.
    """
    return ERROR_MESSAGES.get(error_code)


def format_error_message(error_code: str, **kwargs: Any) -> str:
    """Format an error message with context values.

    Args:
        error_code: The error code (key in ERROR_MESSAGES).
        **kwargs: Values to substitute into the message template.

    Returns:
        The formatted error message, or a generic message if code not found.

    Example:
        >>> format_error_message("file_not_found", path="/foo/bar.txt")
        "File not found: /foo/bar.txt\\n\\nCheck that:..."
    """
    template = ERROR_MESSAGES.get(error_code)
    if template is None:
        # Return a generic error message
        return f"An error occurred: {error_code}"

    try:
        return template.format(**kwargs)
    except KeyError:
        # If missing placeholder values, return template as-is
        return template


def classify_error(exception: Exception) -> tuple[str, dict[str, Any]]:
    """Classify an exception and return appropriate error code and context.

    Args:
        exception: The exception to classify.

    Returns:
        A tuple of (error_code, context_dict) for use with format_error_message.
    """
    exc_type = type(exception).__name__
    exc_msg = str(exception).lower()

    # File-related errors
    if exc_type == "FileNotFoundError":
        return "file_not_found", {"path": str(exception)}
    if exc_type == "PermissionError":
        return "permission_denied", {"path": str(exception)}

    # Network errors
    if "timeout" in exc_msg or exc_type == "TimeoutError":
        return "timeout", {"timeout": "30"}
    if "connect" in exc_msg or "network" in exc_msg:
        return "network_error", {}

    # API errors
    if "api_key" in exc_msg or "api key" in exc_msg or "authentication" in exc_msg:
        if "invalid" in exc_msg or "incorrect" in exc_msg:
            return "invalid_api_key", {}
        return "no_api_key", {}
    if "rate" in exc_msg and "limit" in exc_msg:
        return "rate_limit", {}
    if "not found" in exc_msg and "model" in exc_msg:
        return "model_not_found", {"model": "unknown"}

    # Git errors
    if "not a git repository" in exc_msg:
        return "git_not_repo", {}
    if "conflict" in exc_msg or "merge" in exc_msg:
        return "git_conflict", {}

    # Default: return a generic error
    return "config_invalid", {"error": str(exception)}


def get_suggestion_for_error(error_code: str) -> str | None:
    """Get a brief suggestion for fixing an error.

    Args:
        error_code: The error code.

    Returns:
        A brief suggestion string, or None if no suggestion available.
    """
    suggestions: dict[str, str] = {
        "no_api_key": "Run: export ANTHROPIC_API_KEY=your-key",
        "invalid_api_key": "Double-check your API key and try again",
        "model_not_found": "Try: chapgent config set llm.model claude-sonnet-4-20250514",
        "rate_limit": "Wait a moment and try again",
        "network_error": "Check your internet connection",
        "timeout": "Try a simpler request",
        "file_not_found": "Check the file path",
        "permission_denied": "Check file permissions",
        "git_not_repo": "Run: git init",
        "git_conflict": "Resolve merge conflicts manually",
        "config_invalid": "Run: chapgent config init --force",
        "session_not_found": "Run: chapgent sessions",
        "template_not_found": "Use: list_templates",
        "no_test_framework": "Install pytest or another test framework",
    }
    return suggestions.get(error_code)
