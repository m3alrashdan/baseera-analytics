# Deployment and operations

The repository provides a Docker Compose baseline for local development and a single private VM.
It is not a public-production claim: TLS, secret injection, backups, monitoring, firewall rules,
image scanning, and recovery ownership remain deployment responsibilities.

## Prerequisites

- Docker Engine with Compose v2 for the full stack.
- For host development: Node.js 20.20.2 or newer, npm matching the lockfile, Python 3.12, and `uv`.
  The inspected environment uses Node 20.20.2 and Python 3.12; re-run version checks on the target.
- At least enough disk for PostgreSQL plus every retained original/derived artifact and one local
  backup. Capacity is workload-specific and must be measured.

## Local Compose startup

The tested host workflow is `npm run local`; it reuses installed Ollama without a hosted key.
Compose below has passed configuration rendering, but not a clean image-build/runtime drill.
Its database password is a known development default in `compose.yaml`; `.env` does not override
that explicit value. Review the complete topology before any non-local deployment.

```sh
cp .env.example .env
# Review all other values; never paste real source credentials into versioned files.

docker compose config --quiet
docker compose up --build -d
docker compose ps

curl --fail http://localhost:8100/api/v1/health/ready
curl --fail http://localhost:3100
```

The stack defines PostgreSQL, Redis, API, worker, and web services. The current durable queue lives
in PostgreSQL; Redis is an optional coordination dependency and is not used as the job authority.
Database and artifact state use named volumes. The API health check controls web startup; readiness must fail if required
control-plane dependencies are unusable rather than returning a superficial 200 response.

Run migrations before serving traffic whenever migration files exist:

```sh
docker compose run --rm api alembic -c services/api/alembic.ini upgrade head
```

Seed only the visibly fictional demo tenant:

```sh
docker compose exec -T api python -m baseera.seed
```

The demo reporting cutoff is 2026-06-30 in `Asia/Amman`, currency JOD. `tenant-demo` and
`tenant-empty` must remain isolated. Verify the actual seed command in the current README/module
before using it; the implementation status is authoritative while the backend is evolving.

For a guided local launch, `bash scripts/demo.sh` performs preflight, startup, readiness wait, and
optional seed. It makes no external source connection and sends no messages.

## Shutdown and logs

```sh
docker compose logs --since=10m api worker web
docker compose stop

# Removes containers/network but preserves named volumes:
docker compose down
```

Do not use `docker compose down -v` on valuable state. It deletes the named database, queue, and
artifact volumes and is not the normal reset procedure.

## Backup and restore

`scripts/backup.sh` creates a PostgreSQL custom dump, artifact archive, sanitized metadata, and
SHA-256 checksums in an explicit destination. Backups may contain sensitive company data: encrypt
them at rest, restrict operator access, replicate off-host, define retention, and test restore.

```sh
bash scripts/backup.sh /secure/backup-directory
```

Restore is destructive to the selected BASEERA Compose database and artifact volume. Run it only in
an isolated recovery target first, verify the archive/checksums, and supply the exact confirmation:

```sh
BASEERA_RESTORE_CONFIRM=restore-baseera \
  bash scripts/restore.sh /secure/backup-directory/baseera-YYYYMMDDTHHMMSSZ
```

The procedure stops API/worker, restores database objects and artifacts, applies current migrations,
starts services, and performs readiness checks. After restoring an older snapshot, replay retained
revocation/deletion events before exposure. A successful shell exit is not a disaster-recovery pass;
verify tenant counts, current versions, result/artifact access, and audit continuity with a recorded
evidence drill.

## Private VM topology

1. Place the repository and non-versioned environment under a dedicated service account in
   `/opt/baseera` (or adjust the example unit).
2. Bind PostgreSQL and Redis to an internal network or remove host port publication. Allow only the
   reverse proxy to reach web/API externally.
3. Terminate TLS with an organization-managed certificate. Review the example
   `infra/nginx/baseera.conf` against the actual Next.js headers/assets and CSP needs.
4. Inject secrets from the host/service manager or a secret store with least privilege. Rotate the
   session, connector-encryption, database, TLS, and provider credentials independently.
5. Pin/scan built images, run as non-root, use read-only filesystems where compatible, drop Linux
   capabilities, set CPU/RAM/PID limits, and restrict worker/source egress.
6. Send structured logs/metrics to an access-controlled backend. Alert on readiness, queue age,
   repeated job/provider failure, source staleness/schema drift, permission denials, disk capacity,
   backup age, and certificate expiry.
7. Schedule encrypted backups and periodic restore drills. Keep database and artifacts at one
   recoverable consistency point.

The checked-in Compose file does not yet assert all of these controls. Treat `infra/` as an operator
template and perform environment review before making the service externally reachable.

## Health and rollout

- **Liveness** means the process can serve; it must not depend on every optional external provider.
- **Readiness** requires migrations plus required PostgreSQL/artifact access and reports an
  unhealthy dependency without secrets.
- Optional model/connectors expose `not_configured` or degraded capability states without making the
  deterministic core unavailable.
- Roll out migrations with a backup and compatibility window. Prefer expand/migrate/contract changes;
  destructive schema changes need their own rollback/restore rehearsal.
- Drain request traffic, stop new jobs, checkpoint/cancel workers, deploy, migrate, start workers,
  then restore traffic. Preserve idempotency records across the rollout.

## Resource profiles and performance

No CPU/RAM sizing or throughput target is claimed before measurement. Record at least two profiles:

| Profile | Dataset and concurrency | Resources | Required measurement |
| --- | --- | --- | --- |
| Demo | Deterministic default seed, one user/job | Actual host/container limits | Startup, dashboard p50/p95, import time, peak memory |
| Representative | Authorized expected rows/files and concurrent users/jobs | Proposed VM limits | API/filter latency, queue time, ingestion throughput, failure rate, storage growth |

Heavy ingestion, OCR, advanced models, and optimization may require separate worker resource limits.
GPU and paid providers are optional; the deterministic core must start without them. Record model
revision, latency, tokens/cost, and provider policy when enabled.

## CI and release

`.github/workflows/ci.yml` checks evaluation contracts, Compose syntax, Python and web format/lint/
types/tests/build using pinned lockfiles. Credentialed live integration and destructive restore drills
do not run in untrusted pull requests. A release is blocked by a critical security/correctness
failure, capability/evidence mismatch, missing migrations, or failed integrated browser journey.

See [`security.md`](security.md), [`evaluation.md`](evaluation.md), and
[`evidence/README.md`](evidence/README.md) before interpreting readiness.
