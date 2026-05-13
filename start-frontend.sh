#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR/frontend"

HOST="${SREZERO_FRONTEND_HOST:-127.0.0.1}"
PORT="${SREZERO_FRONTEND_PORT:-3000}"

if [ ! -d node_modules ]; then
  npm install
fi

npm run dev -- --hostname "$HOST" --port "$PORT"
