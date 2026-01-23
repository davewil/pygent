"""Help command."""

import click

from chapgent.cli.main import cli
from chapgent.ux.help import format_help_topic, get_help_topic, list_help_topics


@cli.command("help")
@click.argument("topic", required=False)
def help_cmd(topic: str | None) -> None:
    """Show help for a topic.

    Available topics: tools, config, shortcuts, permissions, sessions,
    prompts, quickstart, troubleshooting.

    Examples:
      chapgent help              List all help topics
      chapgent help tools        Show help about available tools
      chapgent help shortcuts    Show keyboard shortcuts
    """
    if topic is None:
        # List all topics
        click.echo("Chapgent Help Topics")
        click.echo("=" * 60)
        click.echo()

        topics = list_help_topics()
        for name, summary in sorted(topics):
            click.echo(f"  {name:<15} {summary}")

        click.echo()
        click.echo("Use 'chapgent help <topic>' for detailed information.")
        click.echo("Use 'chapgent --help' for command-line options.")
        return

    # Show specific topic
    help_topic = get_help_topic(topic)
    if help_topic is None:
        topics = list_help_topics()
        available = ", ".join(name for name, _ in sorted(topics))
        raise click.ClickException(f"Unknown help topic: {topic}\nAvailable topics: {available}") from None

    click.echo(format_help_topic(help_topic))


__all__ = ["help_cmd"]
