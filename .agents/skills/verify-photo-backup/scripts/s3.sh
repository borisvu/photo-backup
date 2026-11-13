#!/usr/bin/env bash
# Second view: the bucket as MinIO's own client (mc, inside our container) sees it. Independent of
# the app's rclone path. Read-only unless a FIXTURE op is named explicitly.
# Usage:
#   bash scripts/s3.sh ls                    "<size> <key>" per object, sorted
#   bash scripts/s3.sh md5 <key>             md5 of the stored object bytes
#   bash scripts/s3.sh fixture-rm <key>      FIXTURE: delete an object (verify/repair setup)
#   bash scripts/s3.sh fixture-put <key> KB  FIXTURE: overwrite an object with random bytes of KB size
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_run
op="${1:?ls|md5|fixture-rm|fixture-put}"; key="${2:-}"
[[ "$op" == ls || -n "$key" ]] || die "usage: s3.sh $op <key>"
out="$(evidence_path s3 "$op $key")"
case "$op" in
  ls)          res="$(mc_exec "mc ls --recursive --json local/$BUCKET" | "$PY" -c 'import sys,json
rows=[json.loads(l) for l in sys.stdin if l.strip()]
print("\n".join(sorted("%s %s" % (r["size"], r["key"]) for r in rows if r.get("type")=="file")))')" ;;
  md5)         res="$(mc_exec "mc cat 'local/$BUCKET/$key' | md5sum" | awk '{print $1}')" ;;
  fixture-rm)  res="FIXTURE $(mc_exec "mc rm 'local/$BUCKET/$key'")" ;;
  fixture-put) kb="${3:?KB}"; res="FIXTURE $(mc_exec "head -c $((kb * 1024)) /dev/urandom > /tmp/fx && mc cp /tmp/fx 'local/$BUCKET/$key' && rm /tmp/fx")" ;;
  *)           die "unknown op $op" ;;
esac
{ echo "> s3 $op $key ${3:-}  bucket=$BUCKET"; printf '%s\n' "$res"; } > "$out"
log "s3 $op $key ($(basename "$out"))"
printf '%s\n' "$res"
