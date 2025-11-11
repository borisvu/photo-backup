"""
Unit tests for ServiceManager service loop integration.

Tests cover:
- Monitor polling integration
- Change detection workflow
- Backup triggering
- Change reset after backup
- Error handling in loop
"""

import logging
import time
from datetime import datetime
from threading import Thread
from unittest.mock import MagicMock, Mock, patch

import pytest

from photo_backup.backup import BackupStats
from photo_backup.config.config import Config
from photo_backup.monitor import ChangeSummary
from photo_backup.service import ServiceManager


@pytest.fixture
def test_config():
    """Create test mode configuration."""
    config = Config(test_mode=True)
    config.load_config()
    return config


@pytest.fixture
def mock_monitor():
    """Create mock DriveMonitor."""
    monitor = MagicMock()
    monitor.watch_path = "/tmp/test-photos"
    monitor.should_check.return_value = False
    monitor.check_for_changes.return_value = False
    monitor.get_change_summary.return_value = None
    return monitor


@pytest.fixture
def mock_backup_engine():
    """Create mock BackupEngine."""
    engine = MagicMock()
    job = MagicMock()
    job.__str__ = lambda self: "test-job"
    engine.create_backup_job.return_value = job
    
    # Create mock stats object with all required attributes
    stats = MagicMock(spec=BackupStats)
    stats.success = True
    stats.files_transferred = 5
    stats.total_size_display = "1.5 MB"
    stats.error_message = None
    engine.sync_with_stats.return_value = stats
    
    return engine


@pytest.fixture
def service_with_mocks(test_config, mock_monitor, mock_backup_engine):
    """Create service manager with mocked dependencies."""
    logger = logging.getLogger("test_service")
    return ServiceManager(
        test_config,
        logger=logger,
        monitor=mock_monitor,
        backup_engine=mock_backup_engine,
    )


class TestServiceLoopMonitorIntegration:
    """Test service loop integration with monitor."""

    def test_service_has_monitor_instance(self, service_with_mocks, mock_monitor):
        """Test that service has monitor instance."""
        assert service_with_mocks.monitor is mock_monitor

    def test_service_has_backup_engine_instance(self, service_with_mocks, mock_backup_engine):
        """Test that service has backup engine instance."""
        assert service_with_mocks.backup_engine is mock_backup_engine

    def test_service_creates_monitor_if_not_provided(self, test_config):
        """Test that service creates monitor if not provided."""
        service = ServiceManager(test_config)
        assert service.monitor is not None
        assert hasattr(service.monitor, 'should_check')

    def test_service_creates_backup_engine_if_not_provided(self, test_config):
        """Test that service creates backup engine if not provided."""
        service = ServiceManager(test_config)
        assert service.backup_engine is not None
        assert hasattr(service.backup_engine, 'create_backup_job')

    def test_loop_polls_monitor_should_check(self, service_with_mocks, mock_monitor):
        """Test that loop polls monitor.should_check()."""
        mock_monitor.should_check.return_value = False
        
        def stop_quickly():
            time.sleep(0.1)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_quickly)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should have called should_check at least once
        assert mock_monitor.should_check.called

    def test_loop_checks_for_changes_when_should_check_true(self, service_with_mocks, mock_monitor):
        """Test that loop checks for changes when should_check returns True."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.return_value = False
        
        def stop_quickly():
            time.sleep(0.2)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_quickly)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should have called check_for_changes
        assert mock_monitor.check_for_changes.called

    def test_loop_does_not_check_when_should_check_false(self, service_with_mocks, mock_monitor):
        """Test that loop doesn't check when should_check returns False."""
        mock_monitor.should_check.return_value = False
        
        def stop_quickly():
            time.sleep(0.1)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_quickly)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should NOT have called check_for_changes
        assert not mock_monitor.check_for_changes.called


class TestServiceLoopBackupTriggering:
    """Test backup triggering in service loop."""

    def test_triggers_backup_when_changes_detected(self, service_with_mocks, mock_monitor, mock_backup_engine):
        """Test that backup is triggered when changes detected."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.return_value = True
        
        summary = ChangeSummary(
            added_count=5,
            modified_count=2,
            deleted_count=1,
            total_size=1500000,
        )
        mock_monitor.get_change_summary.return_value = summary
        
        def stop_after_backup():
            time.sleep(0.5)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_after_backup)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should have created backup job
        assert mock_backup_engine.create_backup_job.called
        
        # Should have executed sync
        assert mock_backup_engine.sync_with_stats.called

    def test_does_not_trigger_backup_when_no_changes(self, service_with_mocks, mock_monitor, mock_backup_engine):
        """Test that backup is not triggered when no changes."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.return_value = False
        
        def stop_quickly():
            time.sleep(0.2)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_quickly)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should NOT have triggered backup
        assert not mock_backup_engine.create_backup_job.called
        assert not mock_backup_engine.sync_with_stats.called

    def test_resets_changes_after_successful_backup(self, service_with_mocks, mock_monitor, mock_backup_engine):
        """Test that changes are reset after successful backup."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.return_value = True
        
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        mock_monitor.get_change_summary.return_value = summary
        
        # Mock successful backup
        stats = MagicMock(spec=BackupStats)
        stats.success = True
        stats.files_transferred = 5
        stats.total_size_display = "1 KB"
        stats.error_message = None
        mock_backup_engine.sync_with_stats.return_value = stats
        
        def stop_after_backup():
            time.sleep(0.5)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_after_backup)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should have reset changes after successful backup
        assert mock_monitor.reset_changes.called

    def test_does_not_reset_changes_after_failed_backup(self, service_with_mocks, mock_monitor, mock_backup_engine):
        """Test that changes are not reset after failed backup."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.return_value = True
        
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        mock_monitor.get_change_summary.return_value = summary
        
        # Mock failed backup
        stats = MagicMock(spec=BackupStats)
        stats.success = False
        stats.error_message = "Backup failed"
        stats.files_transferred = 0
        stats.total_size_display = "0 B"
        mock_backup_engine.sync_with_stats.return_value = stats
        
        def stop_after_backup():
            time.sleep(0.5)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_after_backup)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        # Should NOT have reset changes after failed backup
        assert not mock_monitor.reset_changes.called


