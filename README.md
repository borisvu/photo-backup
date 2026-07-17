# Photo Backup System

A Python-based automated backup solution that monitors a local photo collection on an external SSD and maintains synchronized copies on Wasabi S3 storage, following the 3-2-1 backup methodology.

## Project Overview

This system provides:

- **Automated Monitoring**: Detects when external SSD is connected and triggers backup
- **S3 Storage**: Syncs photos to Wasabi S3-compatible storage
- **Integrity Verification**: Validates backup integrity and provides auto-repair
- **Comprehensive Logging**: Detailed logging and progress reporting
- **Flexible Configuration**: Support for multiple credential providers and storage backends
- **Test Mode**: Local testing with Minio for development without Wasabi costs

## Quick Start

### 1. Set Up Virtual Environment

```bash
# Navigate to the project directory
cd /Users/you/git/backup-to-s3/photo-backup

# Create the virtual environment and install all dependencies (uv reads
# pyproject.toml + uv.lock and installs the project itself as editable).
uv sync

# Commands can then be run via `uv run <cmd>` without activating anything,
# or activate the env explicitly:
source .venv/bin/activate
```

### 2. Set Up Minio for Testing

The test suite uses Minio (S3-compatible storage) to simulate Wasabi without requiring real credentials or incurring costs.

```bash
# Start Minio container (required for tests)
docker run -d --name photo-backup-minio \
  -p 9000:9000 -p 9090:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio:latest server /data --console-address :9001

# Verify Minio is running
docker ps | grep photo-backup-minio

# Access Minio console at http://localhost:9090
# Login: minioadmin / minioadmin
```

**Note**: Tests will automatically start/stop Minio containers, but you can also run it manually for development.

### 3. Verify Installation

```bash
# Check if virtual environment is active (should show a path)
echo $VIRTUAL_ENV

# Run tests to verify everything works
cd photo-backup
pytest tests/

# Or use make commands
make test

# Check available commands
python -m photo_backup.main --help
```

### 4. Deactivate Virtual Environment

```bash
deactivate
```

## Key Documentation

### 📋 [Architecture Documentation](architecture.md)

Complete system architecture, design patterns, and technical specifications.

### 📖 [Implementation Instructions](instructions.md)

Step-by-step implementation guide and coding protocols.

### 📝 [Task List](tasks.md)

Detailed task breakdown and implementation roadmap.

### 🔧 [Project README](photo-backup/README.md)

Development setup, code quality tools, and project structure.

### 🚀 [Production Setup Guide](photo-backup/PRODUCTION_SETUP.md)

Complete guide for deploying the system in production with Wasabi S3.

### 👤 [User Guide](photo-backup/USER_GUIDE.md)

Practical guide for everyday operations - commands, workflows, and troubleshooting.

### 🔑 [Key Rotation Guide](photo-backup/KEY_ROTATION.md)

How to rotate the Wasabi S3 access key/secret, where credentials are stored, and how to reload the service.

## Project Structure

```
backup-to-s3/
├── photo-backup/              # Main Python package
│   ├── photo_backup/          # Core application code
│   │   ├── cli/              # Command-line interface
│   │   ├── config/           # Configuration management
│   │   ├── credentials/      # Credential providers
│   │   ├── logger/           # Logging system
│   │   └── main.py           # CLI entry point
│   ├── tests/                # Comprehensive test suite
│   ├── pyproject.toml        # Project metadata, deps & tool config
│   ├── uv.lock               # Locked dependency versions (uv)
│   └── README.md            # Development documentation
├── architecture.md           # System architecture
├── instructions.md           # Implementation guide
├── tasks.md                 # Task breakdown
└── README.md               # This file
```

## Development Commands

```bash
cd photo-backup

# Install all dependencies (creates .venv from uv.lock)
make install-dev   # == uv sync

# Run tests
make test

# Run linting
make lint

# Format code
make format

# Show all available commands
make help
```

## Virtual Environment Management

