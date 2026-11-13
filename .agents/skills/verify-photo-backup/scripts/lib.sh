# Shared config, hooks and guards for verify-photo-backup. Sourced, never executed.
set -euo pipefail

SKILL_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_REPO="$(git -C "$SKILL_DIR" rev-parse --show-toplevel)"
export VERIFY_REPO="$(git -C "${VERIFY_REPO:-$SKILL_REPO}" rev-parse --show-toplevel)"
REPO_ROOT="$VERIFY_REPO"
export VERIFY_FLAGS="${VERIFY_FLAGS:-}"

# ---------- Service facts ----------
SVC="photo-backup"
PROJECT="verify-$SVC"                         # compose project; the repo's tests use named containers instead
APP_DIR="$REPO_ROOT"                          # uv project at the repo root (pyproject.toml + uv.lock)
APP_SRC_DIRS=("$APP_DIR/photo_backup" "$APP_DIR/pyproject.toml" "$APP_DIR/uv.lock")
VENV="$APP_DIR/.venv"                         # per-target venv, editable install of THIS target's source
APP_BIN="$VENV/bin/photo-backup"
APP_CMD_MATCH="$APP_BIN --test-mode start --foreground"   # down.sh kills only a pid whose command line has this
# Hard-coded in photo_backup/consts.py (TEST_MODE_BASE_DIR) and state_utils.get_state_directories():
# test-mode state, PID file and monitor state ALWAYS live here, whatever state.directory says.
# Production mode would write to ~/Library/Application Support/photo-backup instead, which is why
# every invocation forces --test-mode AND a fake HOME. Fixed path => one run at a time, and never
# concurrently with `make test-functional` (those tests rmtree this directory).
FIXED_DIR="/tmp/photo-backup-test"
OWNER_MARK="$FIXED_DIR/.verify-owner"
PID_FILE="$FIXED_DIR/temp/photo-backup.pid"   # consts.SERVICE_PID_FILENAME under dirs["temp"]
APP_STATE_DIR="$FIXED_DIR/state"              # backup_state.json, monitor_state.json, verification_schedule.json
export VERIFY_MINIO_PORT="${VERIFY_MINIO_PORT:-59000}"   # movable: reaches the app via PHOTO_BACKUP_STORAGE_ENDPOINT
FIXED_PORTS=("$VERIFY_MINIO_PORT")
BUCKET="my-photo-backup-bucket-test"          # TEST_MODE_DEFAULTS backup.destination = minio-test:<this>
# Seconds-scale change detection. Test-mode default is 0.1h (6 min). Env overrides skip the
# file validator's 0.1 minimum, which is exactly how the repo's tests shorten timers.
export VERIFY_CHECK_INTERVAL_HOURS="${VERIFY_CHECK_INTERVAL_HOURS:-0.005}"   # 18 s
COMPOSE=(docker compose -p "$PROJECT" -f "$SKILL_DIR/compose.yml")
MINIO_SERVICE="minio"

RUNS_DIR="$SKILL_REPO/.verify/$SVC"
CURRENT="$RUNS_DIR/current"
if [[ -L "$CURRENT" && -f "$CURRENT/state.env" ]]; then
  target="$(bash -c 'source "$1"; printf "%s" "$TARGET_PATH"' _ "$CURRENT/state.env")"
  [[ "$VERIFY_REPO" == "$target" ]] || { echo "active run targets $target; set VERIFY_REPO to that path" >&2; exit 1; }
fi

