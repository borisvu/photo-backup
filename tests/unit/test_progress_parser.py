"""
Unit tests for the progress parser module.
"""

from unittest.mock import MagicMock

from photo_backup.progress_parser import RcloneProgressParser, TransferStats


class TestTransferStats:
    """Test TransferStats class."""

    def test_transfer_stats_initialization(self):
        """Test TransferStats can be initialized correctly."""
        stats = TransferStats()

        assert stats.files_transferred == 0
        assert stats.files_total == 0
        assert stats.bytes_transferred == 0
        assert stats.bytes_total == 0
        assert stats.transfer_rate_mbps == 0.0
        assert stats.eta_seconds is None
        assert stats.percentage == 0.0
        assert stats.errors == 0

    def test_transfer_stats_with_values(self):
        """Test TransferStats with specific values."""
        stats = TransferStats(
            files_transferred=5,
            files_total=10,
            bytes_transferred=1024 * 1024 * 5,  # 5 MB
            bytes_total=1024 * 1024 * 10,  # 10 MB
            transfer_rate_mbps=2.5,
            eta_seconds=120,
            percentage=50.0,
            errors=1,
        )

        assert stats.files_transferred == 5
        assert stats.files_total == 10
        assert stats.bytes_transferred == 5 * 1024 * 1024
        assert stats.bytes_total == 10 * 1024 * 1024
        assert stats.transfer_rate_mbps == 2.5
        assert stats.eta_seconds == 120
        assert stats.percentage == 50.0
        assert stats.errors == 1

    def test_files_percentage(self):
        """Test files percentage calculation."""
        stats = TransferStats(files_transferred=3, files_total=10)
        assert stats.files_percentage == 30.0

        # Test edge case with no files
        stats = TransferStats(files_transferred=0, files_total=0)
        assert stats.files_percentage == 0.0

    def test_bytes_percentage(self):
        """Test bytes percentage calculation."""
        stats = TransferStats(bytes_transferred=300, bytes_total=1000)
        assert stats.bytes_percentage == 30.0

        # Test edge case with no bytes
        stats = TransferStats(bytes_transferred=0, bytes_total=0)
        assert stats.bytes_percentage == 0.0


