---
aliases:
tags:
  - tasks
  - implementation
  - backup
  - project
creation_date: 2025-06-21
---

# Photo Backup MVP - Granular Task List

## Overview

This document contains small, testable tasks for building the Photo Backup MVP. Each task is designed to be completed independently and tested before moving to the next. Testing uses functional tests via main.py with Minio simulating Wasabi.

## Phase 1: Project Foundation (Tasks 1-11)

### Task 1: Create Project Structure

**Goal**: Set up basic Python project structure

- Create `photo-backup/` directory
- Create `photo_backup/` package directory with `__init__.py`
- Create empty `setup.py`, `requirements.txt`, `README.md`
- Create `.gitignore` with Python defaults
  **Test**: Verify directory structure exists

### Task 2: Create Version Management

**Goal**: Add version tracking

- Create `photo_backup/__version__.py` with `__version__ = "0.1.0"`
- Update `photo_backup/__init__.py` to import version
  **Test**: `python -c "import photo_backup; print(photo_backup.__version__)"`

### Task 3: Set Up Basic Requirements

**Goal**: Define Python dependencies

- Add to `requirements.txt`:
  - `PyYAML>=6.0`
  - `click>=8.0`
  - `minio>=7.0`
  - `pytest>=7.0`
- Create `requirements-dev.txt`:
  - `docker>=6.0`
- Create virtual environment and install packages
  **Test**: `pip list` shows installed packages

### Task 4: Create Test Infrastructure

**Goal**: Set up functional testing framework

- Create `photo_backup/test_utils.py`
- Add `start_minio_container()` function using docker
- Add `stop_minio_container()` function
- Add `create_test_photos()` to generate dummy files
- Add `cleanup_test_data()` function
  **Test**: Can import test_utils and start/stop Minio

### Task 5: Create Minimal CLI Entry Point

**Goal**: Basic command-line interface

- Create `photo_backup/main.py` with click CLI
- Add single command `@click.command()` that prints "Photo Backup v{version}"
- Add `--test-mode` flag that sets test configuration
- Add `if __name__ == "__main__"` block
  **Test**: `python -m photo_backup.main` prints version, `--test-mode` flag works

### Task 6: Create Config Module Skeleton

**Goal**: Configuration file structure

- Create `photo_backup/config.py` with empty `Config` class
- Add method `load_config()` that returns hardcoded dict for now
- Add `test_mode` flag support that uses Minio endpoint
  **Test**: Import Config class, test mode changes endpoint

### Task 7: Create Logger Module

**Goal**: Basic logging setup

- Create `photo_backup/logger.py`
- Add `setup_logger()` function that returns configured logger
- Configure console output only for now
  **Test**: Logger writes "Test message" to console

### Task 8: Add Logger to Main

**Goal**: Integrate logging into CLI

- Import logger in main.py
- Initialize logger in main function
- Log startup message with version
  **Test**: Running main shows log output with timestamp

### Task 9: Create Example Config File

**Goal**: User configuration template

- Create `config.yaml.example` with basic structure
- Include source_path and destination placeholders
- Add test_mode section with Minio settings
  **Test**: File exists and is valid YAML

### Task 10: Create Setup.py

**Goal**: Make package installable

- Add basic setup() configuration
- Include console_scripts entry point for `photo-backup` command
- Add package discovery
  **Test**: `pip install -e .` succeeds

### Task 11: Create First Functional Test

**Goal**: Verify basic functionality works

- Create `test_basic.py` that imports main
- Test that CLI runs without errors
- Test version output
- Use test_utils to verify test infrastructure
  **Test**: `python test_basic.py` passes

## Phase 2: Core Utilities (Tasks 12-22)

### Task 12: Create Utils Module

**Goal**: Shared utility functions

- Create `photo_backup/utils.py`
- Add `format_bytes()` function (bytes to human readable)
- Add `ensure_directory()` function
  **Test**: Create functional test that uses format_bytes via CLI output

### Task 13: Add Path Validation

**Goal**: Validate file paths

- Add `validate_path()` to utils.py
- Check if path exists and is accessible
- Return tuple (valid: bool, error: str)
  **Test**: Functional test with valid and invalid paths

### Task 14: Create State Directory Manager

**Goal**: Manage application state directories

- Add function to create state directories
- Use `~/Library/Application Support/photo-backup/`
- Create subdirs: state/, config/, temp/
- In test mode, use `/tmp/photo-backup-test/`
  **Test**: Directories created with correct permissions

