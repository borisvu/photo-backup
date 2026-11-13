# Production Setup Guide

This guide walks you through setting up the Photo Backup System for production use with Wasabi S3 storage.

## Prerequisites

Before starting, ensure you have:

- **macOS** (tested on macOS 12+)
- **Python 3.13+** installed
- **rclone** installed (`brew install rclone`)
- **1Password CLI** (optional, for credential management) or environment variables for credentials
- **External drive** mounted at expected path (e.g., `/Volumes/4TB-SSD`)
- **Wasabi S3 account** with access credentials

### Verify Prerequisites

```bash
# Check Python version (3.13+ required)
python3 --version

# Check rclone installation
rclone version

# Check 1Password CLI (optional)
op --version
```

## Installation Steps

### 1. Clone and Install Dependencies

```bash
# Clone the project
git clone https://github.com/borisvu/photo-backup.git
cd photo-backup

# Create .venv/ and install production dependencies only (uv reads uv.lock;
# the project itself is installed editable). Use `uv sync` for dev tools too.
uv sync --no-dev

# Optional: activate so `photo-backup` is on your PATH
# (otherwise prefix commands with `uv run`)
source .venv/bin/activate
```

> The launchd service runs `.venv/bin/photo-backup` from this checkout. If `.venv` is
> ever deleted, re-run `uv sync` here or the service will crash-loop.

### 2. Run the Installer

```bash
# Run installation (creates directories, config, and launchd service)
uv run python install.py install
```

This will:
- Check all prerequisites
- Create required directories:
  - `~/Library/Application Support/photo-backup/` (state, config, temp)
  - `~/Library/Logs/photo-backup/` (logs)
- Copy example configuration
- Install launchd service plist

### 3. Configure Your Backup

Edit the configuration file:

```bash
# Open config for editing
nano ~/Library/Application\ Support/photo-backup/config/config.yaml
```

#### Required Configuration Values

| Setting | Description | Example |
|---------|-------------|---------|
| `backup.source_path` | Path to your photo directory | `/Volumes/4TB-SSD/Photo` |
| `backup.destination` | rclone remote:bucket | `wasabi-photo:my-photo-backup-bucket` |
| `storage.endpoint` | S3 endpoint | `s3.wasabisys.com` |

#### Example Production Config

```yaml
backup:
  source_path: "/Volumes/4TB-SSD/Photo"
  destination: "wasabi-photo:my-photo-backup-bucket"

storage:
  endpoint: "s3.wasabisys.com"
  access_key: null  # Retrieved from 1Password or env vars
  secret_key: null  # Retrieved from 1Password or env vars
  use_ssl: true

monitoring:
  check_interval_hours: 4
  mount_delay_minutes: 15
  change_delay_minutes: 30

logging:
  level: "INFO"
  directory: "~/Library/Logs/photo-backup"
```

### 4. Set Up Credentials

Choose ONE of these methods:

#### Option A: 1Password CLI (Recommended)

```bash
# Install 1Password CLI
brew install 1password-cli

# Sign in to 1Password
op signin

# Store your Wasabi credentials in 1Password with these fields:
# - access_key: Your Wasabi access key
# - secret_key: Your Wasabi secret key
```

The system will retrieve credentials from 1Password automatically.

#### Option B: Environment Variables

```bash
# Add to your ~/.zshrc or ~/.bash_profile
export WASABI_ACCESS_KEY="your-wasabi-access-key"
export WASABI_SECRET_KEY="your-wasabi-secret-key"
```

### 5. Configure rclone Remote

```bash
# Configure rclone for Wasabi
rclone config

# Create a new remote:
# - Name: wasabi-photo
# - Type: s3
# - Provider: Wasabi
# - access_key_id: (your key)
# - secret_access_key: (your secret)
# - region: (your region, e.g., us-east-1)
# - endpoint: s3.wasabisys.com
```

Test the connection:

```bash
# List bucket contents
rclone ls wasabi-photo:my-photo-backup-bucket
```

### 6. Validate Installation

```bash
# Verify everything is set up correctly
uv run python install.py validate

# Or use the CLI
photo-backup validate
```

### 7. Test the Backup (Dry Run)

```bash
# Activate the uv environment (or prefix commands with `uv run`)
source .venv/bin/activate

# Run a dry-run backup to verify configuration
photo-backup --dry-run sync
```

