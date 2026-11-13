#!/usr/bin/env bash
# Drive a one-shot CLI command the way a user does, in the daemon's exact environment, forced to
# --test-mode. Never call .venv/bin/photo-backup by hand: without this env it reads real HOME
# config and, without --test-mode, the production state dir.
# Usage: bash scripts/cli.sh [--dry-run] <subcommand> [args...]
#   e.g. cli.sh sync -v | cli.sh verify --repair -v | cli.sh status --json | cli.sh --dry-run sync
# Prints "EXIT <code>" then the command's stdout (click output; status --json stays parseable with
# `tail -n +2`). The app's log lines go to stderr and to the evidence file. Exits with the command's code.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_run
[[ $# -ge 1 ]] || die "usage: cli.sh [--dry-run] <subcommand> [args...]"
pre=(); [[ "$1" == "--dry-run" ]] && { pre=(--dry-run); shift; }
[[ "$1" != "start" && "$1" != "restart" && "$1" != "stop" ]] || die "'$1' acts on the daemon this run owns; use up.sh/down.sh (stop/restart are unmapped, see features/README.md)"
out="$(evidence_path cli "${pre[*]:-} $*")"
errf="$RUN_DIR/tmp/cli-stderr.$$"
set +e
res="$(app_exec "$APP_BIN" --test-mode "${pre[@]}" "$@" 2>"$errf")"; code=$?
set -e
{ echo "> photo-backup --test-mode ${pre[*]:+${pre[*]} }$*"; echo "< EXIT $code"; printf '%s\n' "$res"; echo "--- stderr (app log lines)"; cat "$errf"; } > "$out"
cat "$errf" >&2; rm -f "$errf"
log "cli ${pre[*]:+${pre[*]} }$* -> exit $code ($(basename "$out"))"
echo "EXIT $code"; printf '%s\n' "$res"
exit "$code"
