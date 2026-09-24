# BASEERA | بصيرة

**An AI data-analyst team for any business.** Upload a spreadsheet or connect a source, and a
team of nine specialist AI agents does the work of a senior data analyst: it reads and audits
the data, measures performance, tests hypotheses, forecasts, explains why numbers moved, finds
what drives them, segments customers, sizes the levers, prioritises recommendations and writes
the executive report — in native Arabic (RTL) or English.

**فريق محللي بيانات من الذكاء الاصطناعي لأي منشأة.** ارفع ملفك، ويتولى تسعة وكلاء متخصصين عمل
محلل بيانات خبير: فهم البيانات وتدقيقها، قياس الأداء، اختبار الفرضيات، التنبؤ، تفسير أسباب
التغيّر، اكتشاف العوامل المؤثرة، تقسيم العملاء، تقدير أثر القرارات، ترتيب التوصيات، وكتابة
التقرير التنفيذي — بالعربية أو الإنجليزية.

## The AI analyst team

| Agent | What it does |
| --- | --- |
| Chief Analyst · كبير المحللين | Frames the question, plans, delegates, investigates, answers |
| Data Engineer · مهندس البيانات | Semantic model of any table, quality audit, what the data can support |
| Statistician · الإحصائي | KPIs, distributions, correlations, group tests with effect sizes |
| Forecaster · خبير التنبؤ | Trends, seasonality, structural breaks, backtested forecasts with calibrated intervals |
| Root-cause Detective · محقق الأسباب | Exact contribution analysis of every change, root-cause path, anomalies |
| Data Scientist · عالم البيانات | Key-driver models, segmentation, customer value tiers (RFM), cohorts |
| Business Strategist · المستشار الاستراتيجي | What-if on the real levers, prioritised and sized recommendations |
| Quality Reviewer · المراجع الناقد | Re-grades every finding; verifies every number a model writes |
| Report Writer · كاتب التقارير | Executive dossier; PDF, Word, PowerPoint (native charts), HTML, Markdown |

Two rules make it trustworthy: **numbers come only from deterministic, reproducible tools**, and
**every figure a language model writes is checked against that evidence**. Raw rows never leave
the server. Read [`docs/agents.md`](docs/agents.md) for the full design.

### Try it

```sh
npm run local            # API :8100, web :3100, worker; seeds the fictional demo
```

Open <http://localhost:3100/ar/login>, choose the fictional demo, then in **AI analyst team**
pick a sample (*Retail sales* or *Subscription churn*) or upload your own CSV/Excel/JSON/Parquet
and press **Start the full analysis**. Follow the team live, read the dossier, export it, or
switch to **Ask the team** for follow-up questions.

### Choose the engine

| Engine | Configure | Notes |
| --- | --- | --- |
| Claude (recommended) | `BASEERA_ANTHROPIC_API_KEY=...` (default model `claude-opus-5`) | Tool-using chief analyst, richer investigation and writing; aggregates only are sent |
| Local model | `BASEERA_LLM_PROVIDER=ollama`, `BASEERA_LLM_BASE_URL`, `BASEERA_LLM_MODEL` | Fully on-premise; model must support tool calling |
| Built-in expert engine | nothing | Complete analysis and bilingual narrative with no model and no network |

`BASEERA_AGENT_PROVIDER=auto|anthropic|ollama|deterministic` forces a choice; see
[`.env.example`](.env.example) for effort, fallbacks and tool-call limits.

## What is actually available

Never infer completion from a screen, package, or document. Check:

- [`capabilities.json`](capabilities.json) for `implemented_tested`, `implemented_unverified`,
  `configuration_blocked`, and `unimplemented` product capabilities;
- [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) for current work and known failures;
- [`docs/evidence/index.json`](docs/evidence/index.json) for commands that actually ran and retained
  evidence.

The fictional demo proves software behavior only. It is not evidence of model accuracy, regulatory
compliance, production security, or results on a real company. Local Ollama and a disposable local
PostgreSQL source have been tested; live Odoo/private company sources have not. The Claude adapter
is contract-tested against the SDK's message shapes; no live Claude run is recorded in this
repository's evidence. OIDC is not implemented.

## Recommended local start: installed Ollama, no API key

Requires Python 3.12, uv, Node 20.20.2+, npm and the installed Ollama service.

```sh
npm run local
```

