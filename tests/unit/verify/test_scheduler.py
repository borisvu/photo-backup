#!/usr/bin/env python3
"""
Unit tests for the VerificationScheduler.

Add Scheduled Verification - Unit tests.
"""

import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from pathlib import Path

from photo_backup.verify.scheduler import (
    DEFAULT_VERIFICATION_INTERVAL_DAYS,
    TEST_VERIFICATION_INTERVAL_DAYS,
    VERIFICATION_STATE_FILENAME,
    ScheduledVerificationResult,
    VerificationScheduler,
    VerificationScheduleState,
)


class TestVerificationScheduleState:
    """Tests for VerificationScheduleState dataclass."""

    def test_default_state(self):
        """Test default state initialization."""
        state = VerificationScheduleState()

        assert state.last_verification_time is None
        assert state.last_verification_passed is None
        assert state.last_report_id is None
        assert state.next_scheduled_time is None
        assert state.total_verifications == 0
        assert state.failed_verifications == 0

    def test_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime.now()
        state = VerificationScheduleState(
            last_verification_time=now,
            last_verification_passed=True,
            last_report_id="test-report-123",
            next_scheduled_time=now + timedelta(days=30),
            total_verifications=5,
            failed_verifications=1,
        )

        data = state.to_dict()

        assert data["last_verification_time"] == now.isoformat()
        assert data["last_verification_passed"] is True
        assert data["last_report_id"] == "test-report-123"
        assert data["next_scheduled_time"] == (now + timedelta(days=30)).isoformat()
        assert data["total_verifications"] == 5
        assert data["failed_verifications"] == 1

    def test_to_dict_with_none_values(self):
        """Test serialization with None values."""
        state = VerificationScheduleState()
        data = state.to_dict()

        assert data["last_verification_time"] is None
        assert data["last_verification_passed"] is None
        assert data["next_scheduled_time"] is None

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        now = datetime.now()
        data = {
            "last_verification_time": now.isoformat(),
            "last_verification_passed": False,
            "last_report_id": "report-456",
            "next_scheduled_time": (now + timedelta(days=1)).isoformat(),
            "total_verifications": 10,
            "failed_verifications": 2,
        }

        state = VerificationScheduleState.from_dict(data)

        # Note: datetime comparison needs to handle microseconds
        assert state.last_verification_time.isoformat() == now.isoformat()
        assert state.last_verification_passed is False
        assert state.last_report_id == "report-456"
        assert state.total_verifications == 10
        assert state.failed_verifications == 2

    def test_from_dict_with_missing_fields(self):
        """Test deserialization with missing optional fields."""
        data = {}
        state = VerificationScheduleState.from_dict(data)

        assert state.last_verification_time is None
        assert state.last_verification_passed is None
        assert state.total_verifications == 0

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        now = datetime.now().replace(microsecond=0)  # Remove microseconds for clean comparison
        original = VerificationScheduleState(
            last_verification_time=now,
            last_verification_passed=True,
            last_report_id="roundtrip-test",
            next_scheduled_time=now + timedelta(days=7),
            total_verifications=3,
            failed_verifications=0,
        )

        data = original.to_dict()
        restored = VerificationScheduleState.from_dict(data)

        assert restored.last_verification_time == original.last_verification_time
        assert restored.last_verification_passed == original.last_verification_passed
        assert restored.last_report_id == original.last_report_id
        assert restored.total_verifications == original.total_verifications


