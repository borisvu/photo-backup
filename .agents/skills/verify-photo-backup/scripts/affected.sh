#!/usr/bin/env bash
# Deliberately independent of lib.sh: no service, Docker or cloud environment.
set -euo pipefail
exec python3 "$(dirname "$0")/affected.py" "$@"
