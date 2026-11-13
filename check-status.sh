#!/usr/bin/env bash
#
# check-status.sh — quick health check for the photo-backup service.
#
# Answers "is it working right now?" at a glance:
#   - Is the launchd service process alive?
#   - Is rclone actively uploading this moment, or idle/indexing/verifying?
#   - A snapshot from `photo-backup status` (last sync, failures, drive, verdict).
#
# Usage:  ./check-status.sh
#
# Note: the "Credentials: Not Available" line from `photo-backup status` is a
# false alarm when run from a normal shell — the real keys live in the launchd
# service's environment, not your terminal. Ignore it unless the service itself
# is failing (see docs/KEY_ROTATION.md).

set -u

echo "────────────── photo-backup health ──────────────"

echo "── service process ──"
if pgrep -fl "photo-backup start" 2>/dev/null; then
    :
else
    echo "❌ service NOT running (start it: launchctl kickstart -k gui/\$(id -u)/com.example.photo-backup)"
fi

echo
echo "── uploading right now? ──"
RCLONE_PID="$(pgrep -f "rclone sync" 2>/dev/null | head -1)"
if [ -n "$RCLONE_PID" ]; then
    echo "✅ rclone is transferring (PID $RCLONE_PID):"
    ps -o command= -p "$RCLONE_PID" 2>/dev/null | grep -oE '\-\-transfers.*--checksum' | head -1
else
    echo "⏸  idle — no active transfer (indexing/verifying, or waiting for the next run)"
fi

echo
echo "── snapshot (photo-backup status) ──"
if command -v photo-backup >/dev/null 2>&1; then
    photo-backup status 2>/dev/null \
        | grep -E "Last Sync|Last Successful|Consecutive|Drive:|rclone:|^(⚠️|✅|❌).*System Status" \
        || echo "   (could not read status — is photo-backup installed?)"
else
    echo "   photo-backup CLI not on PATH"
fi

echo
echo "── recent activity (last 8 log lines) ──"
LOG="$HOME/Library/Logs/photo-backup/photo-backup.log"
if [ -f "$LOG" ]; then
    tail -n 8 "$LOG"
else
    echo "   no log file at $LOG yet"
fi

echo "──────────────────────────────────────────────────"
