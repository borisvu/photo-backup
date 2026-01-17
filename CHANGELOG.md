# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/yourusername/backup-to-s3/releases/tag/v0.1.0
