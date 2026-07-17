# UV Migration Plan — photo-backup

Status tracker + resumable runbook for porting this repo from
`setup.py` + `requirements*.txt` + pyenv/pip to **uv** (pyproject `[project]` +
`uv.lock` + project `.venv`).

Branch: `uv-migration`. Do all work here; production keeps running off the old
pyenv editable install until Step 7 repoints the service.

## Key facts (as of migration start)
- Package dir: `photo-backup/` (packaging files live here, NOT repo root).
- Package: `photo_backup`, setuptools `find_packages`, console script
  `photo-backup = photo_backup.main:main`.
- Version: single source `photo-backup/photo_backup/__version__.py` (`0.1.0`).
- Runtime deps: `PyYAML>=6.0`, `click>=8.0`, `minio>=7.0`.
- Dev deps: pytest, docker, pytest-sugar, pytest-clarity, pytest-cov, ruff, mypy,
  pre-commit.
- Python: 3.13.3 (pyenv). `.python-version` = `3.13.3`.
- **Production service** (launchd `com.example.photo-backup`) runs:
  `/Users/you/.pyenv/versions/3.13.3/bin/photo-backup start`
  from the current editable install. Plist:
  `~/Library/LaunchAgents/com.example.photo-backup.plist`, `KeepAlive=true`.
- `uv` was NOT installed at start.
- No CI (`.github/workflows` absent). pre-commit uses its OWN isolated envs, so
  it is independent of the project venv and needs no change for uv.

## Rollback (fast, always available)
1. Production is unaffected until Step 7. To undo Step 7:
   restore `~/Library/LaunchAgents/com.example.photo-backup.plist` from the backup
   `com.example.photo-backup.plist.pre-uv.bak`, then
   `launchctl kickstart -k gui/$(id -u)/com.example.photo-backup`.
   The old pyenv editable install (`.pyenv/versions/3.13.3/bin/photo-backup`) is
   left intact throughout, so this restores production instantly.
2. To undo everything: `git checkout master` (branch `uv-migration` holds all edits).

## Steps (check off as completed)

- [x] **1. Install uv.**  (done — `brew install uv`, v0.11.29) `brew install uv` (preferred) or
      `curl -LsSf https://astral.sh/uv/install.sh | sh`. Verify `uv --version`.
- [x] **2. Rewrite `photo-backup/pyproject.toml`.**  (done — added `[build-system]`
      setuptools, `[project]` with `dynamic=["version"]`, `[project.scripts]`,
      `[dependency-groups] dev`, `[tool.setuptools.dynamic]` +
      `[tool.setuptools.packages.find]`; ruff/mypy sections untouched.)
- [x] **3. Delete** `setup.py`, `requirements.txt`, `requirements-dev.txt`.
      (done via `git rm`.)
- [x] **4. `uv lock` then `uv sync`.**  (done — 47 pkgs, `.venv` rebuilt on 3.13.3
      over a stale 3.9.11 venv; `uv.lock` created. Verified `uv run photo-backup
      --version` → v0.1.0 and a 14-test pure-unit subset passes. NOTE: the FULL
      `pytest tests/unit` hangs because the suite's conftest spins up Docker/Minio
      containers — pre-existing, NOT caused by uv.)
- [x] **5. Update `photo-backup/Makefile`.**  (done — install/install-dev →
      `uv sync`; lint/format/test targets → `uv run`.)
- [x] **6. Docs.**  (done — `CLAUDE.md` Production Runtime + Development Commands,
      `README.md` install/venv/troubleshooting. `.gitignore` already covers
      `.venv`; `uv.lock` is tracked. pre-commit config unchanged.)
- [ ] **7. Repoint production service.**  ⚠️ BLOCKED — MUST BE RUN BY THE USER.
      The harness classifier blocks Claude from editing the LaunchAgent plist or
      running launchctl against the service. Plist already backed up to
      `com.example.photo-backup.plist.pre-uv.bak`. User runs (via `!` in session or
      a normal shell):
      ```
      /usr/libexec/PlistBuddy -c "Set :ProgramArguments:0 /Users/you/git/backup-to-s3/photo-backup/.venv/bin/photo-backup" ~/Library/LaunchAgents/com.example.photo-backup.plist
      launchctl kickstart -k gui/$(id -u)/com.example.photo-backup
      ./check-status.sh
      ```
      Verify service alive + last-sync/verify healthy, no crash-loop in
      `~/Library/Logs/photo-backup/service-error.log`.
- [ ] **8. Commit** on branch `uv-migration` (split logically). Update memory
      (`photo-backup-runtime.md`: new venv path + uv workflow). Then user reviews /
      merges. Delete this plan file (or keep as changelog) once merged & stable.

## Verification checklist before declaring done
- `uv run pytest tests/unit -q` passes.
- `.venv/bin/photo-backup status` works standalone (with WASABI env vars).
- After Step 7: `./check-status.sh` — service alive, rclone state sane, no
  respawn crash-loop in `~/Library/Logs/photo-backup/service-error.log`.
- `git status` clean except intended changes; `.venv/` and `uv.lock` handled
  (lock committed, `.venv` ignored).

## Notes / deviations (fill in as we go)
- **launchd reload gotcha (Step 7):** `launchctl kickstart -k` restarts the job
  but reuses launchd's *cached* job definition — it does NOT re-read the plist
  from disk. After editing `ProgramArguments`, the running process stayed on the
  old pyenv interpreter. Must fully reload the job:
  ```
  launchctl bootout gui/$(id -u)/com.example.photo-backup
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.photo-backup.plist
  ```
  Verify the `check-status.sh` "service process" line shows
  `.../photo-backup/.venv/bin/...` (not `.pyenv/...`). `kickstart -k` is fine for
  reloading *code* changes thereafter, just not plist changes.