class TestScheduledVerificationResult:
    """Tests for ScheduledVerificationResult dataclass."""

    def test_default_result(self):
        """Test default result initialization."""
        result = ScheduledVerificationResult()

        assert result.ran is False
        assert result.passed is None
        assert result.report_id is None
        assert result.skipped_reason is None
        assert result.duration_seconds == 0.0
        assert result.errors == []

    def test_skipped_summary(self):
        """Test summary for skipped verification."""
        result = ScheduledVerificationResult(
            ran=False,
            skipped_reason="Not due yet (12.5 hours remaining)",
        )

        summary = result.get_summary()
        assert "skipped" in summary.lower()
        assert "Not due yet" in summary

    def test_passed_summary(self):
        """Test summary for passed verification."""
        result = ScheduledVerificationResult(
            ran=True,
            passed=True,
            report_id="test-report",
            duration_seconds=45.3,
        )

        summary = result.get_summary()
        assert "PASSED" in summary
        assert "45.3" in summary
        assert "test-report" in summary

    def test_failed_summary(self):
        """Test summary for failed verification."""
        result = ScheduledVerificationResult(
            ran=True,
            passed=False,
            report_id="fail-report",
            duration_seconds=120.0,
            errors=["Connection failed"],
        )

        summary = result.get_summary()
        assert "FAILED" in summary


