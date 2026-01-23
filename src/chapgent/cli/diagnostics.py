"""Diagnostic commands for troubleshooting."""

from pathlib import Path

import click

from chapgent.cli.main import cli


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--days", default=7, help="Include logs from last N days")
def report(output: str | None, days: int) -> None:
    """Package logs for bug reporting.

    Creates a compressed archive of recent logs with sensitive
    data (API keys, absolute paths) redacted.
    """
    import io
    import tarfile
    from datetime import datetime

    from chapgent.core.logging import get_log_dir, get_log_files, redact_sensitive

    log_dir = get_log_dir()

    if not log_dir.exists():
        click.echo("No logs found. Run chapgent with logging enabled first.")
        return

    log_files = get_log_files(days=days)
    if not log_files:
        click.echo("No log files found.")
        return

    # Default output path
    if output is None:
        output = f"chapgent-report-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"

    output_path = Path(output)

    # Collect and sanitize logs into archive
    try:
        with tarfile.open(output_path, "w:gz") as tar:
            for log_file in log_files:
                try:
                    # Read and redact sensitive info
                    content = log_file.read_text(errors="replace")
                    redacted = redact_sensitive(content)

                    # Create a tarinfo object with the redacted content
                    data = redacted.encode("utf-8")
                    tarinfo = tarfile.TarInfo(name=log_file.name)
                    tarinfo.size = len(data)
                    tar.addfile(tarinfo, io.BytesIO(data))

                    click.echo(f"  Added: {log_file.name}")
                except Exception as e:
                    click.echo(f"  Skipped: {log_file.name} ({e})", err=True)

        click.echo(f"\nReport created: {output_path}")
        click.echo("Please attach this file to your GitHub issue.")
        click.echo(f"Report size: {output_path.stat().st_size} bytes")
    except Exception as e:
        raise click.ClickException(f"Failed to create report: {e}") from None


@cli.command()
@click.option(
    "--level", "-l", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO", help="Log level"
)
@click.option("--file", "-f", "log_file", type=click.Path(), help="Custom log file path")
def logs(level: str, log_file: str | None) -> None:
    """Show log file path and configure logging.

    Without options, shows current log file path. With options, you can
    configure logging level and custom log file path.
    """
    from chapgent.core.logging import get_log_file, setup_logging

    if log_file:
        # User wants to configure logging
        log_path = setup_logging(level=level, log_file=log_file)
        click.echo(f"Logging configured: level={level}, file={log_path}")
    else:
        # Just show current log file path
        log_path = get_log_file()
        exists = log_path.exists()
        status = "[exists]" if exists else "[not found]"
        click.echo(f"Log file: {log_path} {status}")

        if exists:
            size = log_path.stat().st_size
            click.echo(f"Size: {size} bytes")

        click.echo(f"\nTo view logs: cat {log_path}")
        click.echo(f"To tail logs: tail -f {log_path}")


__all__ = ["report", "logs"]
