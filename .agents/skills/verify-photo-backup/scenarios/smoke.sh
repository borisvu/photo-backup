#!/usr/bin/env bash
# Smoke: the daemon journey. Photos dropped into the watched source dir -> the daemon detects them
# -> rclone sync -> objects in the bucket with identical bytes, hidden files excluded -> persisted
# backup_state updated -> a local delete propagates while a control survives -> CLI verify passes.
# Unique ids per run, so it is re-runnable on one stack. Exit 0 = every check PASS.
# Usage: bash scenarios/smoke.sh  (needs scripts/up.sh first; ~45 s with the default 18 s check interval)
S="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
source "$S/lib.sh"
require_run
set +e
fails=0
check() { if eval "$2"; then echo "PASS  $1"; else echo "FAIL  $1"; fails=$((fails + 1)); fi; }
md5_src() { md5 -q "$RUN_DIR/photos/$1"; }
s3ls() { bash "$S/s3.sh" ls 2>/dev/null; }
synced_files() { bash "$S/state.sh" backup_state 's["total_files_transferred"]' 2>/dev/null || echo 0; }
n="smoke-$(date +%s)"
A="$n/album/a.jpg"; B="$n-b.jpg"; H=".$n-hidden.jpg"

# 1. Input: two photos (one nested) + one hidden file, after a log barrier.
before="$(synced_files)"; [[ "$before" =~ ^[0-9]+$ ]] || before=0
N="$(bash "$S/applog.sh" mark)"
bash "$S/photos.sh" add "$A" 200 >/dev/null 2>&1
bash "$S/photos.sh" add "$B" 30 >/dev/null 2>&1
bash "$S/photos.sh" add "$H" 4 >/dev/null 2>&1
# 2. The daemon reacts (async: wait on its log after the barrier, never sleep).
check "daemon detected + synced (log after barrier)" 'bash "$S/applog.sh" wait "Backup completed successfully" --after "$N" --timeout 90 >/dev/null 2>&1'
check "no failed backup after barrier" '[[ -z "$(bash "$S/applog.sh" since "$N" "Backup failed|Error triggering backup")" ]]'
# 3. Output: second view through MinIO's own client; key, size and bytes bound together.
listing="$(s3ls)"
populated=0; [[ "$listing" == *"204800 $A"* && "$listing" == *"30720 $B"* ]] && populated=1
check "a.jpg in bucket with source size" '[[ "$listing" == *"204800 $A"* ]]'
check "b.jpg in bucket with source size" '[[ "$listing" == *"30720 $B"* ]]'
check "a.jpg bytes identical (md5)" '[[ "$(bash "$S/s3.sh" md5 "$A" 2>/dev/null)" == "$(md5_src "$A")" ]]'
check "hidden file excluded" '[[ "$listing" != *"$H"* ]]'
# 4. Persisted state reflects this sync.
check "backup_state: +2 files transferred" '[[ "$(synced_files)" == "$((before + 2))" ]]'
check "backup_state: last sync succeeded on our source" '[[ "$(bash "$S/state.sh" backup_state "(s[\"last_stats\"][\"success\"], s[\"last_stats\"][\"source_path\"])" 2>/dev/null)" == "(True, '"'"'$RUN_DIR/photos'"'"')" ]]'
# 5. Deletion: populated target (a) + surviving control (b), completion barrier before the absence check.
N="$(bash "$S/applog.sh" mark)"
bash "$S/photos.sh" rm "$A" >/dev/null 2>&1
check "daemon synced the delete" 'bash "$S/applog.sh" wait "Backup completed successfully" --after "$N" --timeout 90 >/dev/null 2>&1'
listing="$(s3ls)"
check "deleted photo gone from bucket (target was populated first)" '(( populated == 1 )) && [[ "$listing" != *" $A"* ]]'
check "control photo survived" '[[ "$listing" == *"30720 $B"* ]]'
# 6. Caller-facing verification agrees.
check "cli verify -> VERIFICATION PASSED, exit 0" 'has "VERIFICATION PASSED" bash "$S/cli.sh" verify 2>/dev/null'

(( fails == 0 )) && { echo "smoke: PASS $n (evidence $RUN_DIR/evidence)"; exit 0; } || { echo "smoke: $fails FAIL $n (evidence $RUN_DIR/evidence)"; exit 1; }
