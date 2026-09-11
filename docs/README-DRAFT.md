# Archived initial README draft — not operational instructions

This historical draft contains outdated ports, provider plans and capability statements.
Use the root [README](../README.md) and [implementation status](../IMPLEMENTATION_STATUS.md).

# BASEERA | بصيرة

BASEERA is a bilingual, tenant-aware analytics and decision-support application. It turns approved
company data into governed metrics, evidence-linked dashboards, editable reports, and reviewed
actions. Arabic uses a real right-to-left interface; English uses left-to-right presentation.

> **Promotion note:** this file is the draft for the repository-root `README.md`. Paths below are
> written relative to the repository root. Capability state—not this introduction—is authoritative.

## What is actually available

Never infer completion from a screen, package, or document. Check:

- [`capabilities.json`](../capabilities.json) for `implemented_tested`, `implemented_unverified`,
  `configuration_blocked`, and `unimplemented` product capabilities;
- [`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md) for current work and known failures;
- [`docs/evidence/index.json`](evidence/index.json) for commands that actually ran and retained
  evidence.

The fictional demo proves software behavior only. It is not evidence of model accuracy, regulatory
compliance, production security, or results on a real company. Hosted AI, OIDC, Odoo, and external
database checks stay configuration-blocked until an authorized endpoint and credentials are tested.

## Fastest local start: Docker Compose

Prerequisites: Docker Engine and Compose v2. The baseline starts PostgreSQL, Redis, API, worker, and
web containers. It is intended for a development machine or reviewed private host; it does not
provide public TLS, a production secrets manager, high availability, or off-host backups.

```sh
cp .env.example .env
# Replace every placeholder, especially the session secret. Never commit .env.
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8000/api/v1/health/ready
```

Initialize the deterministic fictional workspace after the API is healthy:

```sh
docker compose exec -T api python -m baseera.seed
```

Open <http://localhost:3000/en/login> or <http://localhost:3000/ar/login>. Local demo identities are
created only by the seed command:

| Workspace / role | Email | Development-only password |
| --- | --- | --- |
| Fictional demo / executive | `executive@demo.baseera.local` | `BaseeraDemo!2026` |
| Fictional demo / support manager | `manager@demo.baseera.local` | `BaseeraManager!2026` |
| Fictional demo / HR specialist | `hr@demo.baseera.local` | `BaseeraHR!2026` |
| Empty workspace / viewer | `viewer@empty.baseera.local` | `BaseeraEmpty!2026` |

These known credentials must never be exposed on a public deployment. Use enterprise identity or
deployment-specific accounts outside local evaluation.

Stop containers while retaining named volumes:

```sh
docker compose down
```

Do not add `-v` unless deletion of the database, queue, and artifact volumes is explicitly intended.

## Demo walkthrough

Use the reporting cutoff **30 June 2026**, timezone **Asia/Amman**, and currency **JOD** so results
remain deterministic.

1. Sign in as the demo executive and confirm the organization, cutoff, timezone, freshness, and
   selected comparison period.
2. Open the executive overview, select a metric, and inspect its definition, filters, source/data
   version, warnings, and result ID in the evidence panel.
3. Ask the same scoped question in Arabic and English. A configured assistant should call governed
   tools; if no provider is configured, it must say so rather than return a canned answer.
4. Use the ingestion workspace with a generated dirty workbook. Review quarantined rows and a
   cleaning preview before applying; the original remains immutable.
5. Save an evidence-linked dashboard/report revision, reload it, and inspect version history. Data
   blocks retain result references; narrative edits do not silently change numbers.
6. Sign in to the empty workspace and verify that demo metrics, artifacts, jobs, and search results
   are absent. Repeat restricted people-data checks with the support manager.

Only steps backed by `implemented_tested` capabilities should be treated as verified. An unavailable
control should explain the missing capability or configuration.

## Host development

Prerequisites: Node.js 20.9+, npm matching `packageManager`, Python 3.12, `uv`, PostgreSQL 17, and
Redis 8 when exercising the full persistent stack.

```sh
uv sync --frozen --extra dev
npm ci

# terminal 1
uv run uvicorn baseera.main:app --reload --app-dir services/api --port 8000

# terminal 2
npm run dev:web
```

Seed from the API package directory so Python resolves the package without a global install:

```sh
PYTHONPATH=services/api uv run python -m baseera.seed
```

Configuration is environment-driven. Copy `.env.example`, keep it untracked, and review at least
database/Redis URLs, artifact root, web/API origins, cookie environment, connector destination
allow-lists, and LLM settings. Client-visible `NEXT_PUBLIC_*` variables must never contain secrets.

### AI provider modes

- `disabled`: deterministic data, metrics, dashboards, and supported analytics continue to work;
  conversational generation reports `not_configured`.
- local endpoint: set the configured provider/base URL/model to an operator-approved local service;
  model availability, license, privacy, and resource use still require verification.
- hosted endpoint: inject its key through deployment secret management and enforce the provider data
  classification policy. No hosted key is required for deterministic calculations or tests.

Do not silently download model weights. Record every live smoke run separately from deterministic
provider-double tests, including the exact model revision and non-secret policy configuration.

## Deterministic data generation

The normal seed is modest: seven departments, about 100 fictional employees, 20 projects, and
enough transactions/events for visible trends. Generate file-ingestion fixtures at a chosen scale:

```sh
uv run python scripts/generate_demo.py --output ./var/generated-demo --scale 1 --seed 20260630
```

Use `--help` for limits and formats. The generator writes a manifest with counts and hashes; it does
not insert into a company database, contact external systems, or prove production performance.

## Verification

Run gates separately so a missing optional system does not obscure deterministic failures:

```sh
python scripts/validate_ai_evals.py
python scripts/validate_json_contracts.py
docker compose -f compose.yaml -f infra/compose.validate.yml --env-file .env.example config --quiet

uv run ruff format --check services tests scripts
uv run ruff check services tests scripts
uv run mypy services/api/baseera
uv run pytest

npm run format:check --workspace @baseera/web
npm run lint --workspace @baseera/web
npm run typecheck --workspace @baseera/web
npm run test --workspace @baseera/web
npm run build --workspace @baseera/web
```

After a healthy, seeded integrated stack:

```sh
npm run test:e2e --workspace @baseera/web
python scripts/performance_smoke.py --url http://localhost:8000/api/v1/health/ready
```

The HTTP performance smoke measures only the named endpoint under the recorded machine/profile; it
is not an enterprise-scale benchmark. Browser screenshots are evidence only after inspection for
RTL, Arabic shaping, overflow, focus, contrast, chart alternatives, console errors, and print layout.

## Backup, restore, and deployment

Create a database/artifact bundle in an explicit protected directory:

```sh
bash scripts/backup.sh /secure/baseera-backups
```

Restore is intentionally confirmation-gated and should first target an isolated recovery project:

```sh
BASEERA_RESTORE_CONFIRM=restore-baseera \
  bash scripts/restore.sh /secure/baseera-backups/baseera-YYYYMMDDTHHMMSSZ
```

A zero exit code is not a recovery certification. Verify checksums, migrations, readiness, tenant
counts, current versions, permission revocation, artifact access, and audit continuity. See
[`docs/deployment.md`](deployment.md), [`docs/security.md`](security.md), and the templates under
[`infra/`](../infra/).

## Repository map

```text
apps/web/             Next.js browser application
services/api/         FastAPI control plane and worker entry points
packages/contracts/   Shared JSON contracts
tests/                Backend, browser, contract, and product evaluation suites
scripts/              Seed-fixture, verification, performance, backup, and restore utilities
infra/                Private-host operator templates (not a managed deployment)
docs/                 Architecture, metrics, connectors, security, evaluation, and runbooks
```

Key design references: [`architecture`](architecture.md), [`data model`](data-model.md),
[`metric semantics`](metrics.md), [`connectors`](connectors.md), [`design system`](design-system.md),
[`evaluation`](evaluation.md), and [`ADR index`](adr/README.md).

## Safety boundaries

- Server-side policy—not UI visibility—controls tenant, row, department, protected-field, artifact,
  search, graph, cache, scheduled-job, and export access.
- Source connectors are read-only unless a separately reviewed write capability exists. Demo actions
  never send email, update CRM/Odoo, or contact real people.
- Facts, forecasts, assumptions, hypotheses, and recommendations remain visibly distinct. Missing,
  unavailable, suppressed, and denied values are not converted to zero.
- Do not put credentials, protected rows, raw prompts containing sensitive data, session cookies, or
  connection strings in logs, screenshots, CI artifacts, evidence, or bug reports.

Report security problems privately to the repository owner; do not attach real company data to an
issue. Production use requires an environment-specific threat review, hardening, retention policy,
backup drill, monitoring, and authorization test.