class TestServiceLoopErrorHandling:
    """Test error handling in service loop."""

    def test_continues_after_monitor_check_error(self, service_with_mocks, mock_monitor, caplog):
        """Test that loop continues after monitor check error."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.side_effect = [Exception("Test error"), False]
        
        with caplog.at_level(logging.ERROR):
            def stop_after_delay():
                time.sleep(0.5)
                service_with_mocks.stop()
            
            thread = Thread(target=stop_after_delay)
            thread.start()
            
            service_with_mocks.start()
            thread.join()
        
        # Should have logged error
        assert "Error in service loop" in caplog.text
        
        # Should have continued running
        assert service_with_mocks._status.loop_count > 0

    def test_continues_after_backup_trigger_error(self, service_with_mocks, mock_monitor, mock_backup_engine, caplog):
        """Test that loop continues after backup trigger error."""
        mock_monitor.should_check.return_value = True
        mock_monitor.check_for_changes.return_value = True
        
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        mock_monitor.get_change_summary.return_value = summary
        
        # Mock backup error
        mock_backup_engine.sync_with_stats.side_effect = Exception("Backup error")
        
        with caplog.at_level(logging.ERROR):
            def stop_after_delay():
                time.sleep(0.5)
                service_with_mocks.stop()
            
            thread = Thread(target=stop_after_delay)
            thread.start()
            
            service_with_mocks.start()
            thread.join()
        
        # Should have logged error
        assert "Error triggering backup" in caplog.text
        
        # Should have continued running (not crashed)
        assert service_with_mocks._status.loop_count > 0


class TestServiceLoopTiming:
    """Test service loop timing and intervals."""

    def test_loop_respects_interval_setting(self, service_with_mocks):
        """Test that loop respects configured interval."""
        # In test mode, interval is 5 seconds
        assert service_with_mocks._loop_interval == 5

    def test_loop_sleeps_between_iterations(self, service_with_mocks):
        """Test that loop sleeps between iterations."""
        start_time = time.time()
        
        def stop_after_one_iteration():
            # Wait for at least one full iteration
            time.sleep(service_with_mocks._loop_interval + 0.5)
            service_with_mocks.stop()
        
        thread = Thread(target=stop_after_one_iteration)
        thread.start()
        
        service_with_mocks.start()
        thread.join()
        
        elapsed = time.time() - start_time
        
        # Should have taken at least one interval
        assert elapsed >= service_with_mocks._loop_interval


class TestTriggerBackupMethod:
    """Test _trigger_backup method directly."""

    def test_trigger_backup_creates_job(self, service_with_mocks, mock_backup_engine):
        """Test that trigger_backup creates a backup job."""
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        
        service_with_mocks._trigger_backup(summary)
        
        assert mock_backup_engine.create_backup_job.called

    def test_trigger_backup_executes_sync(self, service_with_mocks, mock_backup_engine):
        """Test that trigger_backup executes sync."""
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        
        service_with_mocks._trigger_backup(summary)
        
        assert mock_backup_engine.sync_with_stats.called

    def test_trigger_backup_resets_on_success(self, service_with_mocks, mock_monitor, mock_backup_engine):
        """Test that trigger_backup resets changes on success."""
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        
        stats = MagicMock(spec=BackupStats)
        stats.success = True
        stats.files_transferred = 5
        stats.total_size_display = "1 KB"
        stats.error_message = None
        mock_backup_engine.sync_with_stats.return_value = stats
        
        service_with_mocks._trigger_backup(summary)
        
        assert mock_monitor.reset_changes.called

    def test_trigger_backup_handles_exception(self, service_with_mocks, mock_backup_engine, caplog):
        """Test that trigger_backup handles exceptions gracefully."""
        summary = ChangeSummary(added_count=5, modified_count=0, deleted_count=0, total_size=1000)
        
        mock_backup_engine.create_backup_job.side_effect = Exception("Test error")
        
        with caplog.at_level(logging.ERROR):
            service_with_mocks._trigger_backup(summary)
        
        assert "Error triggering backup" in caplog.text

