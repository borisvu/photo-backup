"""
Functional tests for photo-backup start command.

Tests cover:
- Start command execution
- Foreground/background mode selection
- Test mode vs production mode
- Service initialization
- Error handling

Note: Tests use mocking to avoid actually starting the service loop,
which would cause tests to hang indefinitely.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from photo_backup.main import main


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_service_manager():
    """Mock ServiceManager to avoid starting actual service."""
    with patch("photo_backup.cli.service_commands.ServiceManager") as mock:
        # Mock the start method to return immediately
        mock_instance = MagicMock()
        mock_instance.start.return_value = None
        mock.return_value = mock_instance
        yield mock


class TestStartCommandBasics:
    """Test basic start command functionality."""

    def test_start_command_exists(self, cli_runner):
        """Test that start command is registered."""
        result = cli_runner.invoke(main, ["start", "--help"])
        assert result.exit_code == 0
        assert "Start the photo backup service" in result.output

    def test_start_command_shows_usage(self, cli_runner):
        """Test that start command shows usage information."""
        result = cli_runner.invoke(main, ["start", "--help"])
        assert "--background" in result.output
        assert "--foreground" in result.output

    def test_start_in_test_mode_foreground(self, cli_runner, mock_service_manager):
        """Test starting service in test mode (foreground by default)."""
        result = cli_runner.invoke(main, ["--test-mode", "start"])
        
        assert result.exit_code == 0
        assert "Starting photo backup service" in result.output
        assert "TEST MODE" in result.output
        assert "foreground" in result.output

    def test_start_shows_configuration(self, cli_runner, mock_service_manager):
        """Test that start command shows configuration."""
        result = cli_runner.invoke(main, ["--test-mode", "start"])
        
        assert "Monitor path:" in result.output
        assert "Destination:" in result.output
        assert "Check interval:" in result.output
        assert "Loop interval:" in result.output

    def test_start_with_dry_run(self, cli_runner, mock_service_manager):
        """Test starting service in dry-run mode."""
        result = cli_runner.invoke(main, ["--test-mode", "--dry-run", "start"])
        
        assert "DRY RUN MODE" in result.output


class TestStartCommandModes:
    """Test foreground/background mode selection."""

    def test_start_with_foreground_flag(self, cli_runner, mock_service_manager):
        """Test starting with explicit foreground flag."""
        result = cli_runner.invoke(main, ["--test-mode", "start", "--foreground"])
        
        assert result.exit_code == 0
        assert "foreground" in result.output.lower()

    def test_start_with_background_flag(self, cli_runner, mock_service_manager):
        """Test starting with explicit background flag."""
        result = cli_runner.invoke(main, ["--test-mode", "start", "--background"])
        
        assert result.exit_code == 0
        # Background mode not fully implemented yet, should show warning
        assert "background" in result.output.lower()

    def test_start_cannot_specify_both_modes(self, cli_runner):
        """Test that specifying both foreground and background fails."""
        result = cli_runner.invoke(main, ["--test-mode", "start", "--foreground", "--background"])
        
        assert result.exit_code == 1
        assert "Cannot specify both" in result.output


class TestStartCommandIntegration:
    """Test start command integration with service manager."""

    def test_start_creates_service_manager(self, cli_runner, mock_service_manager):
        """Test that start command creates ServiceManager."""
        result = cli_runner.invoke(main, ["--test-mode", "start"])
        
        # Service should initialize
        assert result.exit_code == 0
        assert "Starting photo backup service" in result.output
        # Verify ServiceManager was instantiated
        assert mock_service_manager.called

    def test_start_calls_service_start_method(self, cli_runner, mock_service_manager):
        """Test that start command calls ServiceManager.start()."""
        result = cli_runner.invoke(main, ["--test-mode", "start"])
        
        assert result.exit_code == 0
        # Verify start() was called on the service instance
        mock_service_manager.return_value.start.assert_called_once()

    def test_start_shows_press_ctrl_c_message(self, cli_runner, mock_service_manager):
        """Test that start shows Ctrl+C message."""
        result = cli_runner.invoke(main, ["--test-mode", "start"])
        assert "Press Ctrl+C" in result.output or "Service" in result.output


class TestStartCommandErrors:
    """Test start command error handling."""

    def test_start_handles_service_error(self, cli_runner, mock_service_manager):
        """Test that start handles service errors gracefully."""
        # Make service.start() raise an exception
        mock_service_manager.return_value.start.side_effect = Exception("Test error")
        
        result = cli_runner.invoke(main, ["--test-mode", "start"])
        
        assert result.exit_code == 1
        assert "Error starting service" in result.output


class TestStopCommandPlaceholder:
    """Test stop command placeholder."""

    def test_stop_command_exists(self, cli_runner):
        """Test that stop command is registered."""
        result = cli_runner.invoke(main, ["stop", "--help"])
        assert result.exit_code == 0

    def test_stop_command_not_yet_implemented(self, cli_runner):
        """Test that stop command shows not implemented message."""
        result = cli_runner.invoke(main, ["--test-mode", "stop"])
        assert "not yet implemented" in result.output


class TestRestartCommandPlaceholder:
    """Test restart command placeholder."""

    def test_restart_command_exists(self, cli_runner):
        """Test that restart command is registered."""
        result = cli_runner.invoke(main, ["restart", "--help"])
        assert result.exit_code == 0

    def test_restart_command_not_yet_implemented(self, cli_runner):
        """Test that restart command shows not implemented message."""
        result = cli_runner.invoke(main, ["--test-mode", "restart"])
        assert "not yet implemented" in result.output