# The ONLY environment the app ever sees. env -i drops WASABI_*/S3_* keys (the direct credential
# provider prefers them over config) and any PHOTO_BACKUP_* the shell carries. Fake HOME hides
# ~/.config/photo-backup/config.yaml (it would override test defaults, incl. the destination),
# ~/.photo-backup (verify cache/report fallback) and the production state dir.
app_env() {
  local rclone_dir; rclone_dir="$(dirname "$(command -v rclone)")"
  printf '%s\n' \
    "PATH=$VENV/bin:$rclone_dir:/usr/bin:/bin:/usr/sbin:/sbin" \
    "HOME=$RUN_DIR/home" "TMPDIR=$RUN_DIR/tmp" "LANG=en_US.UTF-8" "PYTHONUTF8=1" "PYTHONIOENCODING=utf-8" \
    "PHOTO_BACKUP_TEST_MODE=1" \
    "PHOTO_BACKUP_BACKUP_SOURCE_PATH=$RUN_DIR/photos" \
    "PHOTO_BACKUP_STORAGE_ENDPOINT=localhost:$VERIFY_MINIO_PORT" \
    "PHOTO_BACKUP_STORAGE_ACCESS_KEY=minioadmin" \
    "PHOTO_BACKUP_STORAGE_SECRET_KEY=minioadmin" \
    "PHOTO_BACKUP_STORAGE_USE_SSL=true" \
    "RCLONE_CA_CERT=$RUN_DIR/certs/public.crt" \
    "PHOTO_BACKUP_STORAGE_BUCKET=$BUCKET" \
    "PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS=$VERIFY_CHECK_INTERVAL_HOURS"
}
# Run a command in the app environment, cwd = run dir (never $APP_DIR: cwd/config.yaml is a config source).
app_exec() {
  local envs=(); while IFS= read -r e; do envs+=("$e"); done < <(app_env)
  (cd "$RUN_DIR" && env -i "${envs[@]}" "$@")
}

# ---------- Hooks ----------

# Venv per target. Offline frozen install from the uv cache; refuse with the exact command otherwise.
svc_deps() {
  command -v uv >/dev/null || die "uv not installed (repo manages deps with uv)"
  command -v rclone >/dev/null || die "rclone not installed (the app shells out to it): brew install rclone"
  if [[ ! -x "$APP_BIN" ]]; then
    # uv's own discovery can hit version-manager shims (mise/pyenv recursion seen on the author's Mac).
    # Pick a real interpreter matching .python-version; VERIFY_PYTHON overrides.
    # .python-version pins a patch (3.13.3); pyproject only needs >=3.13, so match major.minor.
    local want py; want="$(cut -d. -f1,2 "$APP_DIR/.python-version")"
    py="${VERIFY_PYTHON:-$(uv python list --only-installed 2>/dev/null | awk -v w="cpython-$want." 'index($1,w)==1 && $2 !~ /\/shims\// {print $2; exit}')}"
    [[ -n "$py" ]] || die "no non-shim Python $want found; install one (uv python install $want) or set VERIFY_PYTHON"
    log "no venv at $VENV; uv sync --frozen --offline --python $py"
    (cd "$APP_DIR" && env -u VIRTUAL_ENV uv sync --frozen --offline --python "$py") >> "$RUN_DIR/deps.log" 2>&1 \
      || die "dependencies missing; run: cd '$APP_DIR' && uv sync --frozen --python $py"
  fi
  # Editable install must resolve to THIS target's source, or a worktree run would test the home repo.
  local where; where="$("$VENV/bin/python" -c 'import photo_backup; print(photo_backup.__file__)' 2>>"$RUN_DIR/deps.log")" \
    || die "venv cannot import photo_backup; run: cd '$APP_DIR' && uv sync --frozen"
  [[ "$where" == "$APP_DIR/photo_backup/"* ]] || die "venv imports $where, not $APP_DIR; run: cd '$APP_DIR' && uv sync --frozen"
  echo "$where" > "$RUN_DIR/import-path.txt"
}

# This service has no feature-flag provider. Anything in VERIFY_FLAGS is a mistake.
svc_flags() {
  [[ -z "$VERIFY_FLAGS" ]] || die "photo-backup has no feature flags; unset VERIFY_FLAGS (got '$VERIFY_FLAGS')"
  echo "no feature flags in this service"
}

# No database. The 'schema' is the app's own JSON state; record the target sha instead.
svc_migrate() { git -C "$REPO_ROOT" rev-parse --short HEAD; }

