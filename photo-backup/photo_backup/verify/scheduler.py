"""
Verification scheduler for automated integrity checks.

Add Scheduled Verification - Monthly automatic check (daily in test mode).

This module provides the VerificationScheduler class that manages
scheduled verification runs based on configurable intervals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..config.config import Config
from ..state_utils import load_json_state, save_json_state
from .verifier import Verifier

# State file name for verification schedule
VERIFICATION_STATE_FILENAME = "verification_schedule.json"

# Default intervals
DEFAULT_VERIFICATION_INTERVAL_DAYS = 30  # Monthly for production
TEST_VERIFICATION_INTERVAL_DAYS = 1  # Daily for test mode


@dataclass
class VerificationScheduleState:
    """State tracking for verification schedule."""

    last_verification_time: datetime | None = None
    last_verification_passed: bool | None = None
    last_report_id: str | None = None
    next_scheduled_time: datetime | None = None
    total_verifications: int = 0
    failed_verifications: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "last_verification_time": (
                self.last_verification_time.isoformat() if self.last_verification_time else None
            ),
            "last_verification_passed": self.last_verification_passed,
            "last_report_id": self.last_report_id,
            "next_scheduled_time": (self.next_scheduled_time.isoformat() if self.next_scheduled_time else None),
            "total_verifications": self.total_verifications,
            "failed_verifications": self.failed_verifications,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationScheduleState":
        """Create from dictionary (JSON deserialization)."""
        last_time = data.get("last_verification_time")
        next_time = data.get("next_scheduled_time")

        return cls(
            last_verification_time=datetime.fromisoformat(last_time) if last_time else None,
            last_verification_passed=data.get("last_verification_passed"),
            last_report_id=data.get("last_report_id"),
            next_scheduled_time=datetime.fromisoformat(next_time) if next_time else None,
            total_verifications=data.get("total_verifications", 0),
            failed_verifications=data.get("failed_verifications", 0),
        )


@dataclass
class ScheduledVerificationResult:
    """Result of a scheduled verification run."""

    ran: bool = False
    passed: bool | None = None
    report_id: str | None = None
    skipped_reason: str | None = None
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get a summary string of the result."""
        if not self.ran:
            return f"Verification skipped: {self.skipped_reason}"

        status = "PASSED" if self.passed else "FAILED"
        return f"Verification {status} (duration: {self.duration_seconds:.1f}s, report: {self.report_id})"


