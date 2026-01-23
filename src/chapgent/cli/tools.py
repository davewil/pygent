"""Tools listing command."""

import click

from chapgent.cli.main import cli
from chapgent.tools.base import ToolCategory
from chapgent.tools.registry import ToolRegistry


def _create_full_registry() -> ToolRegistry:
    """Create a registry with all available tools registered."""
    registry = ToolRegistry()

    # Filesystem tools
    from chapgent.tools.filesystem import (
        copy_file,
        create_file,
        delete_file,
        edit_file,
        list_files,
        move_file,
        read_file,
    )

    registry.register(read_file)
    registry.register(list_files)
    registry.register(edit_file)
    registry.register(create_file)
    registry.register(delete_file)
    registry.register(move_file)
    registry.register(copy_file)

    # Shell tool
    from chapgent.tools.shell import shell

    registry.register(shell)

    # Search tools
    from chapgent.tools.search import find_definition, find_files, grep_search

    registry.register(grep_search)
    registry.register(find_files)
    registry.register(find_definition)

    # Git tools
    from chapgent.tools.git import (
        git_add,
        git_branch,
        git_checkout,
        git_commit,
        git_diff,
        git_log,
        git_pull,
        git_push,
        git_status,
    )

    registry.register(git_status)
    registry.register(git_diff)
    registry.register(git_log)
    registry.register(git_branch)
    registry.register(git_add)
    registry.register(git_commit)
    registry.register(git_checkout)
    registry.register(git_push)
    registry.register(git_pull)

    # Web tools
    from chapgent.tools.web import web_fetch

    registry.register(web_fetch)

    # Testing tools
    from chapgent.tools.testing import run_tests

    registry.register(run_tests)

    # Project scaffolding tools
    from chapgent.tools.scaffold import add_component, create_project, list_components, list_templates

    registry.register(list_templates)
    registry.register(create_project)
    registry.register(add_component)
    registry.register(list_components)

    return registry


@cli.command()
@click.option("--category", "-c", help="Filter by category (filesystem, git, search, web, shell, testing, project)")
def tools(category: str | None) -> None:
    """List all available tools."""
    registry = _create_full_registry()

    # Risk level colors/indicators
    risk_indicators = {
        "low": "[LOW]",
        "medium": "[MEDIUM]",
        "high": "[HIGH]",
    }

    if category:
        # Filter by category
        try:
            cat = ToolCategory(category.lower())
        except ValueError:
            valid = ", ".join(c.value for c in ToolCategory)
            raise click.ClickException(f"Invalid category '{category}'. Valid: {valid}") from None

        tool_list = registry.list_by_category(cat)
        if not tool_list:
            click.echo(f"No tools in category '{category}'.")
            return

        click.echo(f"\n{cat.value.title()} Tools:")
        click.echo("-" * 60)
        for tool in sorted(tool_list, key=lambda t: t.name):
            risk = risk_indicators.get(tool.risk.value, "[?]")
            click.echo(f"  {tool.name:<20} {tool.description:<40} {risk}")
    else:
        # Show all tools grouped by category
        categories = registry.get_categories()

        for cat in categories:
            tool_list = registry.list_by_category(cat)
            if not tool_list:
                continue

            click.echo(f"\n{cat.value.title()} Tools:")
            click.echo("-" * 60)
            for tool in sorted(tool_list, key=lambda t: t.name):
                risk = risk_indicators.get(tool.risk.value, "[?]")
                click.echo(f"  {tool.name:<20} {tool.description:<40} {risk}")

    click.echo()


__all__ = ["tools"]
