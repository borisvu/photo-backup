#!/usr/bin/env bash
# Cleanup: stop our daemon, snapshot + remove our fixed state dir, remove our containers + volume.
# Evidence stays. Idempotent; safe after a half-failed up.sh. Usage: bash scripts/down.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
RUN_DIR=""
if [[ -L "$CURRENT" ]]; then
  RUN_DIR="$(cd -P "$CURRENT" 2>/dev/null && pwd || true)"
  [[ -f "$RUN_DIR/state.env" ]] && source "$RUN_DIR/state.env"
fi
pid="${APP_PID:-$([[ -n "$RUN_DIR" && -f "$RUN_DIR/app.pid" ]] && cat "$RUN_DIR/app.pid" || true)}"

if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
  if has "$APP_CMD_MATCH" ps -o command= -p "$pid"; then   # kill what we started, never by name
    kill -TERM "$pid"; for _ in $(seq 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    kill -0 "$pid" 2>/dev/null && { pkill -KILL -P "$pid" 2>/dev/null || true; kill -KILL "$pid"; }
    log "stopped daemon pid $pid"
  else
    log "pid $pid is not our daemon; left alone"
  fi
fi

# Fixed dir: snapshot into evidence, remove only when our marker says so.
if [[ -e "$FIXED_DIR" ]]; then
  if [[ -n "$RUN_DIR" && -n "${RUN_ID:-}" && "$(cat "$OWNER_MARK" 2>/dev/null)" == "$RUN_ID" ]]; then
    rm -rf "$RUN_DIR/app-state"; cp -R "$FIXED_DIR" "$RUN_DIR/app-state" 2>/dev/null || true
    rm -rf "$FIXED_DIR"; log "snapshotted and removed $FIXED_DIR"
  else
    log "WARN $FIXED_DIR is not marked as this run's; left alone"
  fi
fi

"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
[[ -z "$(our_containers)" ]] && log "containers and volumes removed" || die "$PROJECT containers survived"

busy=""
for port in "${FIXED_PORTS[@]}"; do
  for _ in $(seq 10); do [[ -z "$(port_pid "$port")" ]] && break; sleep 0.5; done
  [[ -z "$(port_pid "$port")" ]] || busy+=" $port"
done
[[ -z "$busy" ]] || log "WARN ports still busy:$busy (not ours?)"

if [[ -n "$RUN_DIR" && -d "$RUN_DIR" ]]; then
  printf 'ENDED_AT=%q\n' "$(date -u +%FT%TZ)" >> "$RUN_DIR/state.env"
  rm -f "$CURRENT"
  log "evidence kept at $RUN_DIR"; echo "$RUN_DIR"
fi