### Task 15: Add JSON State Helper

**Goal**: Save/load JSON state files

- Add `save_json_state()` to utils.py
- Add `load_json_state()` with error handling
- Use state directory from previous task
  **Test**: Functional test saves and loads test data

### Task 16: Add Process Lock

**Goal**: Prevent multiple instances

- Add `acquire_lock()` function using PID file
- Add `release_lock()` function
- Store in temp/ directory
  **Test**: Run two instances, second fails with clear message

### Task 17: Create Time Utilities

**Goal**: Time calculation helpers

- Add `parse_interval()` (e.g., "4h" -> seconds)
- Add `format_duration()` (seconds -> "1h 23m")
  **Test**: Test via CLI with different time formats

### Task 18: Add Shell Command Runner

**Goal**: Safe subprocess execution

- Create `run_command()` function
- Capture stdout, stderr, return code
- Add timeout support
  **Test**: Functional test runs echo command via main.py

### Task 19: Add Retry Decorator

**Goal**: Retry logic for network operations

- Create `@retry` decorator
- Support max attempts and backoff
- Log retry attempts
  **Test**: Test with Minio connection failure/recovery

### Task 20: Create Size Calculator

**Goal**: Calculate directory sizes

- Add `calculate_directory_size()` function
- Return total bytes and file count
- Handle permission errors gracefully
  **Test**: Calculate test photo directory size

### Task 21: Add Test Photo Generator

**Goal**: Create realistic test data

- Add to test_utils: `generate_test_photos()`
- Create dummy files with JPEG, JPG, DNG and CR2 with some random text inside.
- Organize by year/month structure
- This code will only to be invoked by tests that need it.
  **Test**: Generate test set, verify structure

### Task 22: Integration Test for Utils

**Goal**: Verify all utilities work together

- Create functional test using multiple utilities
- Save state, calculate size, format output
- Use test photos from previous task
  **Test**: All utilities work via main.py commands

## Phase 3: Configuration System (Tasks 23-32)

### Task 23: Implement Config Loading

**Goal**: Load YAML configuration

- Update Config class to load from file
- Add schema validation basics
- Fall back to defaults if file missing
- In test mode, override with Minio settings
  **Test**: Loads config, test mode uses Minio endpoint

### Task 24: Add Config Validation

**Goal**: Validate configuration values

- Check required fields exist
- Validate paths are absolute
- Validate numeric ranges
- Test mode validation allows test paths
  **Test**: Rejects invalid configs with clear errors

### Task 25: Create Default Config

**Goal**: Sensible defaults

- Add DEFAULT_CONFIG dict in config.py
- Merge with loaded config
- Document each setting
- Test mode defaults to Minio
  **Test**: Works without config file

### Task 26: Add Config Search Paths

**Goal**: Multiple config locations

- Check: current dir, user config dir, system
- Use first found
- Log which config loaded
- Test mode uses test config location
  **Test**: Finds config in different locations

### Task 27: Environment Variable Override

**Goal**: Override config with env vars

- Support PHOTO*BACKUP*\* variables
- Override specific config values
- PHOTO_BACKUP_TEST_MODE=1 enables test mode
  **Test**: Env vars override file config

### Task 28: Create Config CLI Command

**Goal**: Show current configuration

- Add `photo-backup config` command
- Display merged configuration
- Show config file location
- Indicate if in test mode
  **Test**: Command shows all settings including test mode

### Task 29: Add Config Validation Command

**Goal**: Test configuration validity

- Add `photo-backup validate` command
- Check all paths exist
- Test rclone availability
- In test mode, verify Minio connection
  **Test**: Reports valid/invalid config

### Task 30: Create User Config Directory

**Goal**: Set up user configuration

- Create config directory on first run
- Copy example config if none exists
- Set correct permissions (600)
- Test mode uses temporary directory
  **Test**: Creates config on fresh install

### Task 31: Add Dry Run Mode

**Goal**: Test without making changes

- Add --dry-run flag to CLI
- Set in config when present
- Pass through to all operations
- Works with test mode
  **Test**: Dry run + test mode shows operations without executing

### Task 32: Config Functional Test

**Goal**: Full config system test

- Test loading config from file
- Override with env var
- Validate all settings
- Test with Minio endpoint
  **Test**: Complete config flow works with test mode

## Phase 4: Logging System (Tasks 33-42)

