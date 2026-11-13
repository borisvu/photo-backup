# Verify and repair (CLI)

Covers: ["photo_backup/cli/verify_commands.py", "photo_backup/verify/**", "photo_backup/credentials/**", "photo_backup/config/**", "photo_backup/main.py", "pyproject.toml", "uv.lock"]

`photo-backup verify` compares the local source with the bucket by **size + existence** (no hashing;
`rclone lsf --format sp`). It reports matched, size-mismatched, missing-on-remote and
missing-locally files and exits 1 when anything is off. `--repair` re-uploads mismatched and missing
files and re-checks them.

## Sub-features

- `pass` clean backup → `✅ VERIFICATION PASSED`, exit 0.
- `missing-remote` object deleted remotely → counted under `Missing on remote`, exit 1.
- `size-mismatch` object with a different size → `Mismatched files`, `Type: size`, exit 1.
- `repair` `--repair` uploads both, `✅ VERIFICATION PASSED (after repair)`, exit 0, remote bytes equal the source again.
- `hidden` dot-files are not scanned locally (2 local files reported while 3 exist).
- `report` `--save-report` / `--report-format` / `--report-path`: not driven (see README Not yet mapped).

## How to get to it (user POV)

- `photo-backup [--test-mode] [--dry-run] verify [--verbose|-v] [--repair|-r] [--save-report] [--report-format json|...] [--report-path PATH]`.
- With global `--dry-run`, `--repair` only prints what it would repair.

## Driving it with verify-photo-backup scripts

Required flags: none.

Preconditions: doctor OK; at least two photos backed up (add with `photos.sh`, wait for the daemon's
`Backup completed successfully`).

- **Clean.** `bash scripts/cli.sh verify -v` → `EXIT 0`, `Found 2 local files (70.0 KB)`, `Found 2 remote files`, `✅ Matched files: 2`, `✅ VERIFICATION PASSED`.
- **Damage (FIXTURE).** `bash scripts/s3.sh fixture-rm v-c.jpg`; `bash scripts/s3.sh fixture-put <b>.jpg 7`.
- **Detect.** `bash scripts/cli.sh verify -v` → `EXIT 1`, `Found 1 remote files`, `❌ Mismatched files: 1` (`Type: size`), `⚠️  Missing on remote: 1`, `❌ VERIFICATION FAILED`.
- **Repair.** `bash scripts/cli.sh verify --repair -v` → `EXIT 0`, `✅ Repaired: 2`, `❌ Failed: 0`, `✓  Verified: 2`, `✅ VERIFICATION PASSED (after repair)`.
- **Second view.** `bash scripts/s3.sh md5 <key>` for both keys equals `photos.sh ls` md5.

## Gotchas

- Verification is size-based by design (production lists ~200k objects; hashing was too slow). A same-size corruption passes verify; do not write a recipe that expects it to be caught.
- Inferred from source, not observed: the daemon only syncs when the source changed, so a damaged remote stays damaged until the next source change. Avoid source changes between damage and verify, or the daemon's sync may repair it first.
- `✅ Matched files` appears twice in output (log summary + click echo); match the click line or the exit code.
