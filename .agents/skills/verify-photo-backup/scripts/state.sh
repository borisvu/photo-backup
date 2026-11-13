#!/usr/bin/env bash
# Read-only view of the app's persisted JSON state (hard-coded test-mode dir).
# Usage: bash scripts/state.sh <backup_state|monitor_state|verification_schedule> [python-expr]
#   python-expr sees the parsed JSON as `s`, e.g. 's["total_files_backed_up"]'
#   With no expr, prints the whole document.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_run
name="${1:?backup_state|monitor_state|verification_schedule}"; expr="${2:-}"
f="$APP_STATE_DIR/$name.json"
out="$(evidence_path state "$name ${expr:0:30}")"
[[ -f "$f" ]] || { echo "> $f" > "$out"; echo "MISSING" >> "$out"; echo "MISSING $f"; exit 1; }
res="$("$PY" - "$f" "$expr" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
print(json.dumps(s, indent=2, default=str) if not sys.argv[2] else eval(sys.argv[2], {}, {"s": s}))
PY
)"
{ echo "> $f ${expr}"; printf '%s\n' "$res"; } > "$out"
log "state $name ${expr:0:40} ($(basename "$out"))"
printf '%s\n' "$res"
