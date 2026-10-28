#!/usr/bin/env bash
# Live hackathon demo: NVIDIA Nemotron (via the local OmniRoute gateway) +
# Meterless H-MEM. The gateway key is loaded at runtime from the local Hermes
# profile config and is NEVER echoed or committed.
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

echo "OMNIROUTE_API_KEY loaded (length ${#OMNIROUTE_API_KEY} chars, value hidden)"
python3 demo_hackathon.py "$@"
