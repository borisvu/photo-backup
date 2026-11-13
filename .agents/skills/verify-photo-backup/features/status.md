# Status (CLI)

Covers: ["photo_backup/cli/status_commands.py", "photo_backup/backup/state.py", "photo_backup/backup/engine.py", "photo_backup/credentials/**", "photo_backup/config/**", "photo_backup/state_utils.py", "photo_backup/main.py"]

`photo-backup status` summarizes configuration, credential validity (a live `rclone lsd`), rclone
version and the persisted backup history from `backup_state.json`. `--json` emits the same as a
JSON document on stdout; log lines go to stderr.

## Sub-features

- `json` `status --json`: `mode`, `backup_info` (endpoint, credential validation), `backup_state` (totals, success rate, last sync).
- `human` `status` / `status -v`: text summary (not asserted field-by-field yet).
- `history` totals match `backup_state.json` (`total_syncs`, `successful_syncs`, `total_files_transferred`).

## How to get to it (user POV)

- `photo-backup [--test-mode] status [--verbose|-v] [--json]`.

## Driving it with verify-photo-backup scripts

Required flags: none.

Preconditions: doctor OK; at least one daemon or CLI sync done.

- **JSON.** `bash scripts/cli.sh status --json 2>/dev/null | tail -n +2` → parseable JSON; observed `"mode": "test"`, `backup_info.endpoint` `localhost:59000`, `credential_status.validation` `{"is_valid": true, "message": "Credentials validated successfully with rclone"}`, `backup_state.total_syncs` 3, `successful_syncs` 3, `total_files_transferred` 4, `total_bytes_transferred` 419840 (run 20261113-190938 after its drives).
- **Second view.** `bash scripts/state.sh backup_state '(s["total_syncs"], s["successful_syncs"], s["total_files_transferred"])'` → the same three numbers.

## Gotchas

- `credential_info.credential_source` says `config_file` even though the keys came from `PHOTO_BACKUP_STORAGE_*` env overrides (they merge into the config dict). Not a harness problem.
- Run from a normal shell outside this skill, status reads the caller's own environment, not the daemon's (see CLAUDE.md on launchd credentials).
- `cli.sh` prints `EXIT n` first; strip it (`tail -n +2`) before parsing.
