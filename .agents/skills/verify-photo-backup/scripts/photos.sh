#!/usr/bin/env bash
# The input surface: the watched source directory ($RUN_DIR/photos). Every change is recorded with
# size + md5 so the remote copy can be compared byte-for-byte later.
# Usage:
#   bash scripts/photos.sh add <rel/path.jpg> [KB]     random content (default 64 KB); refuses to overwrite
#   bash scripts/photos.sh modify <rel/path.jpg> [KB]  rewrite with new random content (size changes if KB differs)
#   bash scripts/photos.sh rm <rel/path.jpg>
#   bash scripts/photos.sh ls                          path, size, md5 for every file
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_run
SRC="$RUN_DIR/photos"
op="${1:?add|modify|rm|ls}"; rel="${2:-}"
[[ "$op" == ls || -n "$rel" ]] || die "usage: photos.sh $op <rel/path>"
[[ "$rel" != /* && "$rel" != *..* ]] || die "path must be relative inside the source dir"
f="$SRC/$rel"; kb="${3:-64}"
out="$(evidence_path photos "$op $rel")"
describe() { printf '%s %s %s\n' "$1" "$(stat -f %z "$SRC/$1")" "$(md5 -q "$SRC/$1")"; }
case "$op" in
  add)    [[ ! -e "$f" ]] || die "$rel exists; use modify"
          mkdir -p "$(dirname "$f")"; head -c $((kb * 1024)) /dev/urandom > "$f"; line="$(describe "$rel")" ;;
  modify) [[ -f "$f" ]] || die "$rel does not exist"
          sleep 1   # monitor compares mtime at 1 s granularity on some filesystems
          head -c $((kb * 1024)) /dev/urandom > "$f"; line="$(describe "$rel")" ;;
  rm)     [[ -f "$f" ]] || die "$rel does not exist"; rm "$f"; line="$rel deleted" ;;
  ls)     line="$(cd "$SRC" && find . -type f | sed 's|^\./||' | sort | while read -r p; do describe "$p"; done)" ;;
  *)      die "unknown op $op" ;;
esac
{ echo "> photos $op $rel ${3:-}"; printf '%s\n' "$line"; } > "$out"
log "photos $op $rel ($(basename "$out"))"
printf '%s\n' "$line"
