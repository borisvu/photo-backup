# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python 3.13 CLI/daemon (`photo-backup`, package `photo_backup/`) that watches a local photo
collection on an external SSD and syncs it to Wasabi S3 with rclone, then verifies the backup
(size + existence) and can repair it. Test mode targets a local MinIO instead of Wasabi.
Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Usage: [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Development Commands

Dependencies and the virtualenv are managed by **uv** (`pyproject.toml` + `uv.lock`, project at
the repo root). Run `uv sync` once to create `.venv/`; the `make` targets wrap `uv run`, or invoke
tools ad hoc with `uv run <cmd>` (e.g. `uv run pytest tests/unit -q`).

- `make test` / `make test-unit` / `make test-integration` / `make test-functional`
- `make lint` (ruff + mypy), `make lint-fix`, `make format`, `make check` (format check)
- `make clean`

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, `mypy photo_backup`
and the unit, integration and functional suites on every push to `master` and every PR. Tests
marked `launchd` (the macOS installer) are skipped where `launchctl` is missing and run in a
separate `macos-latest` job (no Docker there). Keep all of them green.

### Testing Infrastructure
- Functional tests need **Docker** and **rclone**. They start MinIO from the pinned image in
  `tests/fixtures/minio.py` (`pgsty/minio@sha256:…`; the official `minio/minio` image is no longer
  pullable). Override with `MINIO_TEST_IMAGE`.
- Tests that run the CLI use `sys.executable -m photo_backup.main`, never a bare `python`/`python3`.
- Test mode uses `/tmp/photo-backup-test/` (hard-coded, `consts.TEST_MODE_BASE_DIR`); functional
  tests `rm -rf` it. Production mode uses `~/Library/Application Support/photo-backup/`.
- End-to-end proof against a real daemon: the repo-local skill
  `.agents/skills/verify-photo-backup/` (TLS MinIO stand-in; `scripts/up.sh`, `doctor.sh`,
  `scenarios/smoke.sh`, `down.sh`). Its run evidence goes to `.verify/` (git-ignored).

### Application Commands
- `photo-backup --help`, `photo-backup config`, `photo-backup validate`, `photo-backup test-auth`
- `photo-backup [--test-mode] [--dry-run] sync`, `photo-backup verify [--repair]`, `photo-backup status`
- `photo-backup logs --tail 50`, `photo-backup start|stop|restart`

## rclone config rules (easy to break)

`BackupEngine._build_rclone_config` (sync) and `RemoteLister._build_rclone_config` (verify):
- The endpoint scheme is made explicit from `storage.use_ssl`; rclone treats a scheme-less endpoint
  as HTTPS, which silently broke plain-HTTP MinIO before.
- **Production:** `provider = Wasabi` plus `no_check_bucket = true` (restricted IAM policy).
- **Test mode (MinIO):** `provider = Minio`, which gives path-style addressing. rclone forces
  virtual-host addressing for Wasabi and ignores `force_path_style`. Test mode also omits
  `no_check_bucket`, so rclone creates the bucket.
- The remote lister must use `rclone lsf --format sp`. Do **not** use `rclone lsjson`, `--hash`
  or `provider = Other` in production: each one triggers a per-object HEAD request, which makes
  listing ~200k objects take more than 30 min instead of ~30 s. Verification compares by
  **size + existence**, not MD5.

## Production Runtime (owner's Mac)

How the system actually runs in production. This is operational reality, not derivable from the code:

- **Service:** launchd agent `com.example.photo-backup`
  (`~/Library/LaunchAgents/com.example.photo-backup.plist`, `KeepAlive=true`, so killing the
  process auto-respawns it). The plist runs the console script from the **uv-managed editable venv**
  of the production checkout: `<checkout>/.venv/bin/photo-backup`. Source edits take effect on the
  next restart. If `.venv` is deleted, re-run `uv sync` at the repo root or the service will
  crash-loop.
  - ⚠️ Before the project moved to the repo root, this path was `<checkout>/photo-backup/.venv/...`.
    When pulling that change on the production Mac, run `uv sync` at the root, point the plist
    at `<checkout>/.venv/bin/photo-backup`, then restart.
- **Restart to load code changes:** `launchctl kickstart -k gui/$(id -u)/com.example.photo-backup`
- **Credentials:** Wasabi keys are env vars `WASABI_ACCESS_KEY` / `WASABI_SECRET_KEY` in the
  plist's `EnvironmentVariables`. This install does **not** use 1Password, and the `config.yaml`
  keys are null. Because the keys live only in the service's environment, `photo-backup status`
  run from a normal shell may falsely report credentials unavailable. Rotation:
  [docs/KEY_ROTATION.md](docs/KEY_ROTATION.md).
- **Quick health check:** `./check-status.sh` or `photo-backup status`.
- **Paths:** logs `~/Library/Logs/photo-backup/`; state & hash cache
  `~/Library/Application Support/photo-backup/`; source `/Volumes/4TB-SSD/Photo`; dest bucket
  `my-photo-backup-bucket` (Wasabi, eu-central-2).
- **Commits are signed** via 1Password SSH (`op-ssh-sign`); the 1Password app must be unlocked or
  `git commit` fails. Pre-commit runs ruff + mypy. Never commit `.claude/settings.local.json`.

## Layout

```
photo_backup/      # package: main.py (CLI entry), cli/, config/, credentials/, backup/,
                   # monitor/, service/, verify/, logger/
tests/             # unit/, integration/, functional/ (Docker + rclone), fixtures/
scripts/           # manual performance / error-recovery test tooling
docs/              # architecture, user guide, production setup, key rotation
install.py         # macOS installer (launchd plist, config)
check-status.sh    # production health check
.agents/skills/verify-photo-backup/   # end-to-end verify skill (symlinked from .claude/skills/)
```