class TestVerificationScheduler:
    """Tests for VerificationScheduler class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        config.test_mode = True
        config.is_test_mode.return_value = True
        config.get.return_value = None
        return config

    @pytest.fixture
    def temp_state_dir(self):
        """Create a temporary state directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_init_test_mode(self, mock_config):
        """Test initialization in test mode."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(config=mock_config, test_mode=True)

            assert scheduler.test_mode is True
            assert scheduler.interval_days == TEST_VERIFICATION_INTERVAL_DAYS

    def test_init_production_mode(self, mock_config):
        """Test initialization in production mode."""
        mock_config.test_mode = False
        mock_config.is_test_mode.return_value = False

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(config=mock_config, test_mode=False)

            assert scheduler.test_mode is False
            assert scheduler.interval_days == DEFAULT_VERIFICATION_INTERVAL_DAYS

    def test_init_custom_interval(self, mock_config):
        """Test initialization with custom interval."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=7,
            )

            assert scheduler.interval_days == 7

    def test_interval_timedelta(self, mock_config):
        """Test interval_timedelta property."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=5,
            )

            assert scheduler.interval_timedelta == timedelta(days=5)

    def test_is_verification_due_never_run(self, mock_config):
        """Test verification is due when never run before."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(config=mock_config, test_mode=True)

            assert scheduler.is_verification_due() is True

    def test_is_verification_due_recently_run(self, mock_config):
        """Test verification is not due when recently run."""
        # Set last run to 1 hour ago
        last_run = datetime.now() - timedelta(hours=1)
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            assert scheduler.is_verification_due() is False

    def test_is_verification_due_overdue(self, mock_config):
        """Test verification is due when overdue."""
        # Set last run to 2 days ago (with 1-day interval)
        last_run = datetime.now() - timedelta(days=2)
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            assert scheduler.is_verification_due() is True

    def test_is_verification_due_with_reference_time(self, mock_config):
        """Test verification due check with custom reference time."""
        last_run = datetime.now() - timedelta(hours=12)
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            # With reference time 2 days in the future, should be due
            future_time = datetime.now() + timedelta(days=2)
            assert scheduler.is_verification_due(reference_time=future_time) is True

    def test_get_next_scheduled_time(self, mock_config):
        """Test getting next scheduled time."""
        last_run = datetime.now() - timedelta(hours=6)
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            next_time = scheduler.get_next_scheduled_time()
            assert next_time is not None
            expected = last_run + timedelta(days=1)
            # Compare with some tolerance for microseconds
            assert abs((next_time - expected).total_seconds()) < 1

    def test_get_next_scheduled_time_never_run(self, mock_config):
        """Test next scheduled time when never run."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(config=mock_config, test_mode=True)

            assert scheduler.get_next_scheduled_time() is None

    def test_get_time_until_next(self, mock_config):
        """Test getting time until next verification."""
        # Set last run to now, so next is in 1 day
        last_run = datetime.now()
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            time_until = scheduler.get_time_until_next()
            assert time_until is not None
            # Should be close to 1 day
            assert 0.99 * 24 * 3600 < time_until.total_seconds() < 1.01 * 24 * 3600

    def test_get_schedule_info(self, mock_config):
        """Test getting comprehensive schedule info."""
        last_run = datetime.now() - timedelta(hours=12)
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "last_verification_passed": True,
            "last_report_id": "info-test",
            "total_verifications": 10,
            "failed_verifications": 2,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            info = scheduler.get_schedule_info()

            assert info["mode"] == "test"
            assert info["interval_days"] == 1
            assert info["is_due"] is False
            assert info["last_verification_passed"] is True
            assert info["last_report_id"] == "info-test"
            assert info["total_verifications"] == 10
            assert info["failed_verifications"] == 2
            assert info["success_rate"] == 80.0  # (10-2)/10 * 100

    def test_run_scheduled_verification_not_due(self, mock_config):
        """Test that verification is skipped when not due."""
        last_run = datetime.now()
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            result = scheduler.run_scheduled_verification()

            assert result.ran is False
            assert "Not due yet" in result.skipped_reason

    def test_run_scheduled_verification_forced(self, mock_config):
        """Test forced verification run."""
        last_run = datetime.now()
        state_data = {
            "last_verification_time": last_run.isoformat(),
            "total_verifications": 1,
        }

        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
            patch("photo_backup.verify.scheduler.Verifier") as mock_verifier_class,
        ):
            mock_load.return_value = (state_data, None)
            mock_save.return_value = (True, None)

            # Mock the verifier
            mock_verifier = MagicMock()
            mock_report = MagicMock()
            mock_report.verification_passed = True
            mock_report.report_id = "forced-report"
            mock_report.total_duration_seconds = 30.0
            mock_report.errors = []
            mock_verifier.run_full_verification.return_value = mock_report
            mock_verifier_class.return_value = mock_verifier

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            result = scheduler.run_scheduled_verification(force=True)

            assert result.ran is True
            assert result.passed is True
            assert result.report_id == "forced-report"

    def test_run_scheduled_verification_when_due(self, mock_config):
        """Test verification runs when due."""
        # Never run before
        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
            patch("photo_backup.verify.scheduler.Verifier") as mock_verifier_class,
        ):
            mock_load.return_value = (None, "No file")
            mock_save.return_value = (True, None)

            # Mock the verifier
            mock_verifier = MagicMock()
            mock_report = MagicMock()
            mock_report.verification_passed = True
            mock_report.report_id = "due-report"
            mock_report.total_duration_seconds = 45.0
            mock_report.errors = []
            mock_verifier.run_full_verification.return_value = mock_report
            mock_verifier_class.return_value = mock_verifier

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            result = scheduler.run_scheduled_verification()

            assert result.ran is True
            assert result.passed is True
            mock_verifier.run_full_verification.assert_called_once_with(
                repair=False,
                save_report=True,
            )

    def test_run_scheduled_verification_failed(self, mock_config):
        """Test verification failure is tracked."""
        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
            patch("photo_backup.verify.scheduler.Verifier") as mock_verifier_class,
        ):
            mock_load.return_value = (None, "No file")
            mock_save.return_value = (True, None)

            # Mock the verifier to return failed verification
            mock_verifier = MagicMock()
            mock_report = MagicMock()
            mock_report.verification_passed = False
            mock_report.report_id = "failed-report"
            mock_report.total_duration_seconds = 60.0
            mock_report.errors = ["Hash mismatch detected"]
            mock_verifier.run_full_verification.return_value = mock_report
            mock_verifier_class.return_value = mock_verifier

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            result = scheduler.run_scheduled_verification()

            assert result.ran is True
            assert result.passed is False
            assert "Hash mismatch detected" in result.errors
            assert scheduler.state.failed_verifications == 1

    def test_run_scheduled_verification_exception(self, mock_config):
        """Test verification handles exceptions gracefully."""
        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
            patch("photo_backup.verify.scheduler.Verifier") as mock_verifier_class,
        ):
            mock_load.return_value = (None, "No file")
            mock_save.return_value = (True, None)

            # Mock the verifier to raise exception
            mock_verifier_class.side_effect = RuntimeError("Connection failed")

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            result = scheduler.run_scheduled_verification()

            assert result.ran is True
            assert result.passed is False
            assert "Connection failed" in result.errors[0]
            assert scheduler.state.failed_verifications == 1

    def test_reset_schedule(self, mock_config):
        """Test resetting the schedule."""
        state_data = {
            "last_verification_time": datetime.now().isoformat(),
            "total_verifications": 5,
        }

        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
        ):
            mock_load.return_value = (state_data, None)
            mock_save.return_value = (True, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
            )

            # Verify state is loaded
            assert scheduler.state.total_verifications == 5

            # Reset
            scheduler.reset_schedule()

            # State should be cleared
            assert scheduler.state.last_verification_time is None
            assert scheduler.state.total_verifications == 0
            mock_save.assert_called()

    def test_mark_verification_complete(self, mock_config):
        """Test manually marking verification complete."""
        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
        ):
            mock_load.return_value = (None, "No file")
            mock_save.return_value = (True, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            scheduler.mark_verification_complete(
                passed=True,
                report_id="manual-report",
            )

            assert scheduler.state.last_verification_time is not None
            assert scheduler.state.last_verification_passed is True
            assert scheduler.state.last_report_id == "manual-report"
            assert scheduler.state.total_verifications == 1
            assert scheduler.state.failed_verifications == 0

    def test_mark_verification_complete_failed(self, mock_config):
        """Test marking failed verification complete."""
        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
        ):
            mock_load.return_value = (None, "No file")
            mock_save.return_value = (True, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
            )

            scheduler.mark_verification_complete(passed=False)

            assert scheduler.state.last_verification_passed is False
            assert scheduler.state.failed_verifications == 1

    def test_repr(self, mock_config):
        """Test string representation."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (None, "No file")

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
                interval_days=1,
            )

            repr_str = repr(scheduler)
            assert "VerificationScheduler" in repr_str
            assert "test_mode=True" in repr_str
            assert "interval=1d" in repr_str


