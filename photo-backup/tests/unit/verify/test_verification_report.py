"""
Unit tests for verification report functionality.

Tests the VerificationReport class and report generation.
"""

import json

from pathlib import Path

from photo_backup.verify import (
    ComparisonResult,
    FileHash,
    FileMismatch,
    RepairResult,
    VerificationReport,
    Verifier,
)


class TestVerificationReportDataclass:
    """Test VerificationReport dataclass."""

    def test_verification_report_instantiation(self):
        """Test that VerificationReport can be instantiated."""
        report = VerificationReport()

        assert report.report_id != ""  # Auto-generated
        assert report.timestamp != ""  # Auto-generated
        assert report.source_path == ""
        assert report.destination == ""
        assert report.verification_passed is False

    def test_verification_report_auto_generates_id(self):
        """Test that report ID is auto-generated and unique."""
        report1 = VerificationReport()
        report2 = VerificationReport()

        # IDs should be unique (using nanoseconds)
        assert report1.report_id != report2.report_id
        assert report1.report_id.startswith("verify-")

    def test_verification_report_auto_generates_timestamp(self):
        """Test that timestamp is auto-generated."""
        report = VerificationReport()

        # Should be ISO format
        assert "T" in report.timestamp
        assert "-" in report.timestamp

    def test_verification_report_preserves_custom_id(self):
        """Test that custom report ID is preserved."""
        report = VerificationReport(report_id="custom-123")

        assert report.report_id == "custom-123"

    def test_verification_report_preserves_custom_timestamp(self):
        """Test that custom timestamp is preserved."""
        custom_ts = "2024-01-15T10:30:00"
        report = VerificationReport(timestamp=custom_ts)

        assert report.timestamp == custom_ts


class TestVerificationReportToDict:
    """Test VerificationReport.to_dict method."""

    def test_to_dict_basic(self):
        """Test basic to_dict conversion."""
        report = VerificationReport(
            report_id="test-123",
            timestamp="2024-01-15T10:00:00",
            source_path="/photos",
            destination="bucket/photos",
            mode="test",
            verification_passed=True,
            total_files_checked=100,
            total_bytes_checked=1000000,
            total_duration_seconds=30.5,
        )

        result = report.to_dict()

        assert result["report_id"] == "test-123"
        assert result["source_path"] == "/photos"
        assert result["verification_passed"] is True
        assert result["total_files_checked"] == 100
        assert result["total_bytes_checked"] == 1000000

    def test_to_dict_with_comparison_result(self):
        """Test to_dict includes comparison results."""
        comparison = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
            mismatched_files=[FileMismatch("c.jpg", "abc", "def", 100, 200, "hash")],
            missing_remote=[FileHash("d.jpg", 300, "ghi")],
            missing_local=[FileHash("e.jpg", 400, "jkl")],
        )

        report = VerificationReport(
            report_id="test-456",
            comparison_result=comparison,
        )

        result = report.to_dict()

        assert "comparison" in result
        assert result["comparison"]["matched_files"] == 2
        assert len(result["comparison"]["mismatched_files"]) == 1
        assert result["comparison"]["mismatched_files"][0]["path"] == "c.jpg"
        assert len(result["comparison"]["missing_remote"]) == 1
        assert len(result["comparison"]["missing_local"]) == 1

    def test_to_dict_with_repair_result(self):
        """Test to_dict includes repair results."""
        repair = RepairResult(
            repaired_files=["a.jpg", "b.jpg"],
            failed_files=[{"path": "c.jpg", "error": "Timeout"}],
            verified_after_repair=["a.jpg", "b.jpg"],
            repair_time_seconds=15.0,
        )

        report = VerificationReport(
            report_id="test-789",
            repair_result=repair,
        )

        result = report.to_dict()

        assert "repair" in result
        assert result["repair"]["repaired_files"] == ["a.jpg", "b.jpg"]
        assert len(result["repair"]["failed_files"]) == 1
        assert result["repair"]["repair_time_seconds"] == 15.0


