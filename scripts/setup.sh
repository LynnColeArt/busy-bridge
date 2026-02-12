#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${VENV:-.venv}"

python3 -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"

python -m pip install -q -U pip
python -m pip install -q -e .

# For SquidKeys (squid store) interop/import.
python -m pip install -q duckdb cryptography

if [ -d "../key-store" ]; then
  # Install local SquidKeys distribution (project name is squidkeys).
  python -m pip install -q -e ../key-store
fi

if [ "${1:-}" = "--init-squidstore" ]; then
  if [ -z "${KEY_STORE_KEKS_JSON:-}" ] && [ -z "${KEY_STORE_MASTER_KEY:-}" ]; then
    OUT_DIR="${HOME}/.config/squidkeys"
    OUT_FILE="${OUT_DIR}/env"
    mkdir -p "$OUT_DIR"
    python - <<'PY' >"$OUT_FILE"
import os, json
from base64 import urlsafe_b64encode

key = urlsafe_b64encode(os.urandom(32)).decode("ascii")
print(f'export KEY_STORE_MASTER_KEY=\"{key}\"')
PY
    chmod 600 "$OUT_FILE"
    echo "Wrote SquidKeys env file: $OUT_FILE"
    echo "Load it in your shell before using --to-squidstore:"
    echo "  source \"$OUT_FILE\""
  else
    echo "Squid store keys already configured via KEY_STORE_KEKS_JSON or KEY_STORE_MASTER_KEY."
  fi
fi

echo "Setup complete."