Open <http://localhost:3100/ar/login> (or `/en/login`) and choose the fictional demo.
This starts the real API at `127.0.0.1:8100` and web UI at `127.0.0.1:3100`, with SQLite
persistence and a separate metric-refresh worker. Seed is idempotent: existing data is not reset.
Stop all three processes with Ctrl+C. Use only one worker with the local SQLite database.
`qwen3.5:9b` is selected explicitly; no model download or hosted API key is required.
On this machine, live Arabic and English revenue queries returned the same deterministic value.
Check `/api/v1/assistant/status` after sign-in; installed-model availability is distinct from a
successful inference. If Ollama is stopped, run `ollama serve` in its own terminal.

Environment variables override defaults in `scripts/local-api.sh`; `.env.example` documents them.
The host scripts do not automatically execute `.env` as shell code. For overrides, set/export the
specific variables before running the command. Arabic PDF uses Noto Arabic fonts and Pango; these
are available on the tested host and installed by the API Dockerfile.

## Alternative: Docker Compose

Prerequisites: Docker Engine and Compose v2. The baseline starts PostgreSQL, an optional Redis
coordination service, API, worker, and web containers. Durable jobs currently live in PostgreSQL.
It is intended for a development machine or reviewed private host; it does not
provide public TLS, a production secrets manager, high availability, or off-host backups.

```sh
cp .env.example .env
# Review database credentials and all settings. Never commit .env.
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8100/api/v1/health/ready
```

Initialize the deterministic fictional workspace after the API is healthy:

```sh
docker compose exec -T api python -m baseera.seed
```

Open <http://localhost:3100/en/login> or <http://localhost:3100/ar/login>. Local demo identities are
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

Prerequisites: Node.js 20.20.2+, npm matching `packageManager`, Python 3.12, `uv`, PostgreSQL 17, and
Redis 8 when exercising the full persistent stack.

```sh
uv sync --frozen --extra dev --extra advanced
npm ci

# terminal 1
npm run dev:api

# terminal 2
npm run dev:web

# terminal 3, after seeding/initializing the same database
npm run dev:worker
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
- hosted endpoint: the AI analyst team supports Claude through the official Anthropic SDK
  (`BASEERA_ANTHROPIC_API_KEY`). Only schema, category labels and aggregates are sent. The
  legacy metric assistant (`/assistant`) remains local-only.

On Linux, a container cannot reach Ollama bound only to host loopback through the Docker gateway.
Use the recommended host start to reuse this machine's Ollama. For an operator-managed Docker
endpoint, set `BASEERA_DOCKER_OLLAMA_URL`; do not expose Ollama publicly. Compose configuration is
validated, but a full image-build/container readiness test is not yet recorded.

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
BASEERA_LIVE_E2E=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 npm run test:e2e --workspace @baseera/web
python scripts/performance_smoke.py --url http://localhost:8100/api/v1/health/ready
```

To reproduce the two real local Ollama checks on the fictional demo (creates two saved
conversations, does not download weights):

```sh
uv run --extra advanced python scripts/smoke_local_ollama.py --output docs/evidence/local-ollama-smoke.json
```

If Playwright's downloaded Chromium is unavailable, set `PLAYWRIGHT_EXECUTABLE_PATH` to an
installed Chromium executable; the recorded host run used `/snap/bin/chromium`.

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
[`docs/deployment.md`](docs/deployment.md), [`docs/security.md`](docs/security.md), and the templates
under [`infra/`](infra/).

## Repository map

```text
apps/web/             Next.js browser application
services/api/         FastAPI control plane and worker entry points
services/api/baseera/agents/   AI analyst team: toolkit, agents, orchestrator, critic, exports
packages/contracts/   Shared JSON contracts
tests/                Backend, browser, contract, and product evaluation suites
scripts/              Seed-fixture, verification, performance, backup, and restore utilities
infra/                Private-host operator templates (not a managed deployment)
docs/                 Architecture, metrics, connectors, security, evaluation, and runbooks
```

Key design references: [`AI analyst team`](docs/agents.md), [`architecture`](docs/architecture.md),
[`data model`](docs/data-model.md), [`metric semantics`](docs/metrics.md),
[`connectors`](docs/connectors.md), [`design system`](docs/design-system.md),
[`evaluation`](docs/evaluation.md), and [`ADR index`](docs/adr/README.md).

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
