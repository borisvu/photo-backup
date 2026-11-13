#!/usr/bin/env bash
# The daemon's output surface: its log (app.log = console output of the daemon).
# The daemon is async; take a barrier BEFORE acting, then wait for a pattern AFTER the barrier.
# Usage:
#   N=$(bash scripts/applog.sh mark)                        current line count (the barrier)
#   bash scripts/applog.sh wait <ERE> --after N [--timeout S]  exit 0 when a line after N matches
#   bash scripts/applog.sh since N [ERE]                    lines after N (optionally filtered)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_run
L="$RUN_DIR/app.log"
op="${1:?mark|wait|since}"
case "$op" in
  mark) wc -l < "$L" | tr -d ' ' ;;
  since)
    n="${2:?N}"; pat="${3:-.}"
    tail -n +"$((n + 1))" "$L" | grep -E -- "$pat" || true ;;
  wait)
    pat="${2:?ERE}"; shift 2; after=""; timeout=60
    while [[ $# -gt 0 ]]; do case "$1" in --after) after="$2"; shift 2;; --timeout) timeout="$2"; shift 2;; *) die "unknown arg $1";; esac; done
    [[ -n "$after" ]] || die "wait needs --after N (take a barrier with 'mark' before acting)"
    out="$(evidence_path applog "wait $pat")"
    end=$((SECONDS + timeout))
    while :; do
      hit="$(tail -n +"$((after + 1))" "$L" | grep -E -m1 -- "$pat" || true)"
      if [[ -n "$hit" ]]; then
        { echo "> wait /$pat/ after line $after (timeout ${timeout}s)"; echo "< MATCH"; printf '%s\n' "$hit"; } > "$out"
        log "applog matched /$pat/ ($(basename "$out"))"; printf '%s\n' "$hit"; exit 0
      fi
      (( SECONDS < end )) || break
      kill -0 "$APP_PID" 2>/dev/null || { echo "daemon died" >&2; break; }
      sleep 1
    done
    { echo "> wait /$pat/ after line $after (timeout ${timeout}s)"; echo "< TIMEOUT"; tail -n +"$((after + 1))" "$L" | tail -30; } > "$out"
    log "applog TIMEOUT /$pat/ ($(basename "$out"))"; echo "TIMEOUT waiting for /$pat/" >&2; exit 1 ;;
  *) die "unknown op $op" ;;
esac
