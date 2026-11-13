---
name: verify-photo-backup
description: Launch the photo-backup daemon (photo-backup start, the launchd service) from the code on disk against its own TLS MinIO stand-in for Wasabi, and drive it the way its owner does — drop photos into the watched source dir, run the sync / verify --repair / status CLI — capturing bucket, state and log evidence. Use to reproduce or prove a photo-backup bug fix or behavior change end to end, not just in unit tests.
---

# Verify photo-backup

Real: the daemon (`photo-backup --test-mode start --foreground`, the same entry point launchd runs)
from this target's editable uv venv, the real `rclone` binary, a real S3 server (MinIO, pinned
`pgsty/minio` digest) with the bucket the tests create, the app's real JSON state. Stand-in: MinIO
over **TLS** replaces Wasabi (production is HTTPS; test mode uses rclone `provider = Minio`,
path-style, see Gotchas). Shortened: the monitor check interval
(`VERIFY_CHECK_INTERVAL_HOURS`, default 0.005 h = 18 s) via the repo's own `PHOTO_BACKUP_*` env
override. No feature flags exist in this service. Production mode is never run.

Paths are relative to this skill directory. Every script refuses to drive a stack it did not start.

## Launch

```bash
bash scripts/up.sh                # ~5 s warm, ~18 s cold (creates the repo-root .venv via uv sync --frozen --offline)
```

Ready = `READY:` line, meaning: daemon alive and named in its PID file, `Entering main service loop`
logged, the boot iteration's scheduled verification finished, MinIO healthy over TLS, bucket exists.
Needs: Docker (OrbStack: `orb start`), `rclone`, `uv`, `openssl`, free port `VERIFY_MINIO_PORT`
(default 59000) and an **absent `/tmp/photo-backup-test`** — the app hard-codes test-mode state, PID
file and logs there (`consts.TEST_MODE_BASE_DIR`). One run at a time; never alongside
`make test-functional` (those tests `rm -rf` that directory). up.sh refuses if it exists.

## Doctor

```bash
bash scripts/doctor.sh            # read-only; exit 0 = worth driving
```

Checks: daemon pid alive and is this target's `photo-backup ... start --foreground`; owns the PID
file and `/tmp/photo-backup-test` (marker); MinIO healthy; svc_ready; HEAD unchanged; no
non-loopback TCP from daemon or its rclone children; the app's own `config` output shows endpoint
`localhost:$VERIFY_MINIO_PORT`, source `$RUN_DIR/photos`, no Wasabi; daemon env has the fake HOME
and no `WASABI_*`/`S3_*` keys; **no `.py` under `photo_backup/` newer than daemon start** (editable
install: the daemon holds the code it imported). FAIL on that = `down.sh && up.sh` before trusting a result.

## Drive

```bash
bash scripts/photos.sh add|modify|rm <rel/path.jpg> [KB]   # the watched source dir (daemon input)
bash scripts/photos.sh ls                                  # path size md5
N=$(bash scripts/applog.sh mark)                           # barrier BEFORE acting
bash scripts/applog.sh wait 'Backup completed successfully' --after "$N" [--timeout 90]
bash scripts/applog.sh since "$N" [ERE]
bash scripts/cli.sh [--dry-run] <sync|verify|status|...> [args]   # one-shot CLI in the daemon's env
bash scripts/s3.sh ls | md5 <key>                          # bucket via MinIO's own mc (second view)
bash scripts/s3.sh fixture-rm <key> | fixture-put <key> KB # FIXTURE damage for verify/repair
bash scripts/state.sh backup_state|monitor_state|verification_schedule ['s["total_syncs"]']
bash scenarios/smoke.sh           # daemon journey: add -> synced bytes -> state -> delete w/ control -> verify; ~40 s, exit 0 = all PASS
```

Never call `.venv/bin/photo-backup` directly: without `cli.sh`'s environment it reads
your real HOME config and, without `--test-mode`, the production state dir.

Cheap selective scope (no Docker): `PATH=/usr/bin:$PATH bash scripts/affected.sh` compares each
feature’s last VERIFIED commit to HEAD; `... affected.sh <base> [<head>]` diagnoses an explicit
range. (`PATH=/usr/bin:$PATH` only because this Mac's `python3` is a broken mise shim; the system
Python 3.9 satisfies the selector.) Record VERIFIED / NOT VERIFIED / INCONCLUSIVE per driven
feature; only VERIFIED advances its index record. Optional hooks require explicit acceptance:
`python3 scripts/hooks.py install`; undo with `python3 scripts/hooks.py uninstall`. Hooks only flag
stale work in `.verify/photo-backup/pending`.

