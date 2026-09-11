#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
for required_command in uv npm curl; do
  command -v "$required_command" >/dev/null || { printf 'Missing prerequisite: %s\n' "$required_command" >&2; exit 1; }
done
uv sync --extra dev --extra advanced --frozen
npm ci
# Seed is idempotent and never resets existing datasets or tenant records.
PYTHONPATH=services/api uv run --extra advanced python -m baseera.seed
if ! curl --fail --silent --max-time 3 "${BASEERA_LLM_BASE_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null; then
  printf 'Ollama is not reachable. Start ollama serve; deterministic analysis remains available.\n' >&2
fi
printf 'BASEERA: http://localhost:3100/ar/login\n'
exec npm run dev
