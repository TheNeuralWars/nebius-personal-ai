#!/usr/bin/env bash
# Run the Hermes Personal AI demo on REAL Nebius Token Factory inference.
# Loads the API key from the secure file at runtime — the key is NEVER echoed.
set -euo pipefail
cd "$(dirname "$0")"

KEY_FILE="${NEBIUS_KEY_FILE:-/data/secrets/nebius_api_key}"
if [[ ! -f "$KEY_FILE" ]]; then
  echo "ERROR: key file not found: $KEY_FILE" >&2
  exit 1
fi
# Load key into env at runtime only. Never printed.
export NEBIUS_API_KEY="$(cat "$KEY_FILE")"
export HERMES_LLM_PROVIDER=nebius
# Optional model override (default: NousResearch/Hermes-4-405B):
# export NEBIUS_MODEL="moonshotai/Kimi-K3"

echo "NEBIUS_API_KEY loaded (length ${#NEBIUS_API_KEY} chars, value hidden)"
python3 demo_live.py "$@"
