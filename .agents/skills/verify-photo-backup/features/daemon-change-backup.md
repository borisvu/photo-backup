# Daemon: change detection → backup

Covers: ["photo_backup/service/**", "photo_backup/monitor/**", "photo_backup/backup/**", "photo_backup/credentials/**", "photo_backup/config/**", "photo_backup/verify/scheduler.py", "photo_backup/verify/verifier.py", "photo_backup/verify/remote_lister.py", "photo_backup/cli/service_commands.py", "photo_backup/main.py", "photo_backup/state_utils.py", "photo_backup/consts.py", "photo_backup/fs_utils.py", "photo_backup/progress_parser.py", "photo_backup/logger/**", "pyproject.toml", "uv.lock"]

The long-running service (`photo-backup start --foreground`, what launchd runs in production) polls
the source directory. On every check it compares a path→mtime snapshot with the previous one; any
added, modified or deleted file triggers an `rclone sync` of the whole source to the bucket, so local
deletes propagate. Hidden files, `Thumbs.db` and `.DS_Store` are excluded. Each sync updates
`backup_state.json`. On its first loop iteration it also runs the scheduled verification, which is
always due on a fresh state ("never run before").

## Sub-features

- `boot-scan` first check is immediate with an empty snapshot: every file already in the source counts as added.
- `boot-verify` first iteration runs scheduled verification (`Scheduled verification PASSED`), then once a day in test mode.
- `add` new files (nested dirs included) → uploaded with identical bytes.
- `modify` rewritten file (new size/content) → object replaced.
- `delete` removed file → object deleted (rclone sync semantics); other objects survive.
- `exclude` dot-files never reach the bucket.
- `state` `backup_state.json` totals and `last_stats` updated per sync.
- `fail` (error path) unreachable/HTTPS-mismatched endpoint → `Backup failed: ...` after rclone's retries (observed only against the plain-HTTP stand-in, run 20261113-190155; took 5m52s).

## How to get to it (user POV)

- No request body: the input is the contents of the watched directory (`backup.source_path`).
- Launched by `photo-backup [--test-mode] start [--foreground|--background]`; per source, `--background` still runs in the foreground ("Background mode requested but not implemented"; unverified, not driven).
- Check cadence = `monitoring.check_interval_hours` (env `PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS`), loop sleep = `service.loop_interval_seconds` (5 s in test mode).

## Driving it with verify-photo-backup scripts

Required flags: none.

Preconditions: doctor OK. Nothing else; the source starts empty.

- **Add.** `N=$(bash scripts/applog.sh mark)`, then `bash scripts/photos.sh add smoke-$n/album/a.jpg 200` (prints `<path> 204800 <md5>`), `bash scripts/photos.sh add .smoke-$n-hidden.jpg 4`.
- **Daemon reacts.** `bash scripts/applog.sh wait "Backup completed successfully" --after $N --timeout 90` → `... photo_backup.service INFO [...] - Backup completed successfully: 2 files transferred, 0.3 MB` (~18 s). Preceded by `Changes detected: 3 files, 344.0 KB` (the count includes the hidden file; the transfer does not).
- **Second view.** `bash scripts/s3.sh ls` → `204800 smoke-$n/album/a.jpg`; hidden file absent. `bash scripts/s3.sh md5 smoke-$n/album/a.jpg` → same md5 as `photos.sh`.
- **State.** `bash scripts/state.sh backup_state 's["total_files_transferred"]'` → previous + 2; `last_stats.success` `True`, `last_stats.source_path` = `$RUN_DIR/photos`.
- **Delete + modify.** barrier, `photos.sh rm <a>`, `photos.sh modify <b> 50` → `Changes detected: 2 files, 50.0 KB`, `Backup completed successfully: 1 files transferred, 0.0 MB`; `s3.sh ls` shows only `51200 <b>` with the new md5.
- **Whole journey:** `bash scenarios/smoke.sh` → 12 PASS, `smoke: PASS smoke-<ts>`.

## Gotchas

- Deletion checks need a populated target first and a surviving control; smoke gates the absence check on both objects having been listed.
- "Backup completed successfully" alone does not prove upload: with all files excluded the daemon still logs success with 0 files (red run 20261113-191248). Always check the bucket.
- `Changes detected: N files` counts excluded and deleted files too; it is not the transfer count.
- The daemon imported the code at start (editable install). After a source edit, doctor FAILs "sources changed since daemon start": down.sh && up.sh.
- Before the use_ssl fix, plain-HTTP S3 was broken in the product (the engine stripped the scheme, so rclone used HTTPS). This skill's MinIO stays on TLS, which is production-like and works on old and new targets.
