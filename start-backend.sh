#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR"

HOST="${SREZERO_BACKEND_HOST:-127.0.0.1}"
PORT="${SREZERO_BACKEND_PORT:-8000}"

python -m srezero.server --host "$HOST" --port "$PORT"