### Task 33: Enhance Logger Configuration

**Goal**: Configure from settings

- Read log level from config
- Set up formatters
- Add context (job ID)
- Test mode uses DEBUG level
  **Test**: Log level changes work, test mode verbose

### Task 34: Add File Logging

**Goal**: Write logs to file

- Create log directory
- Add RotatingFileHandler
- Configure rotation size/count
- Test mode logs to temp directory
  **Test**: Logs written to file, rotation works

### Task 35: Create Error Log

**Goal**: Separate error logging

- Add error-only log file
- Filter ERROR and above
- Different format for errors
  **Test**: Errors in separate file during test

### Task 36: Add Structured Logging

**Goal**: JSON log format option

- Add JSON formatter
- Include metadata fields
- Toggle via config
  **Test**: Valid JSON output in test logs

### Task 37: Create Log Cleanup

**Goal**: Manage old logs

- Add function to clean old logs
- Keep based on age/count
- Run on startup
- Test mode cleans aggressively
  **Test**: Old test logs deleted

### Task 38: Add Operation Context

**Goal**: Track operations

- Create context manager for operations
- Add operation ID to logs
- Log operation start/end
  **Test**: Test backup operation shows context

### Task 39: Create Progress Logger

**Goal**: Log progress updates

- Add progress logging method
- Include percentages and ETA
- Rate limit updates
  **Test**: Progress shown during test file operations

### Task 40: Add Summary Statistics

**Goal**: Log operation summaries

- Create summary formatter
- Log files processed, bytes, time
- Format nicely for console
  **Test**: Summary after test backup

### Task 41: Create Log Viewer Command

**Goal**: Comprehensive log viewing and filtering

- Add `photo-backup logs` command with multiple options:
  - `--tail N` - Show last N lines (default: 50)
  - `--level LEVEL` - Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - `--errors` - Show only error/critical logs (shortcut for `--level ERROR`)
  - `--follow` - Follow log file in real-time (like `tail -f`)
  - `--json` - Output in JSON format (if logs are in JSON format)
- Leverage existing Unix tools (grep, awk, tail) under the hood
- Support both production and test mode log paths
- Provide examples and documentation for manual log filtering
  **Test**: Comprehensive log viewing and filtering works for all scenarios

### Task 42: Logging Functional Test

**Goal**: Full logging system test

- Run test backup with logging
- Verify all log levels work
- Check file rotation
- Validate JSON format
  **Test**: Complete logging works during test backup

## Phase 5: Credential Management (Tasks 43-52)

### Task 43: Create Credentials Module

**Goal**: Basic credentials structure

- Create `photo_backup/credentials.py`
- Add `CredentialManager` class
- Define credential schema
- Support test mode credentials
  **Test**: Can instantiate with test credentials

### Task 44: Add Test Mode Credentials

**Goal**: Hardcoded Minio credentials for testing

- In test mode, use fixed Minio credentials
- Access key: "minioadmin"
- Secret key: "minioadmin"
- Endpoint: "localhost:9000"
  **Test**: Test mode returns Minio credentials

### Task 45: Add 1Password Detection

**Goal**: Check if 1Password CLI available

- Add `check_op_cli()` function
- Verify `op` command exists
- Check version compatibility
- Skip in test mode
  **Test**: Detects op installation (or skips in test mode)

### Task 46: Implement Credential Retrieval

**Goal**: Get credentials from 1Password

- Add `get_credentials()` method
- Parse JSON response
- Handle missing fields
- Return test credentials in test mode
  **Test**: Retrieves credentials (Minio in test mode)

### Task 47: Add Session Caching

**Goal**: Cache 1Password session

- Store session token in memory
- Detect expired sessions
- Re-authenticate as needed
- Test mode doesn't need sessions
  **Test**: Reuses session token (or skips in test)

### Task 48: Create Credential Validation

**Goal**: Verify credentials work

- Add `validate_credentials()` method
- Test with simple rclone command
- For test mode, verify Minio is running
- Return success/failure
  **Test**: Validates against Minio in test mode

### Task 48.1: Investigate 1Password CLI Authentication Options

**Goal**: Find ways to use 1Password CLI without Touch ID

- Research 1Password CLI authentication methods
- Investigate service account tokens
- Look into API access tokens
- Check for environment variable authentication
- Explore session token persistence options
- Document findings and recommendations
- Test alternative authentication methods
- Consider security implications
  **Test**: Document authentication options and their trade-offs

