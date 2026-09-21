# BASEERA implementation status

Updated: 2026-09-21 (Asia/Amman)

A persisted local application is working with real Ollama inference and a tested
import → reviewed cleaning → metric → saved dashboard → report/export journey.
**The entire original specification is not complete; public production readiness is not certified.**

## Run locally

Run `npm run local`, open <http://localhost:3100/ar/login>, and choose the fictional demo.
This installs locked dependencies, idempotently seeds SQLite and starts web, API and one worker.
Installed `qwen3.5:9b` is selected through Ollama at 127.0.0.1:11434; no hosted API key or model
download is required. Existing data is not reset. See [README](README.md) for environment overrides.

For production-mode local web testing, run `npm run build`, then
`npm run start --workspace @baseera/web` while the same API/worker are running.
Do not run development and production web servers on port 3100 simultaneously.

## Verified scope

- Local sessions, CSRF/origin checks, tenant/department restrictions, protected HR projections
  and permission rechecks when reading stored evidence or executing metric jobs.
- CSV/TSV/XLSX/JSON/JSONL/Parquet uploads, full accepted-row profiles, reviewed deterministic
  cleaning, immutable versions, idempotency, reconciliation and publication rollback.
- Seven company metrics, scoped company read views, persisted dashboards and versioned reports;
  JSON/HTML/PDF/DOCX/CSV/XLSX exports. Arabic PDF uses Unicode fonts and pagination.
- Local Ollama typed planning through LangGraph, deterministic calculations and scoped conversation
  history. Invalid plans fail closed. All-history metrics share the overview/worker reporting cutoff.
- Baseline temporal support-demand forecasting, case paths, bounded resource assignment,
  queue simulation and assumption-labeled synthetic causal estimation.
- Read-only PostgreSQL adapter exercised against a disposable local database; REST/Odoo
  mock-transport contract tests, not live company-system verification.
- Server-side connector execution: the deployment stores credentials encrypted with AES-256-GCM
  and fetches from the source itself through the REST/Odoo/PostgreSQL adapters. Credentials are
  bound to their tenant and connector, are never returned by the API, and a retired key still
  decrypts while the value is re-sealed by the active key. Outside development the API refuses to
  start without `BASEERA_SECRET_KEY`. Verified in the Compose deployment on PostgreSQL: the
  plaintext appears nowhere in a full `pg_dump`.
- Docker Compose build and runtime verified end to end on PostgreSQL in `production` mode:
  all five containers healthy, seed applied, connector created and credentials stored.
- A separate worker calculates and persists metric-refresh results. Revoked owners and malformed
  requests fail explicitly; cancellation, persisted recovery and idempotency have scoped tests.

## Latest evidence

| Check | Actual result |
| --- | --- |
| Backend suite | 159 passed; 4 skipped (3 dedicated PostgreSQL, 1 data-dependent) |
| Python coverage | 82% statement coverage; subprocess worker coverage is not collected |
| Dedicated local PostgreSQL source | All 3 skipped cases passed in a separate configured run |
| Web unit/component suite | 20 passed in 9 files |
| Production-mode browser suite | 8 passed: 2 full real-API journeys and 6 contract/mock checks |
| Lint and formatting (`ruff check`, `ruff format --check`) | Passed |
| Type check (`mypy`) | **Fails: 36 pre-existing errors** in cleaning, deliverables, forecasting, insights, analytics |
| Clean Docker build and runtime on PostgreSQL | Passed; stack healthy, credentials encrypted at rest |
| npm advisory audit | 0 reported vulnerabilities at check time; not a security certification |
| Real Ollama bilingual smoke | Arabic 35.813 s; English 20.315 s; both 1,019,113.64 JOD and identical result ID |

Timings are two local observations, not performance promises or a general model-accuracy result.
The 72 held-out AI cases are structurally validated but have not been executed as a complete model
benchmark. See [verification summary](docs/evidence/verification-summary.md),
[evidence index](docs/evidence/index.json) and [capability manifest](capabilities.json).

## Not complete / not verified

- OCR/PDF document ingestion, interactive 3D, OIDC, hosted providers, MySQL/SQL Server,
  Chronos and TabPFN adapters.
- Connector discovery/mapping UI and canonical publication from synced records. Credential
  storage and server-side fetch execution are now implemented; mapping a customer schema onto
  governed metrics is still manual.
- Background report-export/connector-sync adapters: these fail explicitly. Schedule metadata is
  saved, but cron/alert delivery is not implemented. Decision records are not a full approval flow.
- Full collaborative report/dashboard designer, complete accessibility/zoom review, raw-source
  lineage, representative load tests, live company validation and full adversarial AI evaluation.
- Backup/restore drill, hardened public deployment (TLS, reverse proxy), enterprise identity
  (OIDC/SSO is not implemented), monitoring/alerting and independent security review.
- Alembic migrations describe the full schema and `alembic check` reports no drift, but the
  application still calls `Base.metadata.create_all()` at startup, so a customer upgrade path
  between released versions is not yet proven.
- `mypy` does not pass on the pre-existing modules listed above; CI's type-check step fails.
- Scheduled execution: `Schedule` rows with a cron field are stored, but no executor runs them,
  so connector sync and metric refresh are still triggered manually.

Use one worker with local SQLite. Ingestion is bounded but synchronous. Known demo credentials
must never be exposed publicly. Capability labels describe limited tested scope, not every
requirement implied by a broad feature name.
