#!/bin/bash
set -eu
cd -- "$(dirname -- "$0")"
exec /usr/bin/python3 -u scripts/start.py "$@"
