# Monitor Module Integration Guide

## Overview

The monitor module provides comprehensive file system monitoring for the photo backup system. It's designed to detect changes in photo directories and trigger backups when needed.

## Quick Start

```python
from photo_backup.monitor import DriveMonitor
from photo_backup.config import Config

# Initialize with config
config = Config(test_mode=True)
monitor = DriveMonitor(config=config)

# Start monitoring
monitor.start()

# Check for changes
if monitor.check_for_changes():
    # Get pending changes
    changes = monitor.get_pending_changes()
    
    # Get change summary
    summary = monitor.get_change_summary()
    print(f"Found {summary.total_files} changed files ({summary.get_formatted_size()})")
    
    # After successful backup
    monitor.reset_changes()

# Stop monitoring
monitor.stop()
```

## Public API

### Classes

#### `DriveMonitor`
Main monitoring class for detecting file system changes.

**Constructor:**
```python
DriveMonitor(config: Config | None = None)
```

**Key Methods:**

- `start()` - Start monitoring (sets state to WATCHING)
- `stop()` - Stop monitoring (sets state to STOPPED)
- `check_for_changes() -> bool` - Check for file changes, returns True if changes found
- `get_changes() -> list[tuple[str, MonitorEvent]]` - Get list of pending changes
- `get_change_summary() -> ChangeSummary | None` - Get aggregated change statistics
- `reset_changes()` - Clear pending changes after backup
- `clear_all_state()` - Full state reset (testing/debugging only)
- `get_status() -> dict` - Get current monitor status
- `get_detailed_status() -> dict` - Get detailed status with history
- `get_pending_changes() -> list[dict]` - Get pending changes as dict list
- `format_status() -> str` - Get human-readable status report
- `load_state() -> bool` - Load persistent state from disk
- `save_state() -> bool` - Save persistent state to disk

**Properties:**

- `watch_path: Path` - Path being monitored
- `state: MonitorState` - Current monitor state
- `is_test_mode: bool` - Whether in test mode

**State Checking Methods:**

- `is_drive_mounted() -> bool` - Check if drive is mounted
- `is_debouncing() -> bool` - Check if in debounce window
- `should_check() -> bool` - Check if periodic check is due
- `get_time_since_last_change() -> float | None` - Time since last change
- `get_time_since_last_check() -> float | None` - Time since last check

#### `MonitorEvent` (Enum)
File system and monitoring events.

**File System Events:**
- `FILE_ADDED` - New file detected
- `FILE_MODIFIED` - File modification detected
- `FILE_DELETED` - File deletion detected
- `DIRECTORY_ADDED` - New directory detected
- `DIRECTORY_DELETED` - Directory deletion detected

**Drive Events:**
- `DRIVE_MOUNTED` - Drive mounted
- `DRIVE_UNMOUNTED` - Drive unmounted

**Timer Events:**
- `TIMER_ELAPSED` - Timer elapsed
- `CHECK_INTERVAL` - Check interval reached

**State Events:**
- `MONITOR_STARTED` - Monitor started
- `MONITOR_STOPPED` - Monitor stopped
- `CHANGES_DETECTED` - Changes detected
- `NO_CHANGES` - No changes detected
- `CHANGES_RESET` - Changes reset after backup
- `STATE_CLEARED` - All state cleared

#### `MonitorState` (Enum)
Monitor operational states.

- `IDLE` - Not monitoring
- `WATCHING` - Actively watching
- `PROCESSING` - Processing changes
- `STOPPED` - Stopped
- `ERROR` - Error state

#### `ChangeSummary` (Dataclass)
Aggregated change statistics.

**Fields:**
- `total_files: int` - Total changed files
- `total_size: int` - Total size in bytes
- `added_count: int` - Number of added files
- `modified_count: int` - Number of modified files
- `deleted_count: int` - Number of deleted files
- `by_directory: dict[str, int]` - File count by directory
- `by_directory_size: dict[str, int]` - Size by directory

**Methods:**
- `get_formatted_size() -> str` - Human-readable size (e.g., "1.5 GB")

#### `MonitorStateData` (Dataclass)
Persistent state information.

**Fields:**
- `last_check_time: datetime | None` - Last check timestamp
- `last_change_time: datetime | None` - Last change timestamp
- `total_checks: int` - Cumulative check count
- `total_changes_detected: int` - Cumulative changes count
- `change_history: list[dict]` - Recent changes (max 100)
- `watch_path: str` - Path being monitored