The environment is managed by [uv](https://docs.astral.sh/uv/). `uv sync` creates
`.venv/` from `pyproject.toml` + `uv.lock` and installs the project as editable.
You rarely need to activate it — `uv run <cmd>` uses the env automatically.

### Check Status

```bash
# Show the resolved environment / installed packages
uv pip list

# Which Python uv is using
uv run python -V
```

### Create / Refresh Environment

```bash
# Create .venv and install everything from the lockfile
uv sync

# Production deps only (no dev group)
uv sync --no-dev

# Update the lockfile after changing dependencies in pyproject.toml
uv lock
```

### Activate (optional)

```bash
source .venv/bin/activate   # then run tools directly; `deactivate` to exit
```

## Testing

### Running Tests

The project includes comprehensive test suites:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Functional Tests**: End-to-end workflows with Minio

```bash
# Run all tests
make test
# or
pytest tests/ -v

# Run specific test suites
make test-unit          # Unit tests only
make test-functional    # Functional tests only
make test-integration   # Integration tests only

# Run a specific test file
pytest tests/functional/test_end_to_end.py -v

# Run with coverage
pytest tests/ --cov=photo_backup --cov-report=html
```

### Test Mode

The system supports a special test mode that:

- Uses Minio instead of Wasabi (localhost:9000)
- Uses hardcoded test credentials (minioadmin/minioadmin)
- Operates on test directories (`/tmp/photo-backup-test/`)
- Runs with accelerated timers (minutes instead of hours)
- Skips 1Password integration
- Provides verbose logging

```bash
# Run commands in test mode
photo-backup sync --test-mode
photo-backup status --test-mode
photo-backup validate --test-mode
```

### Minio Setup Guide

#### Quick Start

```bash
# Start Minio container
docker run -d --name photo-backup-minio \
  -p 9000:9000 -p 9090:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio:latest server /data --console-address :9001
```

#### Using Minio Console

1. Open http://localhost:9090 in your browser
2. Login with `minioadmin` / `minioadmin`
3. Create bucket: `my-photo-backup-bucket-test` (or use the bucket name from your test config)
4. Verify bucket is accessible

#### Configure rclone for Minio (Optional)

```bash
# Configure rclone
rclone config

# Create new remote:
# - Name: minio-test
# - Type: s3
# - Provider: Minio
# - access_key_id: minioadmin
# - secret_access_key: minioadmin
# - endpoint: localhost:9000
# - region: us-east-1 (or any)

# Test connection
rclone lsd minio-test:
```

#### Stopping Minio

```bash
# Stop container
docker stop photo-backup-minio

# Remove container
docker rm photo-backup-minio

# Or stop and remove in one command
docker rm -f photo-backup-minio
```

#### Troubleshooting Minio

**Port already in use:**
```bash
# Check what's using port 9000
lsof -i :9000

# Use different ports
docker run -d --name photo-backup-minio \
  -p 9050:9000 -p 9140:9001 \
  ...
```

**Container won't start:**
```bash
# Check Docker logs
docker logs photo-backup-minio

# Check if Docker is running
docker ps

# Pull latest Minio image
docker pull minio/minio:latest
```

**Permission errors:**
```bash
# Ensure Docker has permissions
# On macOS: Docker Desktop must be running
# On Linux: Add user to docker group
sudo usermod -aG docker $USER
```

## Troubleshooting

### Test Failures

**Minio connection errors:**
- Ensure Docker is running: `docker ps`
- Check Minio container is running: `docker ps | grep minio`
- Verify port 9000 is accessible: `curl http://localhost:9000`
- Restart Minio container if needed

**Import errors:**
- Reinstall dependencies: `uv sync`
- Check Python version: `uv run python -V` (requires 3.13+)

**Permission errors:**
- Check file permissions on test directories
- Ensure write access to `/tmp/photo-backup-test/`
- On macOS, check System Preferences > Security & Privacy

**Test isolation issues:**
- Clean up test state: `rm -rf /tmp/photo-backup-test/`
- Stop all Minio containers: `docker stop $(docker ps -q --filter ancestor=minio/minio)`
- Run tests with `--no-cov` if coverage causes issues

### Development Issues

**Virtual environment problems:**
```bash
# Recreate the environment from scratch
rm -rf .venv
uv sync
```

**Make commands not working:**
- Ensure Make is installed: `make --version`
- Use direct commands instead (see `photo-backup/README.md`)

**Pre-commit hooks failing:**
```bash
# Skip hooks temporarily
git commit --no-verify

# Or fix issues
make lint-fix
make format
```

### Getting Help

- Check [Architecture Documentation](architecture.md) for system design
- Review [Task List](tasks.md) for implementation details
- See [Production Setup Guide](photo-backup/PRODUCTION_SETUP.md) for deployment help
- Check test files in `tests/` for usage examples

## Requirements

- **Python 3.13+** (required)
- **Docker** (required for test infrastructure)
- **Make** (optional, for convenience commands)
- **1Password CLI** (optional, for credential management in production)
- **rclone** (required for S3 operations)

## License

MIT License - see LICENSE file for details.
