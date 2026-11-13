# verify-photo-backup feature map

"User" here means whoever drives photo-backup: the owner dropping photos onto the source drive (the
daemon reacts), or the owner running a CLI command. Every recipe below was observed on a real run.

Service paths: ["photo_backup/**", "pyproject.toml", "uv.lock", "install.py", "config.yaml.example"]

Verified: daemon-change-backup.md 8ea4e968a62323dcd68935a304f79046292aa06e
Verified: manual-sync.md 8ea4e968a62323dcd68935a304f79046292aa06e
Verified: verify-repair.md 8ea4e968a62323dcd68935a304f79046292aa06e
Verified: status.md 8ea4e968a62323dcd68935a304f79046292aa06e

## Baseline preconditions

- An active run (`scripts/up.sh`) and `scripts/doctor.sh` → `doctor: OK`.
- Fresh state per run: empty bucket `my-photo-backup-bucket-test`, empty source `$RUN_DIR/photos`,
  no JSON state. The daemon has already done its boot iteration (boot verification over nothing).
- Unique names per scenario (`smoke-$(date +%s)`); the bucket and state accumulate within a run.
- Never drive a stack this run did not start; never run `.venv/bin/photo-backup` by hand (use `cli.sh`).
- No tenants, no feature flags. Required flags for every recipe: none.

## Driving conventions

| Surface | Helper |
|---|---|
| Source drive (daemon input) | `scripts/photos.sh add/modify/rm/ls` |
| Daemon output (async) | `N=$(scripts/applog.sh mark)` BEFORE acting, then `scripts/applog.sh wait '<ERE>' --after $N` |
| One-shot CLI | `scripts/cli.sh [--dry-run] <subcommand> [args]` (stdout printed, app log lines on stderr) |
| Bucket (second view, MinIO's own `mc`) | `scripts/s3.sh ls` / `md5 <key>`; FIXTURE ops `fixture-rm`, `fixture-put` |
| Persisted state | `scripts/state.sh backup_state|monitor_state|verification_schedule ['<expr on s>']` |

The daemon is async: poll its log after a barrier, never sleep. With the default
`VERIFY_CHECK_INTERVAL_HOURS=0.005` a change is picked up within ~18–20 s.

## Proof and skip reporting

- **Daemon proof:** the source change (photos.sh evidence with size + md5), the daemon log line after
  the barrier, the bucket listing + md5 of the object, and the `backup_state` delta.
- **CLI proof:** the `cli.sh` evidence (command, exit code, stdout, stderr) plus a second view
  (`s3.sh` or `state.sh`). Exit code and the bucket must agree with the printed verdict.
- **Unreachable path:** report the attempted command and the unmet precondition. Targets older than
  the use_ssl fix cannot sync to plain-HTTP S3 (see Gotchas in SKILL.md); that is not a skip reason for TLS paths.

## Feature entry contract

Each feature file has exactly one `Covers:` JSON line, then the H2s `Sub-features`,
`How to get to it (user POV)`, `Driving it with verify-photo-backup scripts`, `Gotchas`. Expected
results are the observed ones. Only a VERIFIED live drive advances that feature's `Verified:` line.

## Features

- [daemon-change-backup.md](daemon-change-backup.md) — daemon detects add/modify/delete in the source and syncs; boot-time scheduled verification. Evidence: runs 20261113-190938 (probe + smoke), 20261113-191349 (green smoke), red 20261113-191248.
- [manual-sync.md](manual-sync.md) — `photo-backup sync` and `--dry-run sync`. Evidence: run 20261113-190938 files 027–031.
- [verify-repair.md](verify-repair.md) — `photo-backup verify`, `--repair`. Evidence: run 20261113-190938 files 015–025.
- [status.md](status.md) — `photo-backup status --json`. Evidence: run 20261113-190938 file 026, run 20261113-191349.

## Not yet mapped

- `test-auth` — `photo_backup/cli/auth_commands.py` (its bucket bootstrap builds an rclone `minio:` remote with `--s3-no-ssl` only when use_ssl is false).
- `validate`, `config`, `setup-config` — `photo_backup/cli/config_commands.py`. `validate` probes MinIO with a hard-coded `http://` curl, so against the TLS stand-in it is expected to report the endpoint unreachable (not observed).
- `check-deps` — `photo_backup/cli/deps_commands.py`, `photo_backup/deps.py`.
- `logs` (tail/level/follow) — `photo_backup/cli/log_commands.py`; app log file is `/tmp/photo-backup-test/logs/photo-backup.log` (snapshotted to `app-state/` by down.sh).
- `stop`, `restart` (PID-file signalling) — `photo_backup/cli/service_commands.py`, `photo_backup/service/manager.py`. cli.sh refuses them because they act on the run's own daemon.
- Drive unmount / mount-delay handling — `photo_backup/monitor/monitor.py` (`is_drive_mounted`).
- Scheduled verification FAILED + auto-repair path, interval rollover — `photo_backup/verify/scheduler.py`.
- `verify --save-report` / `--report-path` — `photo_backup/cli/verify_commands.py`, `photo_backup/verify/models.py` (default path lands under the fake HOME).
- Log cleanup/rotation — `photo_backup/logger/cleanup.py`, `photo_backup/logger/core.py`.
- 1Password credential provider — `photo_backup/credentials/providers/onepassword.py`, `photo_backup/credentials/session/`.
- Installer — `install.py` (writes launchd plist; out of scope for a local stack).
- Production mode (Wasabi, `~/Library/Application Support/photo-backup`) — deliberately never driven.