**Methods:**
- `to_dict() -> dict` - Serialize to dict
- `from_dict(data: dict) -> MonitorStateData` - Deserialize from dict
- `add_change_event(event_type, file_path, timestamp)` - Add to history
- `update_check(timestamp)` - Update check time
- `update_changes(change_count, timestamp)` - Update change stats

## Integration Patterns

### Pattern 1: Simple Polling Loop

```python
from photo_backup.monitor import DriveMonitor
from photo_backup.config import Config
import time

config = Config()
monitor = DriveMonitor(config=config)
monitor.start()

while True:
    if monitor.should_check():
        if monitor.check_for_changes():
            if not monitor.is_debouncing():
                # Trigger backup
                summary = monitor.get_change_summary()
                print(f"Backup needed: {summary.total_files} files")
                # ... run backup ...
                monitor.reset_changes()
    
    time.sleep(60)  # Check every minute
```

### Pattern 2: Event-Driven with Summary

```python
from photo_backup.monitor import DriveMonitor
from photo_backup.config import Config

def on_changes_detected(monitor):
    """Handle detected changes."""
    summary = monitor.get_change_summary()
    
    if summary:
        print(f"\n=== Changes Detected ===")
        print(f"Files: {summary.total_files}")
        print(f"Size: {summary.get_formatted_size()}")
        print(f"Added: {summary.added_count}")
        print(f"Modified: {summary.modified_count}")
        print(f"Deleted: {summary.deleted_count}")
        
        # Group by directory
        for dir_path, count in summary.by_directory.items():
            size = summary.by_directory_size.get(dir_path, 0)
            print(f"  {dir_path}: {count} files")
        
        return summary
    return None

config = Config()
monitor = DriveMonitor(config=config)
monitor.start()

# Check for changes
if monitor.check_for_changes():
    # Wait for debounce
    if not monitor.is_debouncing():
        summary = on_changes_detected(monitor)
        if summary:
            # Trigger backup
            # ... backup logic ...
            monitor.reset_changes()
```

### Pattern 3: Persistent State Tracking

```python
from photo_backup.monitor import DriveMonitor
from photo_backup.config import Config

config = Config()
monitor = DriveMonitor(config=config)

# Load previous state
if monitor.load_state():
    print(f"Loaded state: {monitor._monitor_state.total_checks} checks recorded")
else:
    print("Starting fresh")

monitor.start()

# Monitoring loop
# ... your monitoring logic ...

# State is automatically saved after each check
# Manual save if needed:
monitor.save_state()
```

### Pattern 4: Status Monitoring

```python
from photo_backup.monitor import DriveMonitor
from photo_backup.config import Config

config = Config()
monitor = DriveMonitor(config=config)
monitor.start()

# Get basic status
status = monitor.get_status()
print(f"State: {status['state']}")
print(f"Pending changes: {status['changes_pending']}")
print(f"Drive mounted: {status['drive_mounted']}")

# Get detailed status with history
detailed = monitor.get_detailed_status()
print(f"Recent history: {len(detailed['recent_history'])} events")

# Human-readable report
print(monitor.format_status())
```

## Configuration

The monitor respects the following configuration settings:

### Production Settings (defaults)
```yaml
monitoring:
  check_interval_hours: 4          # Periodic check interval
  debounce_delay_seconds: 120      # Change debounce delay (2 minutes)
```

### Test Mode Settings
```yaml
monitoring:
  check_interval_hours: 0.1        # 6 minutes
  debounce_delay_seconds: 0.5      # 0.5 seconds
```

## State Persistence

State is automatically saved after each check (configurable via `_auto_save_state` flag).

**State File Locations:**
- Production: `~/Library/Application Support/photo-backup/state/monitor_state.json`
- Test: `/tmp/photo-backup-test/state/monitor_state.json`

**Persisted Data:**
- Last check time
- Last change time
- Total checks performed
- Total changes detected
- Change history (last 100 events)
- Watch path

## Debouncing

The monitor implements debouncing to batch rapid file changes:

- **Purpose**: Prevent triggering backups during large file operations
- **Behavior**: Timer resets on each new change
- **Configuration**: `monitoring.debounce_delay_seconds`
- **Production**: 120 seconds (2 minutes)
- **Test Mode**: 0.5 seconds

