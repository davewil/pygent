"""Logging infrastructure for pygent using loguru.

This module provides file-based logging that doesn't interfere with the TUI.
Logs are written to ~/.local/share/pygent/logs/ with rotation and compression.
"""

import re
from pathlib import Path

from loguru import logger

# Default log directory
DEFAULT_LOG_DIR = Path("~/.local/share/pygent/logs").expanduser()
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "pygent.log"

# Log format string
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}"

# Valid log levels
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})

# Track if logging has been set up to avoid duplicate handlers
_logging_initialized = False


def get_log_dir() -> Path:
    """Return the default log directory path."""
    return DEFAULT_LOG_DIR


def get_log_file() -> Path:
    """Return the default log file path."""
    return DEFAULT_LOG_FILE


def get_valid_log_levels() -> frozenset[str]:
    """Return set of valid log level names."""
    return VALID_LOG_LEVELS


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
    compression: str = "gz",
) -> Path:
    """Configure logging to file with rotation.

    Removes the default stderr handler (which would corrupt TUI) and adds
    a file handler with rotation, retention, and compression.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Path to log file. Defaults to ~/.local/share/pygent/logs/pygent.log
        rotation: When to rotate log files (e.g., "10 MB", "1 day").
        retention: How long to keep rotated files (e.g., "7 days", "1 month").
        compression: Compression format for rotated files (e.g., "gz", "zip").

    Returns:
        Path to the log file being used.

    Raises:
        ValueError: If level is not a valid log level.
    """
    global _logging_initialized

    # Validate log level
    level_upper = level.upper()
    if level_upper not in VALID_LOG_LEVELS:
        valid = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(f"Invalid log level '{level}'. Valid levels are: {valid}")

    # Determine log file path
    if log_file is None:
        log_path = DEFAULT_LOG_FILE
    else:
        log_path = Path(log_file).expanduser()

    # Create log directory if needed
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove default stderr handler (would corrupt TUI)
    # Only do this once to avoid removing handlers multiple times
    if not _logging_initialized:
        logger.remove()

    # Add file handler
    logger.add(
        log_path,
        level=level_upper,
        format=LOG_FORMAT,
        rotation=rotation,
        retention=retention,
        compression=compression,
        enqueue=True,  # Thread-safe async logging
    )

    _logging_initialized = True

    logger.info(f"Logging initialized at {level_upper} level to {log_path}")

    return log_path


def disable_logging() -> None:
    """Disable all logging.

    Useful for testing to prevent log file creation.
    """
    logger.disable("pygent")


def enable_logging() -> None:
    """Re-enable logging after it was disabled."""
    logger.enable("pygent")


def reset_logging() -> None:
    """Reset logging state for testing.

    Removes all handlers and resets initialization flag.
    """
    global _logging_initialized
    logger.remove()
    _logging_initialized = False


def redact_sensitive(content: str) -> str:
    """Remove API keys, absolute paths, and other sensitive data from log content.

    Args:
        content: Log content to redact.

    Returns:
        Content with sensitive information replaced with placeholders.
    """
    # Redact API key patterns
    # Match common API key formats: sk-xxx, api-key: xxx, api_key = "xxx"
    content = re.sub(r"(api[_-]?key[\"\s:=]+)[\"']?[\w-]+", r"\1[REDACTED]", content, flags=re.I)
    content = re.sub(r"(sk-[a-zA-Z0-9]{20,})", "[REDACTED_KEY]", content)
    content = re.sub(r"(ANTHROPIC_API_KEY=)[^\s\n]+", r"\1[REDACTED]", content)
    content = re.sub(r"(OPENAI_API_KEY=)[^\s\n]+", r"\1[REDACTED]", content)
    content = re.sub(r"(PYGENT_API_KEY=)[^\s\n]+", r"\1[REDACTED]", content)

    # Redact home directory paths
    home = str(Path.home())
    content = content.replace(home, "~")

    return content


def get_log_files(days: int = 7) -> list[Path]:
    """Get list of log files from the log directory.

    Args:
        days: Maximum age of logs to include (not currently implemented,
              returns all log files for simplicity).

    Returns:
        List of paths to log files (main log and rotated files).
    """
    log_dir = get_log_dir()
    if not log_dir.exists():
        return []

    # Get all log files (main log and rotated/compressed versions)
    log_files: list[Path] = []
    for pattern in ["pygent.log", "pygent.log.*"]:
        log_files.extend(log_dir.glob(pattern))

    # Sort by modification time (newest first)
    log_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return log_files


# Export the logger instance for use throughout the codebase
__all__ = [
    "logger",
    "setup_logging",
    "disable_logging",
    "enable_logging",
    "reset_logging",
    "redact_sensitive",
    "get_log_dir",
    "get_log_file",
    "get_log_files",
    "get_valid_log_levels",
    "VALID_LOG_LEVELS",
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_FILE",
    "LOG_FORMAT",
]
