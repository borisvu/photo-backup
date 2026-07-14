# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ IMPORTANT: Required Reading

**BEFORE working on this codebase, you MUST read these critical files:**

1. **`instructions.md`** - Contains essential coding protocols, testing approach, and implementation rules
2. **`architecture.md`** - Complete system architecture and design specifications  
3. **`tasks.md`** - Detailed task breakdown with 110+ granular implementation tasks
4. **`progress.yaml`** - Current implementation status and task completion tracking

These files contain vital context about the project's development methodology, architectural decisions, and current state. Working without understanding these documents will lead to implementation errors and architectural conflicts.

## Project Overview

This is a comprehensive Python-based photo backup system that automatically syncs photos from local storage to S3-compatible cloud storage (Wasabi S3). The system follows a robust architecture with extensive test coverage, configuration management, credential handling, and logging capabilities.

## Development Commands

### Core Development Tasks
- `make test` - Run all tests (unit, functional, integration)
- `make test-unit` - Run only unit tests
- `make test-functional` - Run only functional tests  
- `make test-integration` - Run only integration tests
- `make lint` - Run ruff and mypy linting
- `make lint-fix` - Auto-fix linting issues
- `make format` - Format code with ruff
- `make clean` - Clean cache and build files

### Testing Infrastructure
The project uses a comprehensive test mode with Minio for S3 simulation:
- Tests require Docker for Minio containers
- Test mode uses `/tmp/photo-backup-test/` directories
- Production mode uses `~/Library/Application Support/photo-backup/`
- Run tests with: `pytest tests/ -v`

### Application Commands
- `photo-backup --help` - Show all available commands
- `photo-backup config` - Display current configuration
- `photo-backup validate` - Validate configuration and dependencies  
- `photo-backup test-auth` - Test credential authentication
- `photo-backup sync --test-mode` - Run backup sync in test mode
- `photo-backup logs --tail 50` - View recent log entries

## Production Runtime (this machine)

How the system actually runs in production on the owner's Mac — this is operational
reality not otherwise derivable from the code:

- **Service:** runs as a launchd agent `com.example.photo-backup`
  (`~/Library/LaunchAgents/com.example.photo-backup.plist`, `KeepAlive=true`, so
  killing the process auto-respawns it). Installed as an **editable pip install**
  pointing at this repo, so source edits take effect on the next process restart.
- **Restart to load code changes:** `launchctl kickstart -k gui/$(id -u)/com.example.photo-backup`
- **Credentials:** Wasabi keys are env vars `WASABI_ACCESS_KEY` / `WASABI_SECRET_KEY`
  in the plist's `EnvironmentVariables` (**not** 1Password here; `config.yaml` keys
  are null). Because they live only in the service's environment, `photo-backup status`
  run from a normal shell may falsely report credentials unavailable. Rotation and
  the exact storage locations are documented in `photo-backup/KEY_ROTATION.md`.
- **Quick health check (no code reading):** `./check-status.sh` (repo root) or
  `photo-backup status` — shows whether the service is alive, whether rclone is
  transferring, and last-sync/verify state.
- **Paths:** logs `~/Library/Logs/photo-backup/`; state & hash cache
  `~/Library/Application Support/photo-backup/`; source `/Volumes/4TB-SSD/Photo`;
  dest bucket `my-photo-backup-bucket` (Wasabi, eu-central-2).
- **Verification listing gotcha:** the remote lister must use
  `rclone lsf --format sp` with `provider = Wasabi`. Do **not** use `rclone lsjson`
  or `--hash` or `provider = Other` — each triggers a per-object HEAD request that
  makes listing ~200k objects take >30 min (vs ~30s). Verification compares by
  **size + existence**, not MD5.
- **Commits are signed** via 1Password SSH (`op-ssh-sign`); the 1Password app must
  be unlocked or `git commit` fails. Pre-commit runs ruff + mypy. Never commit
  `.claude/settings.local.json`.

