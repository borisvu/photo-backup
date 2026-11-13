"""
Unit tests for repair functionality.

Tests the repair_files method and RepairResult dataclass.
"""

from unittest.mock import MagicMock, patch

from photo_backup.verify import (
    ComparisonResult,
    FileHash,
    FileMismatch,
    RepairResult,
    Verifier,
)


class TestRepairResultDataclass:
    """Test RepairResult dataclass."""

    def test_repair_result_instantiation(self):
        """Test that RepairResult can be instantiated."""
        result = RepairResult()

        assert result.repaired_files == []
        assert result.failed_files == []
        assert result.verified_after_repair == []
        assert result.repair_time_seconds == 0.0

    def test_repair_result_success_property_all_repaired(self):
        """Test success property when all files repaired."""
        result = RepairResult(
            repaired_files=["a.jpg", "b.jpg"],
            failed_files=[],
        )

        assert result.success is True

    def test_repair_result_success_property_partial(self):
        """Test success property with partial failures."""
        result = RepairResult(
            repaired_files=["a.jpg"],
            failed_files=[{"path": "b.jpg", "error": "Upload failed"}],
        )

        assert result.success is False

    def test_repair_result_success_property_all_failed(self):
        """Test success property when all failed."""
        result = RepairResult(
            repaired_files=[],
            failed_files=[{"path": "a.jpg", "error": "Error"}],
        )

        assert result.success is False

    def test_repair_result_success_property_empty(self):
        """Test success property with no files to repair."""
        result = RepairResult()

        # No files repaired and no failures means no work was done
        assert result.success is False

    def test_repair_result_all_verified_property(self):
        """Test all_verified property."""
        result = RepairResult(
            repaired_files=["a.jpg", "b.jpg"],
            verified_after_repair=["a.jpg", "b.jpg"],
        )

        assert result.all_verified is True

    def test_repair_result_all_verified_property_partial(self):
        """Test all_verified property with partial verification."""
        result = RepairResult(
            repaired_files=["a.jpg", "b.jpg"],
            verified_after_repair=["a.jpg"],  # Only one verified
        )

        assert result.all_verified is False

    def test_repair_result_get_summary(self):
        """Test get_summary method."""
        result = RepairResult(
            repaired_files=["a.jpg", "b.jpg"],
            failed_files=[],
            verified_after_repair=["a.jpg", "b.jpg"],
            repair_time_seconds=5.5,
        )

        summary = result.get_summary()

        assert "SUCCESS" in summary
        assert "Repaired: 2" in summary
        assert "Failed: 0" in summary
        assert "Verified after repair: 2" in summary
        assert "5.5" in summary

    def test_repair_result_get_summary_partial(self):
        """Test get_summary with partial failures."""
        result = RepairResult(
            repaired_files=["a.jpg"],
            failed_files=[{"path": "b.jpg", "error": "Network error"}],
            repair_time_seconds=3.0,
        )

        summary = result.get_summary()

        assert "PARTIAL" in summary
        assert "Repaired: 1" in summary
        assert "Failed: 1" in summary
        assert "b.jpg" in summary
        assert "Network error" in summary

    def test_repair_result_get_summary_all_failed(self):
        """Test get_summary when all repairs failed."""
        result = RepairResult(
            repaired_files=[],
            failed_files=[{"path": "a.jpg", "error": "Error"}],
        )

        summary = result.get_summary()

        assert "FAILED" in summary


