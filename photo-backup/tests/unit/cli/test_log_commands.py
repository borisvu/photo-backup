"""
Unit tests for log viewer commands.

Tests log viewing and filtering functionality.
"""

from unittest.mock import Mock, patch

from photo_backup.cli.log_commands import (
    filter_json_logs_by_level,
    filter_logs_by_level,
    filter_text_logs_by_level,
    get_log_file_path,
    run_command,
)


class TestLogCommands:
    """Test log viewer command functionality."""

    def test_get_log_file_path_production_mode(self):
        """Test log file path for production mode."""
        config = Mock()
        config.get.return_value = "~/Library/Logs/photo-backup"
        config.is_test_mode = False

        log_path = get_log_file_path(config)

        assert log_path.name == "photo-backup.log"
        assert "Library/Logs/photo-backup" in str(log_path)

    def test_get_log_file_path_test_mode(self):
        """Test log file path for test mode."""
        config = Mock()
        config.get.return_value = None
        config.is_test_mode.return_value = True
        
        log_path = get_log_file_path(config)
        
        assert log_path.name == "photo-backup.log"
        assert "/tmp/photo-backup-test/logs" in str(log_path)

    def test_get_log_file_path_fallback(self):
        """Test log file path fallback for production mode."""
        config = Mock()
        config.get.return_value = None
        config.is_test_mode.return_value = False
        
        log_path = get_log_file_path(config)
        
        assert log_path.name == "photo-backup.log"
        assert "Library/Logs/photo-backup" in str(log_path)

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "test output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        returncode, stdout, stderr = run_command(["echo", "test"])

        assert returncode == 0
        assert stdout == "test output"
        assert stderr == ""

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test command execution failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_run.return_value = mock_result

        returncode, stdout, stderr = run_command(["false"], check=False)

        assert returncode == 1
        assert stdout == ""
        assert stderr == "command failed"

    @patch("subprocess.run")
    def test_run_command_timeout(self, mock_run):
        """Test command timeout."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired(["sleep", "60"], 30)

        returncode, stdout, stderr = run_command(["sleep", "60"])

        assert returncode == 1
        assert stdout == ""
        assert "timed out" in stderr

    def test_filter_logs_by_level_empty(self):
        """Test filtering empty log content."""
        result = filter_logs_by_level("", "ERROR")
        assert result == ""

    def test_filter_logs_by_level_json(self):
        """Test filtering JSON log content."""
        json_content = """{"level": "INFO", "message": "test1"}
{"level": "ERROR", "message": "test2"}
{"level": "INFO", "message": "test3"}"""

        with patch("photo_backup.cli.log_commands.filter_json_logs_by_level") as mock_filter:
            mock_filter.return_value = '{"level": "ERROR", "message": "test2"}'

            result = filter_logs_by_level(json_content, "ERROR")

            mock_filter.assert_called_once_with(json_content, "ERROR")
            assert result == '{"level": "ERROR", "message": "test2"}'

    def test_filter_logs_by_level_text(self):
        """Test filtering text log content."""
        text_content = """2024-01-01 10:00:00 INFO - test1
2024-01-01 10:00:01 ERROR - test2
2024-01-01 10:00:02 INFO - test3"""

        with patch("photo_backup.cli.log_commands.filter_text_logs_by_level") as mock_filter:
            mock_filter.return_value = "2024-01-01 10:00:01 ERROR - test2"

            result = filter_logs_by_level(text_content, "ERROR")

            mock_filter.assert_called_once_with(text_content, "ERROR")
            assert result == "2024-01-01 10:00:01 ERROR - test2"

    @patch("photo_backup.cli.log_commands.run_command")
    def test_filter_json_logs_by_level_with_jq(self, mock_run_command):
        """Test JSON filtering with jq available."""
        json_content = """{"level": "INFO", "message": "test1"}
{"level": "ERROR", "message": "test2"}"""

        mock_run_command.return_value = (0, '{"level": "ERROR", "message": "test2"}', "")

        result = filter_json_logs_by_level(json_content, "ERROR")

        assert result == '{"level": "ERROR", "message": "test2"}'
        mock_run_command.assert_called_once()

    @patch("photo_backup.cli.log_commands.run_command")
    def test_filter_json_logs_by_level_fallback_to_grep(self, mock_run_command):
        """Test JSON filtering fallback to grep when jq fails."""
        json_content = """{"level": "INFO", "message": "test1"}
{"level": "ERROR", "message": "test2"}"""

        # jq fails, grep succeeds
        mock_run_command.side_effect = [
            (1, "", "jq not found"),  # jq fails
            (0, '{"level": "ERROR", "message": "test2"}', ""),  # grep succeeds
        ]

        result = filter_json_logs_by_level(json_content, "ERROR")

        assert result == '{"level": "ERROR", "message": "test2"}'
        assert mock_run_command.call_count == 2

    @patch("photo_backup.cli.log_commands.run_command")
    def test_filter_json_logs_by_level_no_matches(self, mock_run_command):
        """Test JSON filtering when no matches found."""
        json_content = """{"level": "INFO", "message": "test1"}
{"level": "WARNING", "message": "test2"}"""

        # Both jq and grep fail
        mock_run_command.side_effect = [
            (1, "", "jq not found"),  # jq fails
            (1, "", ""),  # grep fails (no matches)
        ]

        result = filter_json_logs_by_level(json_content, "ERROR")

        assert result == ""

    def test_filter_text_logs_by_level(self):
        """Test text log filtering."""
        text_content = """2024-01-01 10:00:00 INFO - test1
2024-01-01 10:00:01 ERROR - test2
2024-01-01 10:00:02 INFO - test3"""

        with patch("photo_backup.cli.log_commands.run_command") as mock_run_command:
            mock_run_command.return_value = (0, "2024-01-01 10:00:01 ERROR - test2", "")

            result = filter_text_logs_by_level(text_content, "ERROR")

            assert result == "2024-01-01 10:00:01 ERROR - test2"
            mock_run_command.assert_called_once()

    def test_filter_text_logs_by_level_no_matches(self):
        """Test text log filtering when no matches found."""
        text_content = """2024-01-01 10:00:00 INFO - test1
2024-01-01 10:00:01 WARNING - test2"""

        with patch("photo_backup.cli.log_commands.run_command") as mock_run_command:
            mock_run_command.return_value = (1, "", "")

            result = filter_text_logs_by_level(text_content, "ERROR")

            assert result == ""