## Architecture Overview

### Core System Structure
```
photo-backup/                    # Project root
├── photo_backup/               # Main package
│   ├── main.py                 # CLI entry point
│   ├── backup.py               # Backup engine core
│   ├── config/                 # Configuration system
│   ├── cli/                    # CLI command modules
│   ├── credentials/            # Credential management
│   └── logger/                 # Comprehensive logging system
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── functional/             # End-to-end functional tests
│   └── integration/            # Integration tests
└── config.yaml.example        # Configuration template
```

### Key Components

**Configuration System** (`photo_backup/config/`):
- Multi-layered config loading (file → defaults → env vars → test mode)
- Supports both production (Wasabi) and test mode (Minio)
- Environment variable overrides with `PHOTO_BACKUP_*` prefix
- Comprehensive validation with detailed error messages

**Backup Engine** (`photo_backup/backup.py`):
- BackupEngine class orchestrates rclone-based sync operations
- BackupJob class represents individual backup tasks
- BackupStats class tracks comprehensive transfer metrics
- Real-time progress parsing from rclone output
- Support for dry-run mode and comprehensive error handling

**Credential Management** (`photo_backup/credentials/`):
- Direct credential support via environment variables (primary method)
- 1Password CLI integration as optional fallback
- Test mode uses hardcoded Minio credentials
- rclone-based credential validation

**Logging System** (`photo_backup/logger/`):
- Multi-format support (simple, detailed, JSON)
- Operation context tracking with job IDs
- Progress logging with rate limiting
- Summary statistics and cleanup functionality
- File rotation and comprehensive log viewing commands

### Test Architecture

**Test Modes**:
- **Unit Tests**: Fast, isolated, mock-based testing
- **Functional Tests**: End-to-end testing with Minio infrastructure
- **Integration Tests**: Component interaction testing

**Test Infrastructure**:
- Docker-based Minio containers for S3 simulation
- Automatic test photo generation with realistic file structures
- Comprehensive test fixtures and utilities in `tests/fixtures/`
- Test mode overrides for accelerated timers and local directories

## Development Workflow

### Task Implementation Progress
The project follows a structured task-based development approach documented in:
- `tasks.md` - Detailed task breakdown with 110+ granular tasks
- `architecture.md` - Complete system architecture specification
- `progress.yaml` - Current implementation status tracking

**CRITICAL REQUIREMENT**: After completing ANY task, you MUST update `progress.yaml` with:
- Task completion status and notes
- Any implementation details or deviations
- Test results and verification status
- Updated phase completion percentages

**Current Status**: 
- Phase 1-3: Complete (Foundation, Utilities, Configuration)
- Phase 4-6: In progress (Logging, Credentials, Backup Core)
- Phases 7-10: Pending (Monitoring, Service, Installation, Verification)

### Code Organization Principles
- **Modular Design**: Separate modules for each major functionality area
- **Test-Driven**: Every feature has corresponding test coverage
- **Configuration-Driven**: Behavior controlled through comprehensive config system
- **Error-First**: Robust error handling with detailed user feedback
- **Production-Ready**: Full logging, monitoring, and operational capabilities

### Key Implementation Notes
- Uses rclone as the underlying sync engine with comprehensive parameter tuning
- Implements sophisticated progress parsing from rclone output streams
- Maintains state persistence across runs with JSON and SQLite storage
- Supports both individual file tracking and bulk transfer statistics
- Provides multiple authentication methods with secure credential handling

### Testing Best Practices
- Always test in test mode first with Minio before production
- Use `--test-mode` flag to enable test configuration automatically
- Functional tests should clean up Docker containers and temp files
- Mock external dependencies in unit tests for reliable execution
- Integration tests verify component interactions without external services

This system represents a production-grade backup solution with enterprise-level logging, configuration management, and testing infrastructure suitable for personal photo archive management.