#!/usr/bin/env bash
# Start the local LLM server using the provider and model configured in .env.
#
# Usage:
#   ./scripts/start_llm_server.sh
#
# Reads LLM_PROVIDER and LLM_MODEL from .env (same file the dashboard uses).
# Uncomment a local LLM block in .env.example, copy it to .env, then run this.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env"

# Load .env
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Error: .env not found at $ENV_FILE"
  echo "Copy .env.example to .env and uncomment a local LLM block."
  exit 1
fi

if [[ -z "${LLM_MODEL:-}" ]]; then
  echo "Error: LLM_MODEL is not set in .env"
  echo "Uncomment a local LLM block in .env.example, copy it to .env, and try again."
  exit 1
fi

case "${LLM_PROVIDER:-}" in
  mlx)
    echo "Starting MLX LM server"
    echo "  model : $LLM_MODEL"
    echo "  port  : 8080"
    echo ""
    cd "$ROOT_DIR"
    uv run mlx_lm.server --model "$LLM_MODEL" --port 8080
    ;;
  ollama)
    echo "Pulling Ollama model: $LLM_MODEL"
    ollama pull "$LLM_MODEL"
    echo ""
    echo "Starting Ollama server (port 11434)..."
    ollama serve
    ;;
  *)
    echo "Error: LLM_PROVIDER is '${LLM_PROVIDER:-unset}' — expected 'mlx' or 'ollama'"
    echo ""
    echo "Uncomment a local LLM block in .env.example, copy it to .env, and try again."
    exit 1
    ;;
esac