class TestVerifierRepairFiles:
    """Test Verifier.repair_files method."""

    def test_repair_files_no_issues(self, tmp_path):
        """Test repair_files when there are no issues."""
        verifier = Verifier(test_mode=True)

        comparison_result = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
        )

        result = verifier.repair_files(comparison_result, str(tmp_path))

        assert result.repaired_files == []
        assert result.failed_files == []

    def test_repair_files_collects_files_to_repair(self, tmp_path):
        """Test that repair_files identifies files needing repair."""
        # Create test file
        (tmp_path / "mismatch.jpg").write_bytes(b"test content")
        (tmp_path / "missing.jpg").write_bytes(b"missing content")

        verifier = Verifier(test_mode=True)

        comparison_result = ComparisonResult(
            matched_files=["ok.jpg"],
            mismatched_files=[FileMismatch("mismatch.jpg", "local_hash", "remote_hash", 100, 100, "hash")],
            missing_remote=[FileHash("missing.jpg", 100, "hash123")],
        )

        # Mock the repair and verify methods to avoid actual rclone calls
        with (
            patch.object(verifier, "_repair_single_file", return_value=True) as mock_repair,
            patch.object(verifier, "_verify_repaired_file", return_value=True),
        ):
            verifier.repair_files(
                comparison_result,
                str(tmp_path),
                verify_after_repair=False,
            )

        # Should have attempted to repair both files
        assert mock_repair.call_count == 2

    def test_repair_files_handles_missing_source_file(self, tmp_path):
        """Test repair_files handles missing source files gracefully."""
        verifier = Verifier(test_mode=True)

        comparison_result = ComparisonResult(
            mismatched_files=[FileMismatch("nonexistent.jpg", "abc", "def", 100, 100, "hash")],
        )

        # The actual repair will fail because file doesn't exist
        result = verifier.repair_files(comparison_result, str(tmp_path))

        assert len(result.failed_files) == 1
        assert result.failed_files[0]["path"] == "nonexistent.jpg"

    def test_repair_files_with_verification(self, tmp_path):
        """Test repair_files with verification enabled."""
        # Create test file
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        verifier = Verifier(test_mode=True)

        comparison_result = ComparisonResult(
            mismatched_files=[FileMismatch("test.jpg", "abc", "def", 100, 100, "hash")],
        )

        with (
            patch.object(verifier, "_repair_single_file", return_value=True),
            patch.object(verifier, "_verify_repaired_file", return_value=True) as mock_verify,
        ):
            result = verifier.repair_files(
                comparison_result,
                str(tmp_path),
                verify_after_repair=True,
            )

        assert mock_verify.called
        assert "test.jpg" in result.verified_after_repair

    def test_repair_files_records_timing(self, tmp_path):
        """Test that repair_files records execution time."""
        verifier = Verifier(test_mode=True)

        comparison_result = ComparisonResult(
            matched_files=["a.jpg"],
        )

        result = verifier.repair_files(comparison_result, str(tmp_path))

        assert result.repair_time_seconds >= 0


class TestVerifierRepairSingleFile:
    """Test Verifier._repair_single_file method."""

    def test_repair_single_file_missing_local(self, tmp_path):
        """Test _repair_single_file fails for missing local file."""
        verifier = Verifier(test_mode=True)

        result = verifier._repair_single_file(str(tmp_path), "nonexistent.jpg")

        assert result is False

    def test_repair_single_file_calls_rclone(self, tmp_path):
        """Test _repair_single_file calls rclone copyto."""
        # Create test file
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        verifier = Verifier(test_mode=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            result = verifier._repair_single_file(str(tmp_path), "test.jpg")

        assert result is True
        assert mock_run.called

        # Check command includes copyto
        call_args = mock_run.call_args[0][0]
        assert "rclone" in call_args
        assert "copyto" in call_args

    def test_repair_single_file_handles_rclone_failure(self, tmp_path):
        """Test _repair_single_file handles rclone failure."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        verifier = Verifier(test_mode=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Connection refused")

            result = verifier._repair_single_file(str(tmp_path), "test.jpg")

        assert result is False

    def test_repair_single_file_handles_timeout(self, tmp_path):
        """Test _repair_single_file handles timeout."""
        import subprocess

        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        verifier = Verifier(test_mode=True)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="rclone", timeout=120)

            result = verifier._repair_single_file(str(tmp_path), "test.jpg")

        assert result is False


class TestVerifierVerifyRepairedFile:
    """Test Verifier._verify_repaired_file method."""

    def test_verify_repaired_file_matching_hashes(self, tmp_path):
        """Test _verify_repaired_file returns True for matching hashes."""
        test_file = tmp_path / "test.jpg"
        test_content = b"test content for hashing"
        test_file.write_bytes(test_content)

        verifier = Verifier(test_mode=True)

        # Calculate expected hash
        import hashlib

        expected_hash = hashlib.md5(test_content).hexdigest()

        with patch("subprocess.run") as mock_run:
            # Return the same hash from "remote"
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"{expected_hash}  test.jpg\n",
            )

            result = verifier._verify_repaired_file(str(tmp_path), "test.jpg")

        assert result is True

    def test_verify_repaired_file_mismatched_hashes(self, tmp_path):
        """Test _verify_repaired_file returns False for mismatched hashes."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        verifier = Verifier(test_mode=True)

        with patch("subprocess.run") as mock_run:
            # Return different hash from "remote"
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="different_hash_value  test.jpg\n",
            )

            result = verifier._verify_repaired_file(str(tmp_path), "test.jpg")

        assert result is False

    def test_verify_repaired_file_rclone_failure(self, tmp_path):
        """Test _verify_repaired_file handles rclone failure."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        verifier = Verifier(test_mode=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            result = verifier._verify_repaired_file(str(tmp_path), "test.jpg")

        assert result is False
