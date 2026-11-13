# Manual sync (CLI)

Covers: ["photo_backup/cli/sync_commands.py", "photo_backup/backup/**", "photo_backup/credentials/**", "photo_backup/config/**", "photo_backup/progress_parser.py", "photo_backup/state_utils.py", "photo_backup/main.py", "pyproject.toml", "uv.lock"]

`photo-backup sync` runs one backup immediately, independent of the daemon's timer: it validates the
environment (rclone present, credentials valid via `rclone lsd`), syncs source → bucket, prints
statistics and updates `backup_state.json`. With the global `--dry-run` it reports what would
transfer and uploads nothing.

## Sub-features

- `sync` uploads pending files, exit 0, `✅ Backup completed successfully!`.
- `dry-run` `photo-backup --dry-run sync`: exit 0, `🔍 DRY RUN MODE - No files will be transferred`, bucket unchanged.
- `verbose` `-v` adds credential status, rclone version, duration, return code.
- `invalid-env` (error path) validation failure → `❌ Backup environment validation failed:` and exit 1 (not observed).

## How to get to it (user POV)

- `photo-backup [--test-mode] [--dry-run] sync [--verbose|-v]`. No other options or body.

## Driving it with verify-photo-backup scripts

Required flags: none.

Preconditions: doctor OK. Add a file with `photos.sh` and run the CLI before the daemon's next check
(or accept that the daemon may sync it first; then `Files: 0/0` is the honest result).

- **Dry run.** `bash scripts/photos.sh add manual-$n.jpg 12`, then `bash scripts/cli.sh --dry-run sync` → `EXIT 0`, `Mode: TEST MODE (DRY RUN)`, `🔍 DRY RUN MODE - No files will be transferred`, `Backup SUCCESS (DRY RUN TEST MODE)`, `Files: 1/1 (100.0%)`.
- **Second view after dry run.** `bash scripts/s3.sh ls` → `manual-$n.jpg` absent.
- **Real sync.** `bash scripts/cli.sh sync -v` → `EXIT 0`, `✅ Backup environment validated successfully`, `✅ Backup completed successfully!`, `Files: 1/1 (100.0%)`.
- **Second view.** `bash scripts/s3.sh ls` → `12288 manual-$n.jpg`.

## Gotchas

- The daemon is running in the same stack and syncs the same source every ~18 s; a CLI sync racing it can legitimately report 0 files. Take a log barrier and check `applog.sh since $N "Backup completed"` to attribute the transfer.
- `--dry-run` is a global option: `cli.sh --dry-run sync`, not `cli.sh sync --dry-run`.
