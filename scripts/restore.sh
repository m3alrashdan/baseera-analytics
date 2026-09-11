#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  printf 'Usage: BASEERA_RESTORE_CONFIRM=restore-baseera %s /exact/backup-bundle\n' "$0" >&2
  printf 'This replaces the selected Compose database and artifact volume.\n' >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 64
fi
if [[ "${BASEERA_RESTORE_CONFIRM:-}" != "restore-baseera" ]]; then
  printf 'restore refused: set BASEERA_RESTORE_CONFIRM=restore-baseera exactly\n' >&2
  exit 77
fi

command -v docker >/dev/null 2>&1 || {
  printf 'restore failed: docker is not installed\n' >&2
  exit 69
}

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_directory/.." && pwd)"
cd -- "$repository_root"
docker compose version >/dev/null
docker compose config --quiet

bundle="$(cd -- "$1" 2>/dev/null && pwd)" || {
  printf 'restore failed: bundle directory does not exist\n' >&2
  exit 66
}
if [[ "$bundle" == "/" || "$bundle" == "$repository_root" ]]; then
  printf 'restore refused: invalid bundle path %s\n' "$bundle" >&2
  exit 64
fi
for required in COMPLETE SHA256SUMS postgres.dump artifacts.tar.gz metadata.json; do
  if [[ ! -f "$bundle/$required" ]]; then
    printf 'restore failed: missing %s\n' "$required" >&2
    exit 65
  fi
done

printf 'Verifying bundle checksums...\n' >&2
(
  cd -- "$bundle"
  sha256sum --check SHA256SUMS
)

database_name="${BASEERA_POSTGRES_DB:-baseera}"
database_user="${BASEERA_POSTGRES_USER:-baseera}"
for identifier in "$database_name" "$database_user"; do
  if [[ ! "$identifier" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
    printf 'restore failed: database identifiers contain unsupported characters\n' >&2
    exit 64
  fi
done

restore_complete=0
on_exit() {
  if [[ "$restore_complete" -ne 1 ]]; then
    printf 'Restore did not complete. API, worker, and web remain stopped for inspection.\n' >&2
  fi
}
trap on_exit EXIT

printf 'Stopping request and job services...\n' >&2
docker compose stop web worker api >/dev/null || true
docker compose up -d postgres redis >/dev/null

printf 'Replacing the Compose database...\n' >&2
docker compose exec -T postgres dropdb \
  --username "$database_user" \
  --force \
  --if-exists "$database_name"
docker compose exec -T postgres createdb --username "$database_user" "$database_name"
docker compose exec -T postgres pg_restore \
  --username "$database_user" \
  --dbname "$database_name" \
  --no-owner \
  --no-privileges <"$bundle/postgres.dump"

printf 'Replacing the Compose artifact volume...\n' >&2
docker compose run --rm -T --no-deps \
  --volume "$bundle:/restore:ro" \
  api python -c '
import shutil
import tarfile
from pathlib import Path

root = Path("/data/artifacts")
archive_path = Path("/restore/artifacts.tar.gz")
with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    for member in members:
        if member.issym() or member.islnk() or member.isdev():
            raise SystemExit(f"unsafe archive member: {member.name}")
        target = (Path("/data") / member.name).resolve()
        if Path("/data").resolve() not in target.parents and target != Path("/data").resolve():
            raise SystemExit(f"archive path escapes target: {member.name}")
        if member.name != "artifacts" and not member.name.startswith("artifacts/"):
            raise SystemExit(f"unexpected archive root: {member.name}")
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    archive.extractall("/data", members=members, filter="data")
'

printf 'Applying repository migrations...\n' >&2
docker compose run --rm -T api alembic -c services/api/alembic.ini upgrade head

docker compose up -d api worker web >/dev/null
deadline=$((SECONDS + 120))
until curl --fail --silent --show-error \
  http://localhost:8100/api/v1/health/ready >/dev/null; do
  if ((SECONDS >= deadline)); then
    printf 'restore failed: readiness did not pass within 120 seconds\n' >&2
    exit 1
  fi
  sleep 2
done

restore_complete=1
printf 'Restore procedure completed from: %s\n' "$bundle"
printf 'Still required: tenant/version counts, permission/revocation, artifact, audit, and app checks.\n'
