"""CLI package for chapgent."""

from chapgent.cli.main import cli

# Import subcommand modules to trigger command registration
from chapgent.cli import auth  # noqa: F401
from chapgent.cli import config  # noqa: F401
from chapgent.cli import diagnostics  # noqa: F401
from chapgent.cli import help  # noqa: F401
from chapgent.cli import proxy  # noqa: F401
from chapgent.cli import setup  # noqa: F401
from chapgent.cli import tools  # noqa: F401

__all__ = ["cli"]