class TestRcloneProgressParser:
    """Test RcloneProgressParser class."""

    def test_parser_initialization(self):
        """Test parser can be initialized correctly."""
        parser = RcloneProgressParser()

        assert parser.progress_logger is None
        assert parser.progress_callback is None
        assert isinstance(parser.last_stats, TransferStats)
        assert parser.logger is not None

    def test_parser_with_logger(self):
        """Test parser initialization with custom logger."""
        mock_logger = MagicMock()
        parser = RcloneProgressParser(mock_logger)

        assert parser.logger == mock_logger

    def test_set_progress_callback(self):
        """Test setting progress callback."""
        parser = RcloneProgressParser()
        callback = MagicMock()

        parser.set_progress_callback(callback)
        assert parser.progress_callback == callback

    def test_init_progress_logger(self):
        """Test initializing progress logger."""
        parser = RcloneProgressParser()

        parser.init_progress_logger(10, "test_operation")

        assert parser.progress_logger is not None
        assert parser.progress_logger.total_items == 10
        assert parser.progress_logger.operation_type == "test_operation"

    def test_parse_stats_one_line_basic(self):
        """Test parsing basic stats-one-line format."""
        parser = RcloneProgressParser()

        # Test line: "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete, 1.2 MiB/s, ETA 2s"
        line = "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete, 1.2 MiB/s, ETA 2s"

        stats = parser.parse_line(line)

        assert stats is not None
        assert stats.files_transferred == 5
        assert stats.files_total == 10
        assert stats.bytes_transferred == int(1.5 * 1024 * 1024)
        assert stats.bytes_total == int(3.0 * 1024 * 1024)
        assert stats.percentage == 50.0
        assert abs(stats.transfer_rate_mbps - 1.2) < 0.01  # Allow for floating point precision
        assert stats.eta_seconds == 2

    def test_parse_stats_one_line_without_rate(self):
        """Test parsing stats line without transfer rate."""
        parser = RcloneProgressParser()

        line = "Transferred: 3 / 8 files, 500 KiB / 2.0 MiB, 25% complete"

        stats = parser.parse_line(line)

        assert stats is not None
        assert stats.files_transferred == 3
        assert stats.files_total == 8
        assert stats.bytes_transferred == 500 * 1024
        assert stats.bytes_total == int(2.0 * 1024 * 1024)
        assert stats.percentage == 25.0
        assert stats.transfer_rate_mbps == 0.0
        assert stats.eta_seconds is None

    def test_parse_final_summary(self):
        """Test parsing final transfer summary."""
        parser = RcloneProgressParser()

        line = "Transferred: 10 files (5.2 MiB)"

        stats = parser.parse_line(line)

        assert stats is not None
        assert stats.files_transferred == 10
        assert stats.files_total == 10
        assert stats.bytes_transferred == int(5.2 * 1024 * 1024)
        assert stats.bytes_total == int(5.2 * 1024 * 1024)
        assert stats.percentage == 100.0

    def test_parse_error_line(self):
        """Test parsing error lines."""
        parser = RcloneProgressParser()

        line = "ERROR : file.jpg: permission denied"

        # Should not return stats but should increment error count
        stats = parser.parse_line(line)
        assert stats is None
        assert parser.last_stats.errors == 1

    def test_parse_empty_line(self):
        """Test parsing empty lines."""
        parser = RcloneProgressParser()

        stats = parser.parse_line("")
        assert stats is None

        stats = parser.parse_line("   ")
        assert stats is None

    def test_parse_unrecognized_line(self):
        """Test parsing unrecognized lines."""
        parser = RcloneProgressParser()

        line = "Some unrecognized output line"

        stats = parser.parse_line(line)
        assert stats is None

    def test_progress_callback_called(self):
        """Test that progress callback is called."""
        parser = RcloneProgressParser()
        callback = MagicMock()
        parser.set_progress_callback(callback)

        line = "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete"

        parser.parse_line(line)

        assert callback.called
        stats = callback.call_args[0][0]
        assert isinstance(stats, TransferStats)
        assert stats.files_transferred == 5

    def test_progress_callback_exception_handling(self):
        """Test that parser handles callback exceptions gracefully."""
        parser = RcloneProgressParser()
        callback = MagicMock(side_effect=Exception("Callback error"))
        parser.set_progress_callback(callback)

        line = "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete"

        # Should not raise exception
        stats = parser.parse_line(line)
        assert stats is not None

    def test_parse_size_conversions(self):
        """Test size parsing with different units."""
        parser = RcloneProgressParser()

        # Test bytes
        assert parser._parse_size("100", "") == 100

        # Test KiB
        assert parser._parse_size("1", "K") == 1024

        # Test MiB
        assert parser._parse_size("1", "M") == 1024 * 1024

        # Test GiB
        assert parser._parse_size("1", "G") == 1024 * 1024 * 1024

        # Test TiB
        assert parser._parse_size("1", "T") == 1024 * 1024 * 1024 * 1024

        # Test decimal values
        assert parser._parse_size("1.5", "M") == int(1.5 * 1024 * 1024)

    def test_parse_duration_conversions(self):
        """Test duration parsing with different units."""
        parser = RcloneProgressParser()

        # Test seconds
        assert parser._parse_duration("30s") == 30
        assert parser._parse_duration("30") == 30

        # Test minutes
        assert parser._parse_duration("5m") == 300

        # Test hours
        assert parser._parse_duration("2h") == 7200

        # Test days
        assert parser._parse_duration("1d") == 86400

        # Test invalid
        assert parser._parse_duration("invalid") is None

    def test_complete(self):
        """Test marking progress as complete."""
        parser = RcloneProgressParser()
        parser.init_progress_logger(10, "test")

        # Mock the progress logger
        parser.progress_logger.complete = MagicMock()

        parser.complete()

        assert parser.progress_logger.complete.called

    def test_get_final_stats(self):
        """Test getting final statistics."""
        parser = RcloneProgressParser()

        # Parse some stats
        line = "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete"
        parser.parse_line(line)

        final_stats = parser.get_final_stats()

        assert final_stats.files_transferred == 5
        assert final_stats.files_total == 10
        assert final_stats.percentage == 50.0

    def test_multiple_lines_parsing(self):
        """Test parsing multiple progress lines."""
        parser = RcloneProgressParser()

        lines = [
            "Transferred: 2 / 10 files, 0.5 MiB / 3.0 MiB, 17% complete",
            "ERROR : file1.jpg: permission denied",
            "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete",
            "ERROR : file2.jpg: not found",
            "Transferred: 10 files (3.0 MiB)",
        ]

        for line in lines:
            parser.parse_line(line)

        final_stats = parser.get_final_stats()

        # Should have the final summary stats
        assert final_stats.files_transferred == 10
        assert final_stats.files_total == 10
        assert final_stats.percentage == 100.0
        assert final_stats.errors == 2  # Two error lines