# Throwaway self-signed cert for the TLS stand-in (SANs cover virtual-host bucket names).
svc_certs() {
  mkdir -p "$RUN_DIR/certs"
  openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:$BUCKET.localhost,IP:127.0.0.1" \
    -keyout "$RUN_DIR/certs/private.key" -out "$RUN_DIR/certs/public.crt" >> "$RUN_DIR/certs.log" 2>&1 \
    || die "cert generation failed, see $RUN_DIR/certs.log"
  chmod 644 "$RUN_DIR/certs/private.key"   # read by the container user; throwaway, local only
  export VERIFY_CERTS_DIR="$RUN_DIR/certs"
}

# The bucket the tests create with `mc mb` (sync uses no_check_bucket = true, so it must pre-exist).
svc_provision() { mc_exec "mc mb --ignore-existing local/$BUCKET"; }

# Editable Python install: nothing to compile. Byte-compile to surface syntax errors before boot.
svc_build() {
  "$VENV/bin/python" -m compileall -q "$APP_DIR/photo_backup" >> "$RUN_DIR/build.log" 2>&1 \
    || die "photo_backup does not compile, see $RUN_DIR/build.log"
}

# The daemon: monitor loop -> rclone sync -> scheduled verification. Logs to app.log.
svc_start() {
  mkdir -p "$RUN_DIR/home" "$RUN_DIR/tmp" "$RUN_DIR/photos"
  local envs=(); while IFS= read -r e; do envs+=("$e"); done < <(app_env)
  (
    cd "$RUN_DIR"
    env -i "${envs[@]}" nohup "$APP_BIN" --test-mode start --foreground > "$RUN_DIR/app.log" 2>&1 &
    echo $! > "$RUN_DIR/app.pid"
  )
  date +%s > "$RUN_DIR/app.started"
}

# Ready = daemon alive, owns the PID file, entered its loop, AND finished its first iteration
# (boot-time scheduled verification is 'never run before' => always due; drives must not race it),
# AND MinIO answers with our bucket present.
svc_ready() {
  local pid; pid="$(cat "$RUN_DIR/app.pid" 2>/dev/null)" || return 1
  [[ "$(cat "$PID_FILE" 2>/dev/null)" == "$pid" ]] || return 1
  grep -q "Entering main service loop" "$RUN_DIR/app.log" || return 1
  grep -qE "Scheduled verification (PASSED|FAILED)|Error checking scheduled verification" "$RUN_DIR/app.log" || return 1
  curl -fsS --cacert "$RUN_DIR/certs/public.crt" "https://localhost:$VERIFY_MINIO_PORT/minio/health/ready" >/dev/null 2>&1 || return 1
  mc_exec "mc stat local/$BUCKET" >/dev/null 2>&1
}

# Extra doctor lines.
svc_doctor_extra() {
  [[ "$(cat "$OWNER_MARK" 2>/dev/null)" == "$RUN_ID" ]] && pass "$FIXED_DIR owned by this run" || fail "$FIXED_DIR not marked as ours"
  [[ "$(cat "$PID_FILE" 2>/dev/null)" == "${APP_PID:-x}" ]] && pass "service PID file = our pid" || fail "PID file $PID_FILE != $APP_PID"
  # Local mode from the app's own view of its effective config (a failed inspection is a FAIL).
  local cfg; if cfg="$(app_exec "$APP_BIN" --test-mode config 2>&1)"; then
    printf '%s\n' "$cfg" > "$RUN_DIR/doctor-config.txt"
    grep -q "localhost:$VERIFY_MINIO_PORT" <<<"$cfg" && pass "effective endpoint localhost:$VERIFY_MINIO_PORT" || fail "effective endpoint is not our MinIO (see doctor-config.txt)"
    grep -q "$RUN_DIR/photos" <<<"$cfg" && pass "effective source = run dir photos" || fail "effective source is not $RUN_DIR/photos"
    grep -qi "wasabisys" <<<"$cfg" && fail "config mentions wasabisys" || pass "no Wasabi endpoint in effective config"
  else
    fail "UNKNOWN: 'photo-backup --test-mode config' failed (see doctor-config.txt)"; printf '%s\n' "$cfg" > "$RUN_DIR/doctor-config.txt"
  fi
  local penv; if penv="$(ps eww -o command= -p "${APP_PID:-0}" 2>/dev/null)" && [[ -n "$penv" ]]; then
    [[ "$penv" == *"HOME=$RUN_DIR/home"* ]] && pass "daemon HOME is the run dir" || fail "daemon HOME is not $RUN_DIR/home"
    [[ "$penv" =~ (WASABI_|S3_)(ACCESS|SECRET) ]] && fail "daemon env carries WASABI_/S3_ keys" || pass "no WASABI_/S3_ keys in daemon env"
  else
    fail "UNKNOWN: cannot read daemon environment"
  fi
}

