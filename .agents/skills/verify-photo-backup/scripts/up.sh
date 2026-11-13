#!/usr/bin/env bash
# Launch: own MinIO, bucket, venv for the target, byte-compile, start the daemon, readiness.
# Usage: bash scripts/up.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
[[ $# == 0 ]] || die "usage: up.sh"

# 1. One run at a time.
[[ -L "$CURRENT" && -f "$CURRENT/state.env" ]] && die "a run is already active ($(readlink "$CURRENT")). scripts/down.sh first."

# 2. Preflight.
docker info >/dev/null 2>&1 || die "docker daemon not reachable (OrbStack: orb start)"
[[ -z "$(our_containers)" ]] || die "leftover $PROJECT containers. scripts/down.sh first."
for port in "${FIXED_PORTS[@]}"; do
  pid="$(port_pid "$port")"
  [[ -z "$pid" ]] || die "port $port busy (pid $pid: $(ps -o comm= -p "$pid" 2>/dev/null)). Set VERIFY_MINIO_PORT or stop it yourself."
done
if [[ -e "$FIXED_DIR" ]]; then
  holder="$(lsof -t +D "$FIXED_DIR" 2>/dev/null | head -1 || true)"
  die "$FIXED_DIR exists (hard-coded test-mode state dir; ${holder:+in use by pid $holder, }not ours). It is usually a leftover of make test-functional. If no tests are running: rm -rf $FIXED_DIR"
fi

# 3. Run dir: evidence lives here and survives cleanup.
RUN_ID="$(date +%Y%m%d-%H%M%S)"; RUN_DIR="$RUNS_DIR/$RUN_ID"
mkdir -p "$RUN_DIR/evidence"; ln -sfn "$RUN_ID" "$CURRENT"
{
  printf 'TARGET_PATH=%q\n' "$REPO_ROOT"
  printf 'TARGET_SHA=%q\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
  printf 'VERIFY_FLAGS=%q\n' "$VERIFY_FLAGS"
  printf 'RUN_ID=%q\n' "$RUN_ID"
  printf 'STARTED_AT=%q\n' "$(date -u +%FT%TZ)"
  printf 'GIT_SHA=%q\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
  printf 'GIT_BRANCH=%q\n' "$(git -C "$REPO_ROOT" branch --show-current)"
  printf 'GIT_DIRTY=%q\n' "$(git -C "$REPO_ROOT" status --porcelain | wc -l | tr -d ' ')"
  printf 'MINIO_PORT=%q\n' "$VERIFY_MINIO_PORT"
  printf 'CHECK_INTERVAL_HOURS=%q\n' "$VERIFY_CHECK_INTERVAL_HOURS"
  printf 'RCLONE_VERSION=%q\n' "$(rclone version 2>/dev/null | head -1)"
} > "$RUN_DIR/state.env"
log "run $RUN_ID at $RUN_DIR (target $REPO_ROOT)"

# Claim the fixed dir before the app creates it, so down.sh can prove it is ours.
mkdir -p "$FIXED_DIR"; printf '%s' "$RUN_ID" > "$OWNER_MARK"
svc_deps
svc_flags >> "$RUN_DIR/flags.log" 2>&1 || die "flags rejected, see $RUN_DIR/flags.log"
state_set ACTIVE_FLAGS "none"

# 4. Infra (healthchecks gate --wait).
svc_certs
"${COMPOSE[@]}" up -d --wait >> "$RUN_DIR/compose.log" 2>&1 || die "compose up failed, see $RUN_DIR/compose.log"

# 5. 'Schema' (target sha) + bucket.
schema="$(svc_migrate)"; state_set SCHEMA_VERSION "$schema"
svc_provision >> "$RUN_DIR/provision.log" 2>&1 || die "bucket provisioning failed, see $RUN_DIR/provision.log"
log "bucket $BUCKET ready on :$VERIFY_MINIO_PORT"

# 6. Build from disk, start.
svc_build
svc_start; APP_PID="$(cat "$RUN_DIR/app.pid")"
state_set APP_STARTED_EPOCH "$(cat "$RUN_DIR/app.started")"
state_set BUILD_MTIME "$(cat "$RUN_DIR/app.started")"

# 7. Ready = daemon in its loop, first iteration (boot verification) done, MinIO + bucket live.
deadline=$((SECONDS + 120))
until svc_ready; do
  kill -0 "$APP_PID" 2>/dev/null || { tail -40 "$RUN_DIR/app.log" >&2; die "daemon exited during boot, see $RUN_DIR/app.log"; }
  (( SECONDS < deadline )) || { tail -40 "$RUN_DIR/app.log" >&2; die "not ready within 120s"; }
  sleep 1
done
state_set APP_PID "$APP_PID"; state_set READY_AT "$(date -u +%FT%TZ)"
log "READY: daemon pid $APP_PID, MinIO :$VERIFY_MINIO_PORT bucket $BUCKET, source $RUN_DIR/photos, evidence $RUN_DIR/evidence"