**Usage:**
```python
if monitor.check_for_changes():
    if monitor.is_debouncing():
        print(f"Still debouncing, wait {monitor.get_time_since_last_change():.1f}s")
    else:
        # Safe to trigger backup
        pass
```

## Periodic Timer

The monitor includes a passive timer for periodic checks:

- **Purpose**: Backstop for missed file system events
- **Behavior**: Tracks time since last check
- **Configuration**: `monitoring.check_interval_hours`
- **Production**: 4 hours
- **Test Mode**: 6 minutes (0.1 hours)

**Usage:**
```python
if monitor.should_check():
    print("Periodic check due")
    monitor.check_for_changes()
```

## Error Handling

The monitor handles errors gracefully:

```python
monitor = DriveMonitor(config=config)

try:
    monitor.start()
    
    if not monitor.is_drive_mounted():
        print("Drive not mounted, skipping check")
    else:
        monitor.check_for_changes()
        
except Exception as e:
    logger.error(f"Monitor error: {e}")
    monitor.state = MonitorState.ERROR
finally:
    monitor.stop()
```

## Testing

The monitor includes comprehensive test coverage:

- **Total Tests**: 83 unit tests
- **Test Classes**: 10 test classes
- **Coverage**: All functionality tested

**Test Mode Features:**
- Accelerated timers (seconds instead of hours)
- Test directory monitoring
- Fast debouncing
- State in `/tmp`

**Running Tests:**
```bash
cd photo-backup
pytest tests/unit/test_monitor.py -v
```

## Performance Considerations

1. **Polling-based**: Uses snapshot comparison, not inotify
2. **Efficient**: Only scans when `check_for_changes()` called
3. **Scalable**: Handles large directories efficiently
4. **Resource-friendly**: No background threads or processes

## Future Integration Points

For Phase 8 (Service Management), the monitor will integrate with:

1. **ServiceManager**: Main service loop will poll monitor
2. **BackupEngine**: Will use monitor's change summaries
3. **CLI Commands**: Status commands will use monitor's status methods
4. **Health Checks**: Will verify monitor is running correctly

## Example: Full Service Integration

```python
from photo_backup.monitor import DriveMonitor
from photo_backup.backup import BackupEngine
from photo_backup.config import Config
import time

class BackupService:
    def __init__(self, config: Config):
        self.config = config
        self.monitor = DriveMonitor(config=config)
        self.backup_engine = BackupEngine(config=config)
        self.running = False
    
    def start(self):
        """Start the service."""
        self.monitor.load_state()
        self.monitor.start()
        self.running = True
        
        print("Backup service started")
        print(self.monitor.format_status())
    
    def run(self):
        """Main service loop."""
        while self.running:
            # Check if periodic check is due
            if self.monitor.should_check():
                self.check_and_backup()
            
            time.sleep(60)  # Check every minute
    
    def check_and_backup(self):
        """Check for changes and backup if needed."""
        if self.monitor.check_for_changes():
            # Wait for debounce
            if self.monitor.is_debouncing():
                print(f"Changes detected, debouncing...")
                return
            
            # Get change summary
            summary = self.monitor.get_change_summary()
            print(f"\nBackup triggered: {summary.total_files} files ({summary.get_formatted_size()})")
            
            # Run backup
            try:
                self.backup_engine.sync()
                
                # Reset changes after successful backup
                self.monitor.reset_changes()
                print("Backup completed successfully")
                
            except Exception as e:
                print(f"Backup failed: {e}")
    
    def stop(self):
        """Stop the service."""
        self.running = False
        self.monitor.save_state()
        self.monitor.stop()
        print("Backup service stopped")

# Usage
if __name__ == "__main__":
    config = Config(test_mode=True)
    service = BackupService(config)
    
    try:
        service.start()
        service.run()
    except KeyboardInterrupt:
        service.stop()
```

## Support

For issues or questions about the monitor module:
1. Check the architecture documentation in `architecture.md`
2. Review test cases in `tests/unit/test_monitor.py`
3. See module docstrings for detailed API documentation

## Version

Monitor Module v1.0 - Phase 7 Complete (Task 72)
- 83 comprehensive unit tests
- Full feature set implemented
- Ready for service integration