### 8. Start the Service

```bash
# Manual start
photo-backup start

# Or let launchd manage it (starts on drive mount)
launchctl load ~/Library/LaunchAgents/com.example.photo-backup.plist
```

## Directory Structure

After installation, you'll have:

```
~/Library/Application Support/photo-backup/
├── config/
│   └── config.yaml          # Your configuration
├── state/
│   ├── monitor_state.json   # File monitoring state
│   └── *.json               # Other state files
└── temp/
    └── photo-backup.pid     # Process ID file

~/Library/Logs/photo-backup/
├── backup.log               # Main log file
├── errors.log               # Error-only log
└── service.log              # launchd service output
```

## File Permissions

The installer sets secure permissions automatically:

| Path | Permissions | Notes |
|------|-------------|-------|
| `config.yaml` | 600 | Read/write owner only |
| `*.plist` | 600 | Read/write owner only |
| Directories | 755 | Standard directory permissions |

## Production Readiness Checklist

Before going live, verify:

### Configuration
- [ ] `source_path` points to your actual photo directory
- [ ] `destination` is your Wasabi bucket
- [ ] `storage.endpoint` is correct for your Wasabi region
- [ ] Logging level set to `INFO` or `WARNING` (not `DEBUG`)

### Credentials
- [ ] Credentials configured (1Password or env vars)
- [ ] Credentials validated with `photo-backup test-auth`
- [ ] rclone remote configured and tested

### Storage
- [ ] Wasabi bucket exists
- [ ] Bucket permissions allow read/write
- [ ] Sufficient storage quota available

### System
- [ ] External drive mounts at expected path
- [ ] Virtual environment activated for CLI use
- [ ] launchd service installed (if using automatic start)
- [ ] Log rotation configured (default: 30 days retention)

### Verification
- [ ] `uv run python install.py validate` passes
- [ ] `photo-backup validate` passes
- [ ] Dry-run sync completes without errors
- [ ] Test backup of small directory works

## Common Operations

### Check Status

```bash
photo-backup status
```

### View Logs

```bash
# Recent log entries
photo-backup logs

# Errors only
photo-backup logs --errors

# Follow logs in real-time
photo-backup logs --follow
```

### Manual Sync

```bash
# Run backup now
photo-backup sync

# Dry-run (no changes)
photo-backup --dry-run sync
```

### Service Control

```bash
# Start service
photo-backup start

# Stop service
photo-backup stop

# Restart service
photo-backup restart
```

## Troubleshooting

### Service Won't Start

```bash
# Check if already running
photo-backup status

# Check for PID file issues
ls -la ~/Library/Application\ Support/photo-backup/temp/

# View service logs
cat ~/Library/Logs/photo-backup/service-error.log
```

### Credential Errors

```bash
# Test authentication
photo-backup test-auth

# Verify rclone config
rclone config show wasabi-photo

# Test rclone connection
rclone lsd wasabi-photo:
```

### Drive Not Detected

```bash
# Check if drive is mounted
ls /Volumes/

# Check config source_path
photo-backup config
```

### Backup Failures

```bash
# Check error log
photo-backup logs --errors

# Run with verbose output
photo-backup sync --verbose

# Check rclone directly
rclone sync --dry-run /Volumes/4TB-SSD/Photo wasabi-photo:my-photo-backup-bucket
```

## Upgrading

To upgrade an existing installation:

```bash
# Pull latest code
git pull
uv sync --no-dev   # refresh dependencies from uv.lock

# Upgrade (preserves config)
uv run python install.py upgrade
```

## Uninstalling

```bash
# Remove service only (keeps data)
uv run python install.py uninstall

# Remove everything including data
uv run python install.py uninstall --remove-data
```

## Security Notes

1. **Credentials**: Never commit credentials to version control
2. **Config file**: Contains sensitive paths, permissions are 600
3. **Process**: Runs as your user, not root
4. **Network**: All Wasabi connections use HTTPS
5. **Logs**: May contain file paths; secure log directory appropriately

## Support

- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md); everyday usage: [USER_GUIDE.md](USER_GUIDE.md); key rotation: [KEY_ROTATION.md](KEY_ROTATION.md)
- Report issues: Create a GitHub issue