### Task 49: Add Error Handling

**Goal**: Handle credential failures

- Catch authentication errors
- Provide clear error messages
- Suggest fixes
- Test mode: suggest starting Minio
  **Test**: Handles missing Minio container gracefully

### Task 50: Create Manual Override

**Goal**: Allow manual credential entry

- Add fallback for no 1Password
- Read from environment variables
- Never store in files
- Test mode ignores overrides
  **Test**: Env vars work (except in test mode)

### Task 51: Add Credential Test Command

**Goal**: Test credential setup

- Add `photo-backup test-auth` command
- Check 1Password or test mode
- Validate S3 access
- Create test bucket if needed
  **Test**: Reports auth status, creates Minio bucket

### Task 52: Credential Functional Test

**Goal**: Full credential flow

- Start Minio container
- Retrieve test credentials
- Validate with rclone
- Clean up properly
  **Test**: Complete auth works with Minio

## Phase 6: Backup Engine Core (Tasks 53-62)

### Task 53: Create Backup Module

**Goal**: Basic backup structure

- Create `photo_backup/backup.py`
- Add `BackupEngine` class
- Define backup job structure
- Support test mode with Minio
  **Test**: Can instantiate engine with test config

### Task 54: Add rclone Detection

**Goal**: Verify rclone installed

- Add `check_rclone()` function
- Get version info
- Check minimum version
  **Test**: Detects rclone installation

### Task 55: Build rclone Command

**Goal**: Construct rclone command

- Add `build_sync_command()` method
- Include all parameters
- Support dry-run mode
- Use Minio endpoint in test mode
  **Test**: Generates correct command for Minio

### Task 56: Implement Basic Sync

**Goal**: Run simple sync

- Add `sync()` method
- Execute rclone subprocess
- Capture output
- Create test photos and sync to Minio
  **Test**: Syncs test photos to Minio bucket

### Task 57: Add Progress Parsing

**Goal**: Parse rclone progress

- Extract transfer statistics
- Parse progress percentage
- Emit progress events
  **Test**: Shows progress during test sync

### Task 58: Create Backup Statistics

**Goal**: Track backup metrics

- Add `BackupStats` class
- Track files, bytes, duration
- Calculate rates
  **Test**: Stats shown after test sync

### Task 59: Add Error Detection

**Goal**: Detect sync failures

- Parse rclone error output
- Categorize error types
- Return error details
- Test with permission errors
  **Test**: Catches and reports errors clearly

### Task 60: Implement State Saving

**Goal**: Save backup state

- Save last sync time
- Record statistics
- Store error info
- Use test state directory
  **Test**: State persists between test runs

### Task 61: Add Sync Command

**Goal**: Manual sync trigger

- Add `photo-backup sync` command
- Run full backup
- Show results
- Support --test-mode flag
  **Test**: Manual sync to Minio works

### Task 62: Backup Functional Test

**Goal**: Full backup cycle

- Start Minio
- Create test photos
- Authenticate
- Run sync
- Verify files in Minio
- Save state
  **Test**: Complete backup to Minio succeeds

### Return to Task 42: Logging Functional Test

**Goal**: Complete logging system integration testing

- Return to Task 42 after implementing backup engine (Phase 6)
- Run comprehensive logging test during actual backup operations
- Verify all log levels work during real backup process
- Test file rotation with backup-generated logs
- Validate JSON format output during backup operations
- Ensure operation context, progress logging, and summary statistics work end-to-end
- **Prerequisites**: Complete Phase 6 (Backup Engine Core) - Tasks 53-62
- **Test**: Complete logging system works during real backup operations

## Phase 7: Drive Monitoring (Tasks 63-72)

### Task 63: Create Monitor Module

**Goal**: Basic monitoring structure

- Create `photo_backup/monitor.py`
- Add `DriveMonitor` class
- Define monitoring events
- In test mode, monitor test directory
  **Test**: Can instantiate monitor

### Task 64: Add Drive Detection

**Goal**: Detect drive presence

- Add `is_drive_mounted()` function
- Check specific path
- Return mount status
- Test mode checks test directory
  **Test**: Detects test directory presence

### Task 65: Implement Path Watching

**Goal**: Watch for changes

- Add basic file watching
- Detect new files
- Use polling for now
- Test with adding files to test dir
  **Test**: Detects new test photos

### Task 66: Add Change Debouncing

**Goal**: Batch rapid changes

