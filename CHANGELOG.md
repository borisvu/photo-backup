# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Repository layout**: The Python project moved from the nested `photo-backup/` subdirectory to the repository root (`pyproject.toml`, `uv.lock`, `Makefile`, `photo_backup/`, `tests/`, `scripts/`, `install.py` are now top-level)
- **Documentation**: Guides moved to `docs/` (`ARCHITECTURE.md`, `USER_GUIDE.md`, `PRODUCTION_SETUP.md`, `KEY_ROTATION.md`); the root `README.md` is now the single entry point and absorbs the former development README
- **Packaging**: Dependencies and the virtualenv are managed by uv (`pyproject.toml` + `uv.lock`) on Python 3.13; `setup.py` and `requirements*.txt` are gone
- **Verification**: Integrity verification compares by size + existence using `rclone lsf --format sp`, which lists ~200k objects in seconds instead of issuing a HEAD per object

### Removed

- Planning artifacts: `tasks.md`, `progress.yaml`, `instructions.md`, the uv migration plan, Cursor rules (`.cursor/`), and `test_basic.py`

### Fixed

- **Plain-HTTP endpoints**: The daemon and `sync` now honour `storage.use_ssl`; previously they always used HTTPS, so plain-HTTP endpoints could not be reached
- **Test mode**: Uses rclone `provider = Minio` (path-style addressing) and lets rclone create the bucket
- **Tests**: Use a digest-pinned MinIO image (overridable via `MINIO_TEST_IMAGE`) since the official image is no longer pullable from Docker Hub; invoke the CLI via `sys.executable`; stale verifier unit tests updated for size + existence verification
- **Code quality**: mypy and ruff are clean
- Hash cache now respects the configured state directory, and cache writes are no longer O(n²)
- `status` no longer raises a false credentials alarm or pollutes `--json` output
- `job_id` `KeyError` spam from the detailed log formatter

### Added

- **CI**: GitHub Actions workflow (ruff check, ruff format check, mypy; unit, integration and functional tests with Docker + rclone)
- **verify-photo-backup skill**: Repo-local agent skill (`.agents/skills/verify-photo-backup/`) for end-to-end verification against a TLS MinIO stand-in
- `check-status.sh` health-check script and Wasabi key rotation guide (`docs/KEY_ROTATION.md`)
- MIT `LICENSE` file

## [0.1.1] - 2026-01-17

### Fixed

- **Wasabi S3 Compatibility**: Fixed backup engine to use `provider = Wasabi` instead of `provider = Other` for proper S3 API compatibility
- **Endpoint Handling**: Strip `https://` prefix from endpoints as rclone handles SSL internally
- **Bucket Checking**: Added `no_check_bucket = true` to avoid permission errors on restricted IAM policies

### Added

- **User Guide**: New comprehensive user guide (`USER_GUIDE.md`) with everyday usage instructions, command reference, and troubleshooting
- **Documentation Links**: Updated READMEs to link to the new User Guide

## [0.1.0] - 2026-01-17

### Added

#### Core Features
- **Automated Photo Backup**: Sync photos from external SSD to S3-compatible storage (Wasabi, Minio)
- **Drive Monitoring**: Automatic detection when external SSD is connected
- **Integrity Verification**: Hash-based verification with auto-repair capability
- **Incremental Sync**: Only uploads new/changed files on subsequent runs
- **Test Mode**: Local testing with Minio to avoid cloud costs during development

#### Configuration System
- YAML-based configuration (`config.yaml`)
- Environment variable overrides
- Test mode configuration with sensible defaults
- Support for multiple storage backends

#### Credential Management
- 1Password integration for secure credential storage (production)
- Environment variable fallback for CI/CD
- Test mode credentials (hardcoded Minio defaults)

#### Logging System
- Structured logging with configurable levels
- Console and file output
- Separate log files for different concerns
- JSON format option for machine parsing

#### Command-Line Interface
- `photo-backup sync` - Run backup synchronization
- `photo-backup status` - Show backup status
- `photo-backup validate` - Verify backup integrity
- `photo-backup verify` - Full verification with repair option
- `--test-mode` flag for all commands

#### Service Management
- macOS LaunchAgent support
- Automatic service installation/uninstallation
- Upgrade support with configuration preservation

#### Testing Infrastructure
- Comprehensive unit test suite
- Integration tests with Minio
- Functional end-to-end tests
- Error recovery testing
- Multi-run backup testing
- Performance testing framework

#### Documentation
- Architecture documentation (`architecture.md`)
- Implementation guide (`instructions.md`)
- Task breakdown (`tasks.md`)
- Production setup guide (`PRODUCTION_SETUP.md`)
- Test instructions and troubleshooting in README

### Technical Details

- **Python Version**: 3.13+ required
- **Storage**: S3-compatible (Wasabi, Minio, AWS S3)
- **File Transfer**: rclone-based for reliable transfers
- **Hash Algorithm**: SHA-256 for integrity verification
- **Container**: Docker-based Minio for testing

### Dependencies

- click >= 8.0 (CLI framework)
- PyYAML >= 6.0 (configuration)
- minio >= 7.0 (S3 operations)
- docker >= 6.0 (test infrastructure)
- pytest >= 7.0 (testing)

[Unreleased]: https://github.com/borisvu/photo-backup/compare/0.1.1...HEAD
[0.1.1]: https://github.com/borisvu/photo-backup/releases/tag/0.1.1
[0.1.0]: https://github.com/borisvu/photo-backup/releases/tag/v0.1.0
