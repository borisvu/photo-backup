"""
Log viewer commands for photo-backup CLI.

This module provides commands for viewing and filtering log files.
"""

import subprocess
import sys

import click
from pathlib import Path

from ..config import Config


def get_log_file_path(config: Config) -> Path:
    """Get the log file path based on configuration.

    Args:
        config: Configuration object

    Returns:
        Path to the log file
    """
    log_directory = config.get("logging.directory")
    if not log_directory:
        # Fallback to default paths
        log_directory = "/tmp/photo-backup-test/logs" if config.is_test_mode() else "~/Library/Logs/photo-backup"

    log_dir = Path(log_directory).expanduser()
    return log_dir / "photo-backup.log"


def run_command(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a shell command and return results.

    Args:
        cmd: Command to run as list of strings
        check: Whether to raise CalledProcessError on non-zero exit

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def filter_logs_by_level(log_content: str, level: str) -> str:
    """Filter log content by log level.

    Args:
        log_content: Raw log content
        level: Log level to filter by (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Filtered log content
    """
    if not log_content.strip():
        return ""

    # For JSON logs, use jq if available, otherwise use grep
    if log_content.strip().startswith("{"):
        return filter_json_logs_by_level(log_content, level)
    else:
        return filter_text_logs_by_level(log_content, level)


def filter_json_logs_by_level(_log_content: str, level: str) -> str:
    """Filter JSON log content by level using jq or grep.

    Args:
        _log_content: JSON log content (unused, kept for interface consistency)
        level: Log level to filter by

    Returns:
        Filtered JSON log content
    """
    # Try jq first for JSON filtering
    jq_cmd = ["jq", "-r", f'select(.level == "{level.upper()}")', "-"]

    returncode, stdout, stderr = run_command(jq_cmd, check=False)

    if returncode == 0 and stdout.strip():
        return stdout

    # Fallback to grep for JSON logs
    grep_cmd = ["grep", "-i", f'"level": "{level.upper()}"']
    returncode, stdout, stderr = run_command(grep_cmd, check=False)

    if returncode == 0:
        return stdout
    else:
        # If grep fails, return empty (no matches)
        return ""


def filter_text_logs_by_level(log_content: str, level: str) -> str:
    """Filter text log content by level using grep.

    Args:
        log_content: Text log content
        level: Log level to filter by

    Returns:
        Filtered text log content
    """
    # Create a temporary file with the log content
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(log_content)
        temp_file = f.name

    try:
        # Use grep to filter by level
        grep_cmd = ["grep", "-i", f"\\b{level.upper()}\\b", temp_file]
        returncode, stdout, stderr = run_command(grep_cmd, check=False)

        if returncode == 0:
            return stdout
        else:
            return ""
    finally:
        # Clean up temporary file
        Path(temp_file).unlink(missing_ok=True)


@click.command()
@click.option("--tail", default=50, help="Show last N lines (default: 50)")
@click.option(
    "--level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]), help="Filter by log level"
)
@click.option("--errors", is_flag=True, help="Show only error/critical logs (shortcut for --level ERROR)")
@click.option("--follow", is_flag=True, help="Follow log file in real-time (like tail -f)")
@click.option("--json", is_flag=True, help="Output in JSON format (if logs are in JSON format)")
@click.pass_context
def logs(ctx: click.Context, tail: int, level: str | None, errors: bool, follow: bool, _json: bool) -> None:
    """View and filter photo-backup log files.

    This command provides comprehensive log viewing and filtering capabilities,
    leveraging Unix tools under the hood for efficient processing.

    Examples:
        photo-backup logs                    # Show last 50 lines
        photo-backup logs --tail 100         # Show last 100 lines
        photo-backup logs --level ERROR      # Show only error logs
        photo-backup logs --errors           # Show only error/critical logs
        photo-backup logs --follow           # Follow logs in real-time
        photo-backup logs --json             # Output in JSON format
    """
    # Get config from context
    context_data = ctx.obj
    test_mode = context_data.get("test_mode", False)
    dry_run = context_data.get("dry_run", False)

    # Create config object
    config = Config(test_mode=test_mode, dry_run=dry_run)
    try:
        config.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    # TODO: Implement JSON output formatting
    # _json parameter is currently unused but kept for future implementation

    # Get log file path
    log_file = get_log_file_path(config)

    if not log_file.exists():
        click.echo(f"Log file not found: {log_file}", err=True)
        click.echo("No logs have been generated yet.", err=True)
        sys.exit(1)

    # Handle --errors flag
    if errors:
        level = "ERROR"

    # Execute the command
    if follow:
        # For follow mode, run interactively with shell for piping
        if level:
            shell_cmd = f"tail -f -n {tail} {log_file} | grep -i '\\b{level.upper()}\\b'"
        else:
            shell_cmd = f"tail -f -n {tail} {log_file}"

        try:
            subprocess.run(shell_cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            click.echo(f"Error running command: {e}", err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            click.echo("\nStopped following logs.")
            sys.exit(0)
    else:
        # For non-follow mode, get the log content first
        tail_cmd = ["tail", "-n", str(tail), str(log_file)]
        returncode, stdout, stderr = run_command(tail_cmd, check=False)

        if returncode != 0:
            click.echo(f"Error reading log file: {stderr}", err=True)
            sys.exit(1)

        # Apply level filtering if needed
        if level and stdout:
            filtered = filter_logs_by_level(stdout, level)
            if filtered:
                click.echo(filtered, nl=False)
            else:
                click.echo(f"No {level} level logs found.")
        else:
            click.echo(stdout, nl=False)