- Implement debounce timer
- Wait for activity to settle
- Configurable delay (shorter in test mode)
  **Test**: Groups rapid test file additions

### Task 67: Create Change Summary

**Goal**: Summarize changes

- Track added/modified files
- Calculate total size
- Group by directory
  **Test**: Accurate summaries of test changes

### Task 68: Add Timer Implementation

**Goal**: Periodic checking

- Implement 4-hour timer (4 minutes in test mode)
- Check for changes
- Trigger if found
  **Test**: Timer fires in test mode timeframe

### Task 69: Create Monitor State

**Goal**: Track monitoring state

- Save last check time
- Record change history
- Persist between runs
  **Test**: State persists in test directory

### Task 70: Add Monitor Status

**Goal**: Show monitoring status

- Add status method
- Show last check
- List pending changes
  **Test**: Shows test monitoring status

### Task 71: Implement Change Reset

**Goal**: Clear change tracking

- Reset after backup
- Clear change list
- Update timestamps
  **Test**: Reset works after test backup**Test**: Loop runs with test timing

### Task 78: Implement Stop Command

**Goal**: Stop service

- Add `photo-backup stop` command
- Send shutdown signal
- Wait for completion
- Clean up test resources
  **Test**: Stops test service cleanly

### Task 79: Add Restart Command

**Goal**: Restart service

- Add `photo-backup restart` command
- Stop then start
- Preserve state
- Restart Minio if needed
  **Test**: Restarts test service

### Task 80: Create PID Management

**Goal**: Track process ID

- Write PID file
- Check for stale PIDs
- Clean up on exit
- Use test PID location
  **Test**: PID tracking in test mode

### Task 81: Add Service Logging

**Goal**: Log service events

- Log start/stop
- Log state changes
- Include timestamps
- Verbose in test mode
  **Test**: Service events logged

### Task 82: Service Functional Test

**Goal**: Full service lifecycle

- Start service in test mode
- Add photos to trigger backup
- Check status
- Stop service
- Verify Minio has all files
  **Test**: Complete service works with Minio

## Phase 8: Installation System (Tasks 83-92)

### Task 83: Create Install Script

**Goal**: Basic installer

- Create `install.py`
- Check prerequisites
- Create directories
- Support --test flag
  **Test**: Creates test structure

### Task 84: Add Dependency Check

**Goal**: Verify requirements

- Check Python version
- Check for rclone
- Check for 1Password CLI (skip in test)
- Check Docker for test mode
  **Test**: Reports dependencies correctly

### Task 85: Create launchd Plist

**Goal**: Generate service file

- Create plist template
- Fill in paths
- Set permissions
- Test mode uses different identifier
  **Test**: Valid test plist created

### Task 86: Implement Plist Installation

**Goal**: Install service

- Copy to LaunchAgents
- Load with launchctl
- Verify loaded
- Test mode uses test service name
  **Test**: Test service installed

### Task 87: Add Configuration Setup

**Goal**: Initialize config

- Copy example config
- Set default paths
- Create state directories
- Test mode uses test paths
  **Test**: Test config ready to use

### Task 88: Create Uninstall Script

**Goal**: Clean removal

- Stop service
- Remove plist
- Optional: remove data
- Clean test artifacts
  **Test**: Clean test uninstall

### Task 89: Add Install Validation

**Goal**: Verify installation

- Check all components
- Test permissions
- Run diagnostics
- Verify Minio in test mode
  **Test**: Reports test setup issues

### Task 90: Create Upgrade Support

**Goal**: Handle upgrades

- Detect existing install
- Preserve config
- Migrate state
- Handle test to production
  **Test**: Test upgrade works

### Task 91: Add Install UI

**Goal**: User-friendly install

- Show progress
- Confirm actions
- Display next steps
- Test mode instructions
  **Test**: Clear test install output

### Task 92: Installation Functional Test

**Goal**: Full install flow

- Fresh test install
- Configure for Minio
- Start service
- Verify operation
  **Test**: Complete test install works

## Phase 9: Verification System (Tasks 93-103)

### Task 93: Create Verify Module

**Goal**: Basic verification structure

- Create `photo_backup/verify.py`
- Add `Verifier` class
- Define verification jobs
- Support Minio verification
  **Test**: Can instantiate verifier

### Task 94: Add Hash Calculation

**Goal**: Calculate file hashes

