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

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Verify Installation

```bash
# Check if virtual environment is active (should show a path)
echo $VIRTUAL_ENV

# Run tests to verify everything works
pytest tests/

# Check available commands
python -m photo_backup.main --help
```

### 3. Deactivate Virtual Environment

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
│   ├── requirements.txt      # Production dependencies
│   ├── requirements-dev.txt  # Development dependencies
│   └── README.md            # Development documentation
├── architecture.md           # System architecture
├── instructions.md           # Implementation guide
├── tasks.md                 # Task breakdown
└── README.md               # This file
```

## Development Commands

```bash
# Activate virtual environment
source photo-backup/venv/bin/activate

# Install dependencies
cd photo-backup
make install-dev

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

### Check Status

```bash
# Check if you're in a virtual environment
echo $VIRTUAL_ENV

# Check which Python you're using
which python

# Check installed packages
pip list
```

### Create New Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Deactivate

```bash
deactivate
```

## Requirements

- Python 3.8+
- Docker (for test infrastructure)
- Make (optional, for convenience commands)
- 1Password CLI (for credential management)
- rclone (for S3 operations)

## License

MIT License - see LICENSE file for details.
