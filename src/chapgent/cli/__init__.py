"""CLI package for chapgent."""

# Import subcommand modules to trigger command registration
from chapgent.cli import (
    auth,  # noqa: F401
    config,  # noqa: F401
    diagnostics,  # noqa: F401
    help,  # noqa: F401
    proxy,  # noqa: F401
    setup,  # noqa: F401
    tools,  # noqa: F401
)
from chapgent.cli.main import cli

__all__ = ["cli"]
