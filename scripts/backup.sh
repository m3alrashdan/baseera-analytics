#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf 'Usage: %s /explicit/protected/backup-directory\n' "$0" >&2
  printf 'Creates a quiesced PostgreSQL + artifact backup bundle.\n' >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 64
fi

command -v docker >/dev/null 2>&1 || {
  printf 'backup failed: docker is not installed\n' >&2
  exit 69
}
command -v python >/dev/null 2>&1 || {
  printf 'backup failed: python is not installed\n' >&2
  exit 69
}

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_directory/.." && pwd)"
cd -- "$repository_root"
docker compose version >/dev/null
docker compose config --quiet

destination="$1"
mkdir -p -- "$destination"
destination="$(cd -- "$destination" && pwd)"
if [[ "$destination" == "/" || "$destination" == "$repository_root" ]]; then
  printf 'backup failed: choose a dedicated directory, not %s\n' "$destination" >&2
  exit 64
fi

timestamp="${BASEERA_BACKUP_TIMESTAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
if [[ ! "$timestamp" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
  printf 'backup failed: BASEERA_BACKUP_TIMESTAMP must use YYYYMMDDTHHMMSSZ\n' >&2
  exit 64
fi
bundle="$destination/baseera-$timestamp"
if [[ -e "$bundle" ]]; then
  printf 'backup failed: bundle already exists: %s\n' "$bundle" >&2
  exit 73
fi

umask 077
mkdir -- "$bundle"
printf 'Backup is incomplete. Do not restore this directory.\n' >"$bundle/INCOMPLETE"

database_name="${BASEERA_POSTGRES_DB:-baseera}"
database_user="${BASEERA_POSTGRES_USER:-baseera}"
for identifier in "$database_name" "$database_user"; do
  if [[ ! "$identifier" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    printf 'backup failed: database identifiers contain unsupported characters\n' >&2
    exit 64
  fi
done

running_services="$(docker compose ps --services --status running)"
was_running() {
  grep -Fxq -- "$1" <<<"$running_services"
}

restart_quiesced_services() {
  local services=()
  local service
  for service in api worker web; do
    if was_running "$service"; then
      services+=("$service")
    fi
  done
  if ((${#services[@]})); then
    docker compose up -d "${services[@]}" >/dev/null || true
  fi
}
trap restart_quiesced_services EXIT

if ! was_running postgres; then
  printf 'backup failed: the Compose postgres service is not running\n' >&2
  exit 69
fi

for service in web worker api; do
  if was_running "$service"; then
    docker compose stop "$service" >/dev/null
  fi
done

printf 'Creating PostgreSQL custom dump...\n' >&2
docker compose exec -T postgres pg_dump \
  --username "$database_user" \
  --dbname "$database_name" \
  --format custom \
  --no-owner \
  --no-privileges >"$bundle/postgres.dump"

printf 'Archiving the tenant artifact volume...\n' >&2
docker compose run --rm -T --no-deps api python -c '
import sys
import tarfile
from pathlib import Path

root = Path("/data/artifacts")
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    if root.exists():
        archive.add(root, arcname="artifacts", recursive=True)
    else:
        info = tarfile.TarInfo("artifacts")
        info.type = tarfile.DIRTYPE
        info.mode = 0o700
        archive.addfile(info)
' >"$bundle/artifacts.tar.gz"

commit="$(git rev-parse HEAD 2>/dev/null || true)"
compose_version="$(docker compose version --short)"
python - "$timestamp" "$database_name" "$compose_version" "$commit" <<'PY' >"$bundle/metadata.json"
import json
import sys

timestamp, database_name, compose_version, commit = sys.argv[1:]
print(
    json.dumps(
        {
            "schemaVersion": "1.0",
            "createdAt": timestamp,
            "database": database_name,
            "composeVersion": compose_version,
            "commit": commit or None,
            "contents": ["postgres.dump", "artifacts.tar.gz"],
            "consistency": "api, worker, and web quiesced when previously running",
            "sensitive": True,
        },
        indent=2,
        sort_keys=True,
    )
)
PY

(
  cd -- "$bundle"
  sha256sum postgres.dump artifacts.tar.gz metadata.json >SHA256SUMS
)
mv -- "$bundle/INCOMPLETE" "$bundle/COMPLETE"
printf 'Backup created: %s\n' "$bundle"
printf 'Encrypt it, copy it off-host, enforce retention, and test an isolated restore.\n'