- Add hash function
- Support large files
- Show progress
  **Test**: Hashes match for test photos

### Task 95: Implement Remote Listing

**Goal**: List remote files

- Use rclone to list Minio
- Parse output
- Extract hashes
  **Test**: Lists files in Minio bucket

### Task 96: Create Hash Comparison

**Goal**: Compare local/remote

- Match files by path
- Compare hashes
- Find differences
  **Test**: Finds mismatches in test set

### Task 97: Add Repair Function

**Goal**: Fix mismatches

- Re-upload bad files
- Verify after upload
- Log repairs
  **Test**: Repairs test files to Minio

### Task 98: Create Verification Report

**Goal**: Detailed report

- List all issues
- Show statistics
- Save to file
  **Test**: Report for test verification

### Task 99: Add Verify Command

**Goal**: Manual verification

- Add `photo-backup verify` command
- Run full check
- Show results
- Work with test mode
  **Test**: Verify against Minio works

### Task 100: Implement Cache System

**Goal**: Speed up verification

- Cache known good hashes
- Update after changes
- Validate cache
  **Test**: Cache speeds up test verify

### Task 101: Add Scheduled Verification

**Goal**: Monthly automatic check

- Check if due (daily in test mode)
- Run verification
- Send report
  **Test**: Schedules test verification

### Task 102: Add Minio Corruption Test

**Goal**: Test repair functionality

- Corrupt file in Minio
- Run verification
- Verify auto-repair
- Check corrected file
  **Test**: Detects and fixes corruption

### Task 103: Verification Functional Test

**Goal**: Full verification cycle

- Upload test photos to Minio
- Corrupt one file
- Run verification
- Verify repair
- Check final report
  **Test**: Complete verification with repair

## Final MVP Testing (Tasks 104-110)

### Task 104: End-to-End Test

**Goal**: Complete workflow test

- Install system in test mode
- Configure for Minio
- Add test photos
- Run full backup cycle
- Verify in Minio
  **Test**: Everything works together

### Task 105: Performance Test

**Goal**: Handle realistic dataset

- Generate 1000 test photos
- Test with Minio
- Measure performance
- Check resource usage
  **Test**: Performs acceptably

### Task 106: Error Recovery Test

**Goal**: Test failure handling

- Stop Minio mid-backup
- Restart Minio
- Verify recovery
- Check data integrity
  **Test**: Recovers from failures

### Task 107: Multi-Run Test

**Goal**: Test repeated operations

- Run multiple backup cycles
- Add photos between runs
- Verify incremental sync
- Check no duplicates
  **Test**: Incremental backups work

### Task 108: Test to Production Migration

**Goal**: Document production setup

- Create migration guide
- List config changes needed
- Remove test dependencies
- Production checklist
  **Test**: Clear migration path

### Task 109: Documentation Review

**Goal**: Complete documentation

- Update README with test instructions
- Add Minio setup guide
- Include troubleshooting
- Production setup guide
  **Test**: Docs help new user run tests

### Task 110: Release Preparation

**Goal**: Prepare for use

- Tag version
- Create changelog
- Final test suite run
- Remove test artifacts
  **Test**: Ready for production use

## Testing Infrastructure Notes

### Minio Setup

- Use Docker: `docker run -p 9000:9000 minio/minio server /data`
- Access at http://localhost:9000
- Default creds: minioadmin/minioadmin
- Create bucket: `my-photo-backup-bucket-test`

### Test Mode Features

- Accelerated timers (minutes instead of hours)
- Fixed Minio credentials
- Test directories in /tmp
- Verbose logging
- No 1Password requirement

### Functional Test Pattern

```python
# Example functional test structure
def test_backup_cycle():
    # Start Minio
    start_minio_container()

    # Create test environment
    create_test_photos("/tmp/test-photos")

    # Run backup
    result = subprocess.run([
        "photo-backup", "sync", "--test-mode"
    ], capture_output=True)

    # Verify in Minio
    assert verify_files_in_minio()

    # Cleanup
    cleanup_test_data()
    stop_minio_container()
```

## Implementation Notes

1. Each task should be completed and tested before moving to the next
2. Use functional tests via main.py, not unit tests
3. Test mode should make everything faster and local
4. Keep commits small - ideally one commit per task
5. If a task reveals missing dependencies, add them before continuing
6. Focus on working code over perfect code in the MVP
7. Document any deviations or additional requirements discovered
8. Always test with Minio before attempting Wasabi integration