class TestVerificationReportToJson:
    """Test VerificationReport.to_json method."""

    def test_to_json_valid_json(self):
        """Test to_json produces valid JSON."""
        report = VerificationReport(
            report_id="test-json",
            source_path="/photos",
            verification_passed=True,
        )

        json_str = report.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["report_id"] == "test-json"

    def test_to_json_with_indent(self):
        """Test to_json respects indent parameter."""
        report = VerificationReport(report_id="test-indent")

        json_no_indent = report.to_json(indent=0)
        json_with_indent = report.to_json(indent=4)

        # Indented version should be longer
        assert len(json_with_indent) > len(json_no_indent)


class TestVerificationReportToText:
    """Test VerificationReport.to_text method."""

    def test_to_text_basic_format(self):
        """Test to_text produces readable output."""
        report = VerificationReport(
            report_id="test-text",
            source_path="/photos",
            destination="bucket/photos",
            mode="test",
            verification_passed=True,
            total_files_checked=100,
            total_bytes_checked=1048576,  # 1 MB
            total_duration_seconds=30.0,
        )

        text = report.to_text()

        assert "VERIFICATION REPORT" in text
        assert "test-text" in text
        assert "/photos" in text
        assert "PASSED" in text
        assert "100" in text

    def test_to_text_shows_failed_status(self):
        """Test to_text shows FAILED status."""
        report = VerificationReport(
            verification_passed=False,
        )

        text = report.to_text()

        assert "FAILED" in text

    def test_to_text_includes_comparison_details(self):
        """Test to_text includes comparison details."""
        comparison = ComparisonResult(
            matched_files=["a.jpg"],
            mismatched_files=[FileMismatch("bad.jpg", "local123", "remote456", 100, 100, "hash")],
            missing_remote=[FileHash("missing.jpg", 200, "abc")],
        )

        report = VerificationReport(
            comparison_result=comparison,
        )

        text = report.to_text()

        assert "COMPARISON RESULTS" in text
        assert "Matched files: 1" in text
        assert "Mismatched files: 1" in text
        assert "bad.jpg" in text
        assert "local123" in text
        assert "remote456" in text
        assert "missing.jpg" in text

    def test_to_text_includes_repair_details(self):
        """Test to_text includes repair details."""
        repair = RepairResult(
            repaired_files=["fixed.jpg"],
            failed_files=[],
            verified_after_repair=["fixed.jpg"],
        )

        report = VerificationReport(
            repair_result=repair,
        )

        text = report.to_text()

        assert "REPAIR RESULTS" in text
        assert "Repaired: 1" in text

    def test_to_text_includes_errors(self):
        """Test to_text includes errors."""
        report = VerificationReport(
            errors=["Connection failed", "Timeout occurred"],
        )

        text = report.to_text()

        assert "ERRORS" in text
        assert "Connection failed" in text
        assert "Timeout occurred" in text

    def test_to_text_truncates_long_lists(self):
        """Test to_text truncates very long lists."""
        comparison = ComparisonResult(
            mismatched_files=[FileMismatch(f"file{i}.jpg", "a", "b", 100, 100, "hash") for i in range(20)],
        )

        report = VerificationReport(
            comparison_result=comparison,
        )

        text = report.to_text()

        # Should show truncation message
        assert "... and" in text
        assert "more" in text