class TestVerificationSchedulerStatePersistence:
    """Tests for state persistence functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        config.test_mode = True
        config.is_test_mode.return_value = True
        return config

    def test_state_loads_on_init(self, mock_config):
        """Test that state is loaded on initialization."""
        existing_state = {
            "last_verification_time": "2025-01-10T12:00:00",
            "last_verification_passed": True,
            "total_verifications": 3,
        }

        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            mock_load.return_value = (existing_state, None)

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
            )

            mock_load.assert_called_once_with(
                VERIFICATION_STATE_FILENAME,
                test_mode=True,
            )
            assert scheduler.state.total_verifications == 3

    def test_state_saved_after_verification(self, mock_config):
        """Test that state is saved after running verification."""
        with (
            patch("photo_backup.verify.scheduler.load_json_state") as mock_load,
            patch("photo_backup.verify.scheduler.save_json_state") as mock_save,
            patch("photo_backup.verify.scheduler.Verifier") as mock_verifier_class,
        ):
            mock_load.return_value = (None, "No file")
            mock_save.return_value = (True, None)

            mock_verifier = MagicMock()
            mock_report = MagicMock()
            mock_report.verification_passed = True
            mock_report.report_id = "save-test"
            mock_report.total_duration_seconds = 10.0
            mock_report.errors = []
            mock_verifier.run_full_verification.return_value = mock_report
            mock_verifier_class.return_value = mock_verifier

            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
            )

            scheduler.run_scheduled_verification()

            # State should be saved
            mock_save.assert_called()
            # Verify the saved data
            call_args = mock_save.call_args
            saved_data = call_args[0][0]
            assert saved_data["last_verification_passed"] is True
            assert saved_data["last_report_id"] == "save-test"
            assert saved_data["total_verifications"] == 1

    def test_corrupted_state_handled(self, mock_config):
        """Test that corrupted state is handled gracefully."""
        with patch("photo_backup.verify.scheduler.load_json_state") as mock_load:
            # Return invalid data that will fail parsing
            mock_load.return_value = ({"invalid": "data", "last_verification_time": "not-a-date"}, None)

            # Should not raise, should create fresh state
            scheduler = VerificationScheduler(
                config=mock_config,
                test_mode=True,
            )

            assert scheduler.state.total_verifications == 0
