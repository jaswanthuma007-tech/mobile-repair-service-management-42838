#!/usr/bin/env bash
set -euo pipefail

# Best-effort load of local .env (some runners don't auto-inject it)
if [[ -f ".env" ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^[[:space:]]*#' .env | grep -v '^[[:space:]]*$' | xargs -d '\n' || true)
fi

HOST="${HOST:-${UVICORN_HOST:-0.0.0.0}}"
PORT="${PORT:-3001}"

# Fail fast if dependencies are missing/broken (common in CI containers).
python -m pip check >/dev/null 2>&1 || {
  echo "Python dependencies are missing or incompatible. Run: pip install -r requirements.txt" >&2
  python -m pip check >&2 || true
  exit 1
}

# Use module path so src/__main__.py and src/api/main.py remain the canonical entrypoints.
exec python -m uvicorn src.api.main:app --host "$HOST" --port "$PORT" --log-level info
