#!/usr/bin/env bash
# Live Zetaris demo: federated SQL tool + Nemotron planner + H-MEM memory join.
# The gateway key is loaded at runtime from the local Hermes profile config and
# is NEVER echoed or committed. Zetaris credentials come from the environment
# (ZETARIS_PASSWORD_FILE or ZETARIS_PASSWORD) and are never printed.
set -euo pipefail
cd "$(dirname "$0")"

export OMNIROUTE_BASE_URL="${OMNIROUTE_BASE_URL:-http://127.0.0.1:20128/v1}"
if [[ -z "${OMNIROUTE_API_KEY:-}" ]]; then
  export OMNIROUTE_API_KEY="$(python3 - <<'PY'
import os, yaml
path = os.path.expanduser("~/.hermes/profiles/hermes-ceo/config.yaml")
print(yaml.safe_load(open(path))["providers"]["omniroute"]["api_key"])
PY
)"
fi
export HERMES_LLM_PROVIDER="${HERMES_LLM_PROVIDER:-nemotron}"
export ZETARIS_UI_URL="${ZETARIS_UI_URL:-http://127.0.0.1:3300}"
export ZETARIS_USER="${ZETARIS_USER:-admin@zetaris.com}"
if [[ -z "${ZETARIS_PASSWORD:-}" && -z "${ZETARIS_PASSWORD_FILE:-}" ]]; then
  export ZETARIS_PASSWORD_FILE="${ZETARIS_PASSWORD_FILE:-/data/secrets/zetaris_admin_password}"
fi

echo "OMNIROUTE_API_KEY loaded (length ${#OMNIROUTE_API_KEY} chars, value hidden)"
echo "Zetaris credentials: loaded from ${ZETARIS_PASSWORD_FILE:-env} (value hidden)"
python3 demo_zetaris.py "$@"