# ---------- Guards and helpers ----------

log() { printf '[%s] %s\n' "verify-$SVC" "$*" >&2; [[ -n "${RUN_DIR:-}" && -d "${RUN_DIR:-}" ]] && printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >> "$RUN_DIR/timeline.log" || true; }
die() { log "FAIL: $*"; exit 1; }
port_pid() { lsof -nP -t -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1 || true; }
our_containers() { docker ps -q --filter "label=com.docker.compose.project=$PROJECT" 2>/dev/null; }
state_set() { printf '%s=%q\n' "$1" "$2" >> "$RUN_DIR/state.env"; }

# Next numbered evidence file: evidence_path cli "sync" -> .../evidence/003-cli-sync.txt
evidence_path() {
  local kind="$1" what="${2:-}" n slug
  n=$(find "$RUN_DIR/evidence" -type f 2>/dev/null | wc -l | tr -d ' ')
  slug=$(printf '%s' "$what" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//' | cut -c1-60)
  printf '%s/evidence/%03d-%s%s.txt' "$RUN_DIR" "$((n + 1))" "$kind" "${slug:+-$slug}"
}

# Load the active run; refuse to drive anything this skill did not start.
require_run() {
  [[ -L "$CURRENT" && -f "$CURRENT/state.env" ]] || die "no active run. Start one: scripts/up.sh"
  RUN_DIR="$(cd -P "$CURRENT" && pwd)"
  # shellcheck disable=SC1091
  source "$RUN_DIR/state.env"
  [[ -n "${APP_PID:-}" ]] || die "run $RUN_ID has no app (launch failed?). See $RUN_DIR/app.log, then scripts/down.sh"
  kill -0 "$APP_PID" 2>/dev/null || die "daemon pid $APP_PID is gone. See $RUN_DIR/app.log; scripts/down.sh && scripts/up.sh"
  [[ "$(cat "$OWNER_MARK" 2>/dev/null)" == "$RUN_ID" ]] || die "$FIXED_DIR is not owned by run $RUN_ID. Refusing to drive foreign state."
  [[ "$(cat "$PID_FILE" 2>/dev/null)" == "$APP_PID" ]] || die "PID file does not name our daemon ($APP_PID). Refusing to drive a foreign process."
  [[ -n "$(our_containers)" ]] || die "no $PROJECT containers running. scripts/down.sh && scripts/up.sh"
}

# mc inside our MinIO container (alias 'local'; self-signed cert, so MC_INSECURE inside the container only).
mc_exec() { "${COMPOSE[@]}" exec -T -e MC_INSECURE=true "$MINIO_SERVICE" sh -c "mc alias set local https://localhost:9000 minioadmin minioadmin >/dev/null && $1"; }
# Helper interpreter: the target venv's Python (host python3 may be a broken version-manager shim).
PY="$VENV/bin/python"

# Capture fully before matching: avoids early-reader SIGPIPE under pipefail.
has() { local out; out="$("${@:2}")" || return; [[ "$out" == *"$1"* ]]; }