Recipes per feature: [features/README.md](features/README.md).

## Evidence

`<skill-home-repo>/.verify/photo-backup/<run-id>/` holds `evidence/NNN-*.txt` (one per helper call),
`timeline.log`, `app.log` (daemon console), `state.env` (target path + full sha, flags none, minio
port, check interval, rclone version, daemon start epoch), the generated certs, `tmp/` (rclone
configs the app wrote — test credentials only), and after `down.sh` an `app-state/` snapshot of
`/tmp/photo-backup-test` (JSON state, app log file, PID file). Git-ignored; survives cleanup.
Proof = the source change, the daemon/CLI output, and the resulting bucket bytes + state. For a fix:
a red run on the old code and a green run on the new, with both run ids.

## Cleanup

```bash
bash scripts/down.sh              # SIGTERM our daemon only, snapshot + remove /tmp/photo-backup-test (if our marker), compose down -v
```

## Gotchas

- **Plain HTTP was a product defect until the CI commit:** before it, `BackupEngine._build_rclone_config` stripped the scheme, so rclone always used HTTPS and every daemon sync against plain-HTTP S3 failed after ~6 min of retries (`Backup failed: ... server gave HTTP response to HTTPS client`, run 20261113-190155), while `verify`/`status` looked healthy. The engine now honours `use_ssl`. This stand-in stays on TLS because production is HTTPS. On a red worktree older than that fix, keep TLS: plain HTTP cannot sync there.
- `minio/minio` is gone from Docker Hub and quay.io refuses anonymous pulls. compose.yml and the repo's functional tests (`tests/fixtures/minio.py`) pin `pgsty/minio` by digest; if it disappears, any MinIO build with `mc` + `curl` works.
- Test mode uses rclone `provider = Minio` (path style: `https://localhost:<port>/<bucket>`); production uses `provider = Wasabi` (virtual host). Older targets used `Wasabi` in test mode too, which addresses `https://<bucket>.localhost:<port>`. That is why compose sets `MINIO_DOMAIN=localhost` and the cert SANs cover `*.localhost` (macOS resolves it to loopback), so both work.
- Hard-coded paths the app ignores config for: `/tmp/photo-backup-test` (test mode) and `~/Library/Application Support/photo-backup` (production) for state/PID; `~/.photo-backup` for verify cache/report fallbacks; `~/.config/photo-backup/config.yaml` is a config source that would override test defaults. The fake `HOME=$RUN_DIR/home` + forced `--test-mode` neutralize all of them.
- Earlier test runs on this Mac wrote into the real `~/Library/Logs/photo-backup` and `~/Library/Application Support/photo-backup` (both predate this skill). This skill never touches them.
- `uv` discovery hits a mise/pyenv shim recursion for `python3.13` on this Mac; svc_deps passes a real interpreter (`VERIFY_PYTHON` overrides). Host `python3` is the same broken shim, so helpers use the venv's Python.
- The monitor's first check is immediate with an empty snapshot: anything already in the source at boot is "added" and synced. Readiness waits for the boot iteration so drives never race it.
- `Backup completed successfully` is logged even when 0 files moved (all excluded). Always confirm in the bucket.
- `Changes detected: N files` counts excluded and deleted files too.
- Test-mode env overrides bypass the config-file validator, which is how a sub-0.1 h interval works. A config *file* with that value would be rejected.

## Red/green worktrees

Keep this skill in its home repo. From that repo create isolated targets (use new branches):

```bash
git worktree add -b verify-red /tmp/verify-red <old-commit>
git worktree add -b verify-green /tmp/verify-green <fix-commit>
# From the skill directory, repeat for red and green:
export VERIFY_REPO=/tmp/verify-red
bash scripts/up.sh                # svc_deps creates that worktree's own .venv offline, or prints the exact command
bash scripts/doctor.sh            # target sha, flags none
bash scenarios/smoke.sh           # or the feature recipe for the bug; keep source + bucket + state evidence
bash scripts/down.sh
# Repeat with VERIFY_REPO=/tmp/verify-green, then remove both worktrees.
```

Every script uses VERIFY_REPO (default: skill home repo); svc_deps refuses a venv that imports
`photo_backup` from anywhere but that target. Use the same target through down.sh. state.env records
TARGET_PATH and TARGET_SHA. Proof stays in the home repo after worktree removal.
