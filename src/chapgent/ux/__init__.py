"""UX utilities for chapgent.

This module provides user experience enhancements including:
- Friendly error messages
- First-run experience
- Help system
"""

from chapgent.ux.help import HELP_TOPICS, get_help_topic, list_help_topics
from chapgent.ux.messages import ERROR_MESSAGES, format_error_message, get_error_message

__all__ = [
    "ERROR_MESSAGES",
    "HELP_TOPICS",
    "format_error_message",
    "get_error_message",
    "get_help_topic",
    "list_help_topics",
]