class VerificationScheduler:
    """
    Manages scheduled verification runs.

    The scheduler tracks verification history and determines when
    the next verification should run based on configurable intervals.

    Production mode: Monthly verification (every 30 days)
    Test mode: Daily verification (every 1 day)

    Usage:
        >>> scheduler = VerificationScheduler(config, test_mode=True)
        >>> if scheduler.is_verification_due():
        ...     result = scheduler.run_scheduled_verification()
        ...     print(result.get_summary())
    """

    def __init__(
        self,
        config: Config | None = None,
        test_mode: bool = False,
        interval_days: int | None = None,
    ):
        """
        Initialize the verification scheduler.

        Args:
            config: Configuration object. If None, creates a new one
            test_mode: Whether to run in test mode (uses daily schedule)
            interval_days: Custom interval in days (overrides default)
        """
        self.config = config or Config(test_mode=test_mode)
        self.test_mode = test_mode or self.config.is_test_mode()
        self.logger = logging.getLogger(__name__)

        # Set verification interval
        if interval_days is not None:
            self._interval_days = interval_days
        elif self.test_mode:
            self._interval_days = TEST_VERIFICATION_INTERVAL_DAYS
        else:
            self._interval_days = DEFAULT_VERIFICATION_INTERVAL_DAYS

        # Load state
        self._state = self._load_state()

        self.logger.info(
            f"VerificationScheduler initialized: "
            f"{'test' if self.test_mode else 'production'} mode, "
            f"interval={self._interval_days} days"
        )

    @property
    def interval_days(self) -> int:
        """Get the verification interval in days."""
        return self._interval_days

    @property
    def interval_timedelta(self) -> timedelta:
        """Get the verification interval as a timedelta."""
        return timedelta(days=self._interval_days)

    @property
    def state(self) -> VerificationScheduleState:
        """Get the current schedule state."""
        return self._state

    def _load_state(self) -> VerificationScheduleState:
        """Load verification schedule state from disk."""
        data, error = load_json_state(VERIFICATION_STATE_FILENAME, test_mode=self.test_mode)

        if error or data is None:
            self.logger.debug(f"No existing verification state found: {error}")
            return VerificationScheduleState()

        try:
            state = VerificationScheduleState.from_dict(data)
            self.logger.debug(f"Loaded verification state: last run={state.last_verification_time}")
            return state
        except Exception as e:
            self.logger.warning(f"Failed to parse verification state: {e}")
            return VerificationScheduleState()

    def _save_state(self) -> bool:
        """Save verification schedule state to disk."""
        success, error = save_json_state(
            self._state.to_dict(),
            VERIFICATION_STATE_FILENAME,
            test_mode=self.test_mode,
        )

        if not success:
            self.logger.error(f"Failed to save verification state: {error}")
            return False

        self.logger.debug("Saved verification schedule state")
        return True

    def is_verification_due(self, reference_time: datetime | None = None) -> bool:
        """
        Check if verification is due based on schedule.

        Args:
            reference_time: Time to check against (defaults to now)

        Returns:
            True if verification should run, False otherwise
        """
        now = reference_time or datetime.now()

        # If never run, it's due
        if self._state.last_verification_time is None:
            self.logger.info("Verification is due: never run before")
            return True

        # Calculate time since last verification
        time_since_last = now - self._state.last_verification_time
        is_due = time_since_last >= self.interval_timedelta

        if is_due:
            days_since = time_since_last.total_seconds() / 86400
            self.logger.info(
                f"Verification is due: {days_since:.1f} days since last run (interval: {self._interval_days} days)"
            )
        else:
            remaining = self.interval_timedelta - time_since_last
            remaining_hours = remaining.total_seconds() / 3600
            self.logger.debug(f"Verification not due: {remaining_hours:.1f} hours remaining")

        return is_due

    def get_next_scheduled_time(self) -> datetime | None:
        """
        Get the next scheduled verification time.

        Returns:
            Next scheduled datetime, or None if never run
        """
        if self._state.last_verification_time is None:
            return None

        return self._state.last_verification_time + self.interval_timedelta

    def get_time_until_next(self) -> timedelta | None:
        """
        Get the time remaining until next scheduled verification.

        Returns:
            Timedelta until next run, or None if due now or never run
        """
        next_time = self.get_next_scheduled_time()
        if next_time is None:
            return None

        remaining = next_time - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def get_schedule_info(self) -> dict[str, Any]:
        """
        Get comprehensive schedule information.

        Returns:
            Dictionary with schedule details
        """
        next_time = self.get_next_scheduled_time()
        time_until = self.get_time_until_next()

        return {
            "mode": "test" if self.test_mode else "production",
            "interval_days": self._interval_days,
            "is_due": self.is_verification_due(),
            "last_verification_time": (
                self._state.last_verification_time.isoformat() if self._state.last_verification_time else None
            ),
            "last_verification_passed": self._state.last_verification_passed,
            "last_report_id": self._state.last_report_id,
            "next_scheduled_time": next_time.isoformat() if next_time else None,
            "time_until_next_hours": (time_until.total_seconds() / 3600 if time_until else None),
            "total_verifications": self._state.total_verifications,
            "failed_verifications": self._state.failed_verifications,
            "success_rate": (
                (self._state.total_verifications - self._state.failed_verifications)
                / self._state.total_verifications
                * 100
                if self._state.total_verifications > 0
                else None
            ),
        }

    def run_scheduled_verification(
        self,
        force: bool = False,
        repair: bool = False,
        save_report: bool = True,
    ) -> ScheduledVerificationResult:
        """
        Run a scheduled verification if due.

        Args:
            force: Run even if not due
            repair: Automatically repair any issues found
            save_report: Save verification report to file

        Returns:
            ScheduledVerificationResult with verification outcome
        """
        # Check if due (unless forced)
        if not force and not self.is_verification_due():
            time_until = self.get_time_until_next()
            hours_until = time_until.total_seconds() / 3600 if time_until else 0
            return ScheduledVerificationResult(
                ran=False,
                skipped_reason=f"Not due yet ({hours_until:.1f} hours remaining)",
            )

        self.logger.info("Starting scheduled verification...")
        start_time = datetime.now()
        result = ScheduledVerificationResult(ran=True)

        try:
            # Create verifier and run
            verifier = Verifier(config=self.config, test_mode=self.test_mode)

            report = verifier.run_full_verification(
                repair=repair,
                save_report=save_report,
            )

            # Update result
            result.passed = report.verification_passed
            result.report_id = report.report_id
            result.duration_seconds = report.total_duration_seconds

            if report.errors:
                result.errors = report.errors

            # Update state
            self._state.last_verification_time = start_time
            self._state.last_verification_passed = report.verification_passed
            self._state.last_report_id = report.report_id
            self._state.next_scheduled_time = start_time + self.interval_timedelta
            self._state.total_verifications += 1

            if not report.verification_passed:
                self._state.failed_verifications += 1

            self._save_state()

            self.logger.info(result.get_summary())

        except Exception as e:
            result.passed = False
            result.errors.append(str(e))
            result.duration_seconds = (datetime.now() - start_time).total_seconds()

            # Update state for failed run
            self._state.last_verification_time = start_time
            self._state.last_verification_passed = False
            self._state.next_scheduled_time = start_time + self.interval_timedelta
            self._state.total_verifications += 1
            self._state.failed_verifications += 1

            self._save_state()

            self.logger.error(f"Scheduled verification failed: {e}", exc_info=True)

        return result

    def reset_schedule(self) -> None:
        """
        Reset the verification schedule state.

        This clears the last verification time, making verification
        immediately due on next check.
        """
        self._state = VerificationScheduleState()
        self._save_state()
        self.logger.info("Verification schedule reset")

    def mark_verification_complete(
        self,
        passed: bool,
        report_id: str | None = None,
    ) -> None:
        """
        Manually mark a verification as complete.

        Use this when verification was run outside the scheduler.

        Args:
            passed: Whether the verification passed
            report_id: Optional report ID from the verification
        """
        now = datetime.now()
        self._state.last_verification_time = now
        self._state.last_verification_passed = passed
        self._state.last_report_id = report_id
        self._state.next_scheduled_time = now + self.interval_timedelta
        self._state.total_verifications += 1

        if not passed:
            self._state.failed_verifications += 1

        self._save_state()
        self.logger.info(f"Marked verification complete: passed={passed}")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"VerificationScheduler("
            f"test_mode={self.test_mode}, "
            f"interval={self._interval_days}d, "
            f"due={self.is_verification_due()})"
        )
