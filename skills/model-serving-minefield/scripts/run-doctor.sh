#!/usr/bin/env sh
set -eu
if [ "$#" -lt 1 ]; then
  echo "usage: run-doctor.sh --base-url http://HOST:PORT/v1 [doctor options]" >&2
  exit 2
fi
exec minefield quick "$@"
