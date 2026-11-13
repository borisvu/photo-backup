# Photo Backup User Guide

A practical guide to installing and using the Photo Backup System.

## Overview

The Photo Backup System automatically backs up your photo collection from an external drive to cloud storage (Wasabi S3). Once configured, it monitors your drive and syncs changes automatically.

**Key Features:**
- Automatic backup when your external drive is connected
- Incremental sync (only uploads new/changed files)
- Integrity verification to catch and repair corruption
- Detailed logging of all operations

## Installation

### Requirements

- **macOS** (tested on macOS 12+)
- **Python 3.13+**
- **Docker** (for running tests)
- **rclone** (`brew install rclone`)
- **Wasabi account** (or other S3-compatible storage)

### Step 1: Download the Project

```bash
# Clone the repository
git clone https://github.com/borisvu/photo-backup.git
cd photo-backup
```

### Step 2: Install Dependencies

Dependencies are managed by [uv](https://docs.astral.sh/uv/) (`brew install uv`):

```bash
# Creates .venv/ from uv.lock and installs the project (editable)
uv sync

# Optional: activate the env so `photo-backup` is on your PATH
# (otherwise prefix commands with `uv run`)
source .venv/bin/activate
```

### Step 3: Run the Installer

```bash
uv run python install.py install
```

This creates:
- Configuration directory: `~/Library/Application Support/photo-backup/`
- Log directory: `~/Library/Logs/photo-backup/`
- LaunchAgent for automatic startup

### Step 4: Configure Your Backup

Edit the configuration file:

```bash
nano ~/Library/Application\ Support/photo-backup/config/config.yaml
```

Set these required values:

```yaml
backup:
  source_path: "/Volumes/YOUR-DRIVE/Photos"    # Your photo directory
  destination: "wasabi-photo:your-bucket-name"  # Your S3 bucket

storage:
  endpoint: "s3.wasabisys.com"  # Or your S3 endpoint
```

### Step 5: Set Up Credentials

**Option A: Environment Variables (simpler)**

Add to your `~/.zshrc`:
```bash
export WASABI_ACCESS_KEY="your-access-key"
export WASABI_SECRET_KEY="your-secret-key"
```

Then reload: `source ~/.zshrc`

**Option B: 1Password CLI (more secure)**

Store credentials in 1Password and the system retrieves them automatically.

### Step 6: Configure rclone

```bash
rclone config
```

Create a remote named `wasabi-photo` (or whatever matches your config) with your S3 credentials.

### Step 7: Validate Installation

```bash
# Check everything is set up correctly
photo-backup validate

# Test your credentials
photo-backup test-auth

# Do a dry-run to preview what would be backed up
photo-backup --dry-run sync
```

### Step 8: Start Using It

```bash
# Run your first backup
photo-backup sync

# Check status
photo-backup status
```

**That's it!** The system will now automatically back up when your drive is connected.

---

For detailed production configuration options, see [Production Setup Guide](PRODUCTION_SETUP.md).

---

## Quick Reference

| Task | Command |
|------|---------|
| Check if backup is running | `photo-backup status` |
| Run a backup now | `photo-backup sync` |
| Preview what would be synced | `photo-backup --dry-run sync` |
| Verify backup integrity | `photo-backup verify` |
| View recent logs | `photo-backup logs` |
| See configuration | `photo-backup config` |

## Before Running Commands

Make sure:
1. You're in the repo with the uv environment active (or prefix each command with `uv run`):
   ```bash
   cd /path/to/photo-backup
   source .venv/bin/activate
   ```
2. Your external drive is connected and mounted

## Understanding the Commands

### Check Status

```bash
photo-backup status
```

Shows:
- Whether the backup service is running
- Last backup time and result
- Number of files backed up
- Any pending operations

**When to use:** Check this first if you're unsure about the system state.

---

### Run a Backup

```bash
photo-backup sync
```

Syncs your photo directory to cloud storage. Only uploads files that are new or changed since the last sync.

**Options:**
```bash
photo-backup --dry-run sync    # Preview changes without uploading
photo-backup sync --verbose    # Show detailed progress
```

**When to use:**
- Your drive has been connected for a while but backup hasn't run
- You want to manually trigger a backup
- After adding a large batch of photos

---

### Verify Backup Integrity

```bash
photo-backup verify
```

Compares local files with cloud backup to ensure everything is correctly backed up.

**What it checks:**
- All local files exist in the backup
- File sizes match
- File hashes match (content is identical)

**Options:**
```bash
photo-backup verify --quick       # Check counts only (faster)
photo-backup verify --repair      # Automatically fix any issues found
photo-backup verify --path 2024/  # Verify specific folder only
```

**When to use:**
- Monthly integrity check (recommended)
- After recovering from errors
- Before deleting local files

---

### View Logs

```bash
photo-backup logs
```

Shows recent backup activity and any issues.

**Options:**
```bash
photo-backup logs --errors     # Show errors only
photo-backup logs --follow     # Watch logs in real-time (Ctrl+C to exit)
photo-backup logs --lines 50   # Show last 50 lines
```

**When to use:**
- Troubleshooting backup issues
- Checking what was backed up recently
- Monitoring a running backup

---

### Service Control

The backup service runs in the background, monitoring for drive connections.

```bash
photo-backup start     # Start the service
photo-backup stop      # Stop the service
photo-backup restart   # Restart the service
```

**Note:** The service starts automatically when configured with launchd. You typically don't need these commands unless troubleshooting.

---

### View Configuration

```bash
photo-backup config
```

Shows your current settings without revealing sensitive credentials.

**When to use:**
- Confirming which drive/folder is being backed up
- Checking the backup destination
- Verifying settings before a sync

---

### Test Authentication

```bash
photo-backup test-auth
```

Verifies your cloud storage credentials are working.

**When to use:**
- After initial setup
- If backups are failing with authentication errors
- After changing credentials

---

### Validate Setup

```bash
photo-backup validate
```

Checks your entire configuration and system requirements.

**What it verifies:**
- Configuration file is valid
- Required tools are installed (rclone, etc.)
- Credentials work
- Source path exists
- Destination is accessible

**When to use:**
- After installation
- After changing configuration
- When troubleshooting issues

---

### Check Dependencies

```bash
photo-backup check-deps
```

Verifies all required system tools are installed.

**When to use:**
- After system updates
- If backups fail with "command not found" errors

## Common Workflows

### Daily Use (Automatic)

1. Connect your external drive
2. The system detects the drive automatically
3. After a short delay (to allow drive to fully mount), backup begins
4. Check status anytime with `photo-backup status`

You don't need to do anything - it's automatic!

### Manual Backup After Adding Photos

1. Connect your drive
2. Copy new photos to your photo directory
3. Wait for the automatic backup, or run:
   ```bash
   photo-backup sync
   ```
4. Verify success:
   ```bash
   photo-backup status
   ```

### Monthly Integrity Check

Run this monthly to ensure your backups are healthy:

```bash
# Full verification
photo-backup verify

# If issues are found, repair them
photo-backup verify --repair
```

### Before Deleting Local Files

If you need to free up space on your drive:

```bash
# First, verify those files are backed up
photo-backup verify --path "2020/"

# Check the report - ensure all files are "OK"
# Only then delete local files
```

### Troubleshooting a Failed Backup

1. Check the status:
   ```bash
   photo-backup status
   ```

2. Look at recent errors:
   ```bash
   photo-backup logs --errors
   ```

3. Validate your setup:
   ```bash
   photo-backup validate
   ```

4. Test authentication:
   ```bash
   photo-backup test-auth
   ```

5. Try a dry-run to see what would happen:
   ```bash
   photo-backup --dry-run sync
   ```

## Understanding Backup Behavior

### What Gets Backed Up

- All files in your configured source directory
- Subdirectory structure is preserved
- File names and metadata are preserved

### What Triggers a Backup

1. **Drive Connection**: When your external drive is mounted
2. **Manual Sync**: When you run `photo-backup sync`
3. **Scheduled Check**: Periodic checks if service is running

### Incremental Sync

The system tracks what's already backed up:
- New files are uploaded
- Changed files are re-uploaded
- Deleted files remain in cloud (not automatically deleted)
- Unchanged files are skipped

This makes subsequent backups fast.

### Timing Delays

The system has built-in delays to prevent issues:
- **Mount delay**: Waits 15 minutes after drive mount (configurable)
- **Change delay**: Waits 30 minutes after changes settle (configurable)

These prevent backups from starting mid-copy.

## Frequently Asked Questions

### How do I know a backup completed successfully?

Run `photo-backup status`. It shows:
- Last backup time
- Whether it completed
- Number of files synced
- Any errors

### How long does a backup take?

Depends on:
- Number of new/changed files
- Your internet upload speed
- File sizes

First backup of a large collection may take hours or days. Subsequent backups are usually quick (minutes) since only new files are uploaded.

### Can I use my computer during backup?

Yes! The backup runs in the background and uses minimal resources. You can continue working, though upload-heavy tasks may be slower.

### What happens if I disconnect the drive during backup?

The backup stops safely. Next time you connect, it resumes where it left off. No data is corrupted.

### What happens if my internet disconnects during backup?

The backup retries automatically. Failed files are retried on the next sync. Check logs for details.

### How do I back up a different folder?

Edit your configuration:
```bash
nano ~/Library/Application\ Support/photo-backup/config/config.yaml
```
Change the `source_path` setting.

### Can I exclude certain files or folders?

Yes, rclone supports exclude patterns. Add them to your rclone configuration or use the `--exclude` flag.

### How do I restore files from backup?

Use rclone directly:
```bash
# List what's in backup
rclone ls wasabi-photo:your-bucket-name

# Download a specific file
rclone copy wasabi-photo:your-bucket-name/2024/photo.jpg ./restored/

# Download an entire folder
rclone copy wasabi-photo:your-bucket-name/2024/ ./restored-2024/
```

### How much storage space do I need?

Your cloud storage needs at least as much space as your photo collection. Wasabi charges ~$7/TB/month with no egress fees.

### Is my data secure?

- All transfers use HTTPS encryption
- Credentials are stored securely (1Password or environment variables)
- Cloud storage is encrypted at rest (Wasabi default)
- Only you have access with your credentials

## Test Mode

For testing without affecting your real backups:

```bash
photo-backup --test-mode sync
photo-backup --test-mode status
photo-backup --test-mode verify
```

Test mode:
- Uses local Minio instead of Wasabi
- Uses temporary directories
- Runs with accelerated timers
- Perfect for learning or development

## Getting Help

- **Configuration issues**: Run `photo-backup validate`
- **View all options**: Run `photo-backup --help`
- **Command help**: Run `photo-backup COMMAND --help`
- **Architecture details**: See [Architecture](ARCHITECTURE.md)
- **Setup guide**: See [Production Setup Guide](PRODUCTION_SETUP.md)

## Tips for Best Results

1. **Keep your drive connected** when adding photos - let the automatic backup handle it
2. **Run monthly verifications** to catch any issues early
3. **Check status occasionally** to confirm backups are running
4. **Review logs** if anything seems wrong
5. **Keep the service running** - it uses minimal resources when idle
