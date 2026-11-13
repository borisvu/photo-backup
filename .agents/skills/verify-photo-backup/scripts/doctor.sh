#!/usr/bin/env bash
# Doctor (read-only): is the daemon we are about to drive ours, current, local and healthy?
# Exit 0 = no FAIL. Usage: bash scripts/doctor.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
fails=0
pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; fails=$((fails + 1)); }

[[ -L "$CURRENT" && -f "$CURRENT/state.env" ]] || { fail "no active run (scripts/up.sh)"; exit 1; }
RUN_DIR="$(cd -P "$CURRENT" && pwd)"; source "$RUN_DIR/state.env"
pass "flags: none (photo-backup has no feature flags)"
pass "target: $TARGET_PATH @ $TARGET_SHA"
pass "active run $RUN_ID (launched at $GIT_SHA on $GIT_BRANCH, $GIT_DIRTY dirty files)"
pass "check interval ${CHECK_INTERVAL_HOURS}h, $RCLONE_VERSION"

[[ -n "${APP_PID:-}" ]] && kill -0 "$APP_PID" 2>/dev/null && pass "daemon pid $APP_PID alive" || fail "daemon not running (pid ${APP_PID:-none})"
has "$APP_CMD_MATCH" ps -o command= -p "${APP_PID:-0}" && pass "pid $APP_PID runs $APP_BIN from this target" || fail "pid ${APP_PID:-none} is not '$APP_CMD_MATCH'"
owner="$(port_pid "$VERIFY_MINIO_PORT")"
[[ -n "$owner" ]] && pass ":$VERIFY_MINIO_PORT listening (MinIO via docker)" || fail ":$VERIFY_MINIO_PORT not listening"

for svc in $("${COMPOSE[@]}" config --services); do
  st="$("${COMPOSE[@]}" ps --format '{{.Health}}' "$svc" 2>/dev/null || true)"
  [[ "$st" == healthy ]] && pass "$svc healthy" || fail "$svc: '${st:-missing}'"
done

svc_ready && pass "every way in is live (daemon loop + boot verification done + MinIO + bucket)" || fail "svc_ready false"
[[ "$(git -C "$REPO_ROOT" rev-parse --short HEAD)" == "${SCHEMA_VERSION:-}" ]] && pass "target sha unchanged ($SCHEMA_VERSION)" || fail "HEAD moved since launch (was ${SCHEMA_VERSION:-?})"

# Outbound inspection: daemon + children (rclone) may only talk to loopback. A failed inspection is a FAIL.
pids="$(printf '%s,' "${APP_PID:-0}" $(pgrep -P "${APP_PID:-0}" 2>/dev/null || true))"
if connections="$(lsof -nP -a -p "${pids%,}" -iTCP -sTCP:ESTABLISHED 2>"$RUN_DIR/inspection.err" || [[ ! -s "$RUN_DIR/inspection.err" ]])"; then
  remote="$(printf '%s\n' "$connections" | awk 'NR>1{print $9}' | grep -vE -- '->(127\.0\.0\.1|\[::1\]):' || true)"
  [[ -z "$remote" ]] && pass "no non-loopback TCP from daemon/children (poller: usually idle)" || fail "non-loopback TCP: $remote"
else
  fail "UNKNOWN connection inspection failed (see inspection.err)"
fi
svc_doctor_extra

# Editable install: the daemon holds the code it imported at start. Any newer source = stale daemon.
stale="$(find "${APP_SRC_DIRS[@]}" -type f -name '*.py' -newer "$RUN_DIR/app.started" 2>/dev/null | head -1 || true)"
[[ -z "$stale" ]] && pass "daemon started after last source change" || fail "sources changed since daemon start ($stale). You would verify stale code: down.sh && up.sh"

(( fails == 0 )) && { echo "doctor: OK"; exit 0; } || { echo "doctor: $fails failure(s)"; exit 1; }
