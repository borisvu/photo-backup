#!/usr/bin/env python3
"""
Unit tests for verification CLI commands.

Task 99: Add Verify Command - Unit tests.
"""

from unittest.mock import Mock, patch

from click.testing import CliRunner

from photo_backup.main import main
from photo_backup.verify import ComparisonResult, FileHash, RepairResult, VerificationReport


class TestVerifyCommand:
    """Test verification CLI command."""

    def test_verify_help(self):
        """Test that verify command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["verify", "--help"])

        assert result.exit_code == 0
        assert "verify" in result.output
        assert "Verify backup integrity" in result.output
        assert "--repair" in result.output
        assert "--save-report" in result.output
        assert "--verbose" in result.output

    def test_verify_success_no_issues(self):
        """Test verify command when all files match."""
        runner = CliRunner()

        # Mock the Verifier
        mock_verifier = Mock()
        mock_verifier.get_verification_info.return_value = {
            "mode": "test",
            "source_path": "/tmp/photos",
            "destination": "test:bucket/photos",
            "endpoint": "localhost:9000",
            "credential_status": {"available": True},
        }

        # Mock local files
        local_files = [
            FileHash(path="photo1.jpg", size=1000, hash_md5="abc123"),
            FileHash(path="photo2.jpg", size=2000, hash_md5="def456"),
        ]
        mock_verifier.calculate_local_hashes.return_value = local_files

        # Mock remote files (same as local)
        remote_files = [
            FileHash(path="photo1.jpg", size=1000, hash_md5="abc123"),
            FileHash(path="photo2.jpg", size=2000, hash_md5="def456"),
        ]
        mock_verifier.list_remote_files.return_value = remote_files

        # Mock comparison result (all matched)
        comparison_result = ComparisonResult(
            matched_files=["photo1.jpg", "photo2.jpg"],
            mismatched_files=[],
            missing_remote=[],
            missing_local=[],
            comparison_time_seconds=0.5,
        )
        mock_verifier.compare_hashes.return_value = comparison_result

        # Mock report
        report = VerificationReport(
            source_path="/tmp/photos",
            destination="test:bucket/photos",
            mode="test",
            comparison_result=comparison_result,
            total_files_checked=2,
            total_bytes_checked=3000,
            verification_passed=True,
            total_duration_seconds=1.0,
        )
        mock_verifier.generate_report.return_value = report

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "verify"])

            assert result.exit_code == 0
            assert "VERIFICATION PASSED" in result.output
            assert "Matched files: 2" in result.output

    def test_verify_with_mismatches(self):
        """Test verify command when there are mismatches."""
        runner = CliRunner()

        mock_verifier = Mock()
        mock_verifier.get_verification_info.return_value = {
            "mode": "test",
            "source_path": "/tmp/photos",
            "destination": "test:bucket/photos",
            "endpoint": "localhost:9000",
            "credential_status": {"available": True},
        }

        local_files = [
            FileHash(path="photo1.jpg", size=1000, hash_md5="abc123"),
            FileHash(path="photo2.jpg", size=2000, hash_md5="def456"),
        ]
        mock_verifier.calculate_local_hashes.return_value = local_files

        remote_files = [
            FileHash(path="photo1.jpg", size=1000, hash_md5="abc123"),
            FileHash(path="photo2.jpg", size=2000, hash_md5="different"),  # Mismatch
        ]
        mock_verifier.list_remote_files.return_value = remote_files

        from photo_backup.verify import FileMismatch

        comparison_result = ComparisonResult(
            matched_files=["photo1.jpg"],
            mismatched_files=[
                FileMismatch(
                    path="photo2.jpg",
                    local_hash="def456",
                    remote_hash="different",
                    local_size=2000,
                    remote_size=2000,
                    mismatch_type="hash",
                )
            ],
            missing_remote=[],
            missing_local=[],
            comparison_time_seconds=0.5,
        )
        mock_verifier.compare_hashes.return_value = comparison_result

        report = VerificationReport(
            source_path="/tmp/photos",
            destination="test:bucket/photos",
            mode="test",
            comparison_result=comparison_result,
            total_files_checked=2,
            total_bytes_checked=3000,
            verification_passed=False,
            total_duration_seconds=1.0,
        )
        mock_verifier.generate_report.return_value = report

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "verify"])

            assert result.exit_code == 1
            assert "VERIFICATION FAILED" in result.output
            assert "Mismatched files: 1" in result.output

    def test_verify_with_repair(self):
        """Test verify command with repair option."""
        runner = CliRunner()

        mock_verifier = Mock()
        mock_verifier.get_verification_info.return_value = {
            "mode": "test",
            "source_path": "/tmp/photos",
            "destination": "test:bucket/photos",
            "endpoint": "localhost:9000",
            "credential_status": {"available": True},
        }

        local_files = [FileHash(path="photo1.jpg", size=1000, hash_md5="abc123")]
        mock_verifier.calculate_local_hashes.return_value = local_files
        mock_verifier.list_remote_files.return_value = []

        # Missing on remote
        comparison_result = ComparisonResult(
            matched_files=[],
            mismatched_files=[],
            missing_remote=[FileHash(path="photo1.jpg", size=1000, hash_md5="abc123")],
            missing_local=[],
            comparison_time_seconds=0.5,
        )
        mock_verifier.compare_hashes.return_value = comparison_result

        # Mock successful repair
        repair_result = RepairResult(
            repaired_files=["photo1.jpg"],
            failed_files=[],
            verified_after_repair=["photo1.jpg"],
            repair_time_seconds=2.0,
        )
        mock_verifier.repair_files.return_value = repair_result

        report = VerificationReport(
            source_path="/tmp/photos",
            destination="test:bucket/photos",
            mode="test",
            comparison_result=comparison_result,
            repair_result=repair_result,
            total_files_checked=1,
            total_bytes_checked=1000,
            verification_passed=True,
            total_duration_seconds=3.0,
        )
        mock_verifier.generate_report.return_value = report

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "verify", "--repair"])

            assert result.exit_code == 0
            assert "REPAIR RESULTS" in result.output
            assert "Repaired: 1" in result.output
            assert "VERIFICATION PASSED (after repair)" in result.output

    def test_verify_verbose(self):
        """Test verify command with verbose flag."""
        runner = CliRunner()

        mock_verifier = Mock()
        mock_verifier.get_verification_info.return_value = {
            "mode": "test",
            "source_path": "/tmp/photos",
            "destination": "test:bucket/photos",
            "endpoint": "localhost:9000",
            "credential_status": {"available": True, "source": "direct"},
        }

        local_files = [FileHash(path="photo1.jpg", size=1000, hash_md5="abc123")]
        mock_verifier.calculate_local_hashes.return_value = local_files
        mock_verifier.list_remote_files.return_value = local_files

        comparison_result = ComparisonResult(
            matched_files=["photo1.jpg"],
            comparison_time_seconds=0.5,
        )
        mock_verifier.compare_hashes.return_value = comparison_result

        report = VerificationReport(
            source_path="/tmp/photos",
            destination="test:bucket/photos",
            mode="test",
            comparison_result=comparison_result,
            verification_passed=True,
            total_duration_seconds=1.0,
        )
        mock_verifier.generate_report.return_value = report

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "verify", "--verbose"])

            assert result.exit_code == 0
            # Verbose shows endpoint and credential status
            assert "Endpoint:" in result.output
            assert "localhost:9000" in result.output

    def test_verify_dry_run_with_repair(self):
        """Test verify command with dry run and repair options."""
        runner = CliRunner()

        mock_verifier = Mock()
        mock_verifier.get_verification_info.return_value = {
            "mode": "test",
            "source_path": "/tmp/photos",
            "destination": "test:bucket/photos",
            "endpoint": "localhost:9000",
            "credential_status": {"available": True},
        }

        local_files = [FileHash(path="photo1.jpg", size=1000, hash_md5="abc123")]
        mock_verifier.calculate_local_hashes.return_value = local_files
        mock_verifier.list_remote_files.return_value = []

        comparison_result = ComparisonResult(
            matched_files=[],
            mismatched_files=[],
            missing_remote=[FileHash(path="photo1.jpg", size=1000, hash_md5="abc123")],
            missing_local=[],
            comparison_time_seconds=0.5,
        )
        mock_verifier.compare_hashes.return_value = comparison_result

        report = VerificationReport(
            source_path="/tmp/photos",
            destination="test:bucket/photos",
            mode="test",
            comparison_result=comparison_result,
            verification_passed=False,
            total_duration_seconds=1.0,
        )
        mock_verifier.generate_report.return_value = report

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "--dry-run", "verify", "--repair"])

            # Should show dry run message instead of actually repairing
            assert "DRY RUN - Would repair" in result.output
            # Should NOT call repair_files
            mock_verifier.repair_files.assert_not_called()

    def test_verify_save_report(self):
        """Test verify command with save-report option."""
        runner = CliRunner()

        mock_verifier = Mock()
        mock_verifier.get_verification_info.return_value = {
            "mode": "test",
            "source_path": "/tmp/photos",
            "destination": "test:bucket/photos",
            "endpoint": "localhost:9000",
            "credential_status": {"available": True},
        }

        local_files = [FileHash(path="photo1.jpg", size=1000, hash_md5="abc123")]
        mock_verifier.calculate_local_hashes.return_value = local_files
        mock_verifier.list_remote_files.return_value = local_files

        comparison_result = ComparisonResult(matched_files=["photo1.jpg"], comparison_time_seconds=0.5)
        mock_verifier.compare_hashes.return_value = comparison_result

        report = Mock()
        report.verification_passed = True
        report.total_duration_seconds = 1.0
        report.report_id = "verify-123456"
        report.save_to_file.return_value = True
        mock_verifier.generate_report.return_value = report

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "verify", "--save-report"])

            assert result.exit_code == 0
            assert "Report saved to:" in result.output
            report.save_to_file.assert_called_once()

    def test_verify_config_error(self):
        """Test verify command with configuration error."""
        runner = CliRunner()

        with patch("photo_backup.cli.verify_commands.Config") as mock_config_cls:
            mock_config = Mock()
            mock_config.load_config.side_effect = ValueError("Invalid configuration")
            mock_config_cls.return_value = mock_config

            result = runner.invoke(main, ["--test-mode", "verify"])

            assert result.exit_code == 1
            assert "Configuration Error" in result.output

    def test_verify_exception_handling(self):
        """Test verify command exception handling."""
        runner = CliRunner()

        mock_verifier = Mock()
        mock_verifier.get_verification_info.side_effect = Exception("Connection failed")

        with (
            patch("photo_backup.cli.verify_commands.Verifier", return_value=mock_verifier),
            patch("photo_backup.cli.verify_commands._get_logger") as mock_get_logger,
        ):
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = runner.invoke(main, ["--test-mode", "verify"])

            assert result.exit_code == 1
            assert "Unexpected error" in result.output