class TestVerificationReportSaveToFile:
    """Test VerificationReport.save_to_file method."""

    def test_save_to_file_json(self, tmp_path):
        """Test saving report as JSON file."""
        report = VerificationReport(
            report_id="save-test",
            source_path="/photos",
            verification_passed=True,
        )

        file_path = tmp_path / "report.json"
        result = report.save_to_file(file_path, format="json")

        assert result is True
        assert file_path.exists()

        # Verify content is valid JSON
        content = file_path.read_text()
        parsed = json.loads(content)
        assert parsed["report_id"] == "save-test"

    def test_save_to_file_text(self, tmp_path):
        """Test saving report as text file."""
        report = VerificationReport(
            report_id="text-test",
            verification_passed=True,
        )

        file_path = tmp_path / "report.txt"
        result = report.save_to_file(file_path, format="text")

        assert result is True
        assert file_path.exists()

        content = file_path.read_text()
        assert "VERIFICATION REPORT" in content

    def test_save_to_file_creates_directories(self, tmp_path):
        """Test that save_to_file creates parent directories."""
        report = VerificationReport(report_id="nested-test")

        file_path = tmp_path / "nested" / "dirs" / "report.json"
        result = report.save_to_file(file_path)

        assert result is True
        assert file_path.exists()

    def test_save_to_file_accepts_string_path(self, tmp_path):
        """Test that save_to_file accepts string path."""
        report = VerificationReport(report_id="string-path-test")

        file_path = str(tmp_path / "report.json")
        result = report.save_to_file(file_path)

        assert result is True
        assert Path(file_path).exists()


class TestVerificationReportFormatBytes:
    """Test VerificationReport._format_bytes static method."""

    def test_format_bytes_small(self):
        """Test formatting small byte values."""
        assert VerificationReport._format_bytes(100) == "100.0 B"

    def test_format_bytes_kilobytes(self):
        """Test formatting kilobyte values."""
        result = VerificationReport._format_bytes(1024)
        assert "KB" in result

    def test_format_bytes_megabytes(self):
        """Test formatting megabyte values."""
        result = VerificationReport._format_bytes(1024 * 1024)
        assert "MB" in result

    def test_format_bytes_gigabytes(self):
        """Test formatting gigabyte values."""
        result = VerificationReport._format_bytes(1024 * 1024 * 1024)
        assert "GB" in result


class TestVerifierGenerateReport:
    """Test Verifier.generate_report method."""

    def test_generate_report_basic(self):
        """Test basic report generation."""
        verifier = Verifier(test_mode=True)

        comparison = ComparisonResult(
            matched_files=["a.jpg", "b.jpg"],
        )

        report = verifier.generate_report(comparison)

        assert report.comparison_result == comparison
        assert report.repair_result is None
        assert report.mode == "test"
        assert report.verification_passed is True

    def test_generate_report_with_issues(self):
        """Test report generation with issues."""
        verifier = Verifier(test_mode=True)

        comparison = ComparisonResult(
            matched_files=["a.jpg"],
            mismatched_files=[FileMismatch("b.jpg", "abc", "def", 100, 100, "hash")],
        )

        report = verifier.generate_report(comparison)

        assert report.verification_passed is False

    def test_generate_report_with_repair(self):
        """Test report generation with repair result."""
        verifier = Verifier(test_mode=True)

        comparison = ComparisonResult(
            mismatched_files=[FileMismatch("b.jpg", "abc", "def", 100, 100, "hash")],
        )

        repair = RepairResult(
            repaired_files=["b.jpg"],
            verified_after_repair=["b.jpg"],
        )

        report = verifier.generate_report(comparison, repair)

        assert report.repair_result == repair
        assert report.verification_passed is True  # All repaired and verified

    def test_generate_report_with_local_files_for_bytes(self):
        """Test report calculates total bytes from local files."""
        verifier = Verifier(test_mode=True)

        comparison = ComparisonResult(matched_files=["a.jpg", "b.jpg"])

        local_files = [
            FileHash("a.jpg", 1000, "abc"),
            FileHash("b.jpg", 2000, "def"),
        ]

        report = verifier.generate_report(comparison, local_files=local_files)

        assert report.total_bytes_checked == 3000

    def test_generate_report_calculates_duration(self):
        """Test report calculates total duration."""
        verifier = Verifier(test_mode=True)

        comparison = ComparisonResult(
            matched_files=["a.jpg"],
            comparison_time_seconds=10.0,
        )

        repair = RepairResult(
            repaired_files=["b.jpg"],
            repair_time_seconds=5.0,
        )

        report = verifier.generate_report(comparison, repair)

        assert report.total_duration_seconds == 15.0
