#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export BASEERA_LLM_PROVIDER="${BASEERA_LLM_PROVIDER:-ollama}"
export BASEERA_LLM_BASE_URL="${BASEERA_LLM_BASE_URL:-http://127.0.0.1:11434}"
export BASEERA_LLM_MODEL="${BASEERA_LLM_MODEL:-qwen3.5:9b}"
export BASEERA_ALLOWED_ORIGINS="${BASEERA_ALLOWED_ORIGINS:-http://localhost:3100,http://127.0.0.1:3100}"
exec uv run --extra advanced uvicorn baseera.main:app --reload --reload-dir services/api/baseera --app-dir services/api --host 127.0.0.1 --port 8100
