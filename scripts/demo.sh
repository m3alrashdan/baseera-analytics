#!/usr/bin/env bash
set -Eeuo pipefail

build=1
seed=1
for argument in "$@"; do
  case "$argument" in
    --no-build) build=0 ;;
    --no-seed) seed=0 ;;
    --help)
      printf 'Usage: %s [--no-build] [--no-seed]\n' "$0"
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$argument" >&2
      exit 64
      ;;
  esac
done

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_directory/.." && pwd)"
cd -- "$repository_root"

docker compose config --quiet

up_arguments=(up -d)
if [[ "$build" -eq 1 ]]; then
  up_arguments+=(--build)
fi
docker compose "${up_arguments[@]}"

printf 'Waiting for measured API readiness...\n'
deadline=$((SECONDS + 120))
until curl --fail --silent --show-error \
  http://localhost:8100/api/v1/health/ready >/dev/null; do
  if ((SECONDS >= deadline)); then
    printf 'API did not become ready in 120 seconds. Recent service logs follow.\n' >&2
    docker compose logs --since=5m api postgres redis >&2
    exit 1
  fi
  sleep 2
done

if [[ "$seed" -eq 1 ]]; then
  docker compose exec -T api python -m baseera.seed
fi

printf 'BASEERA is ready at http://localhost:3100/en/login and /ar/login\n'
printf 'This is the fictional local demo; consult capabilities.json before claiming a feature.\n'
