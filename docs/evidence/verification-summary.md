# Local verification — 2026-09-05 UTC / 2026-09-06 Asia/Amman

Worktree is uncommitted/untracked. No external deployment is claimed. Host: Linux, Python 3.12.3,
Node 20.20.2, npm 10.8.2; 16 logical CPU threads, approximately 16 GiB RAM. Ollama uses CPU-only
inference. The fictional seed uses reporting cutoff 2026-06-30, Asia/Amman and JOD.

## Executed checks

| Gate | Reproduction command / artifact | Result and limitation |
| --- | --- | --- |
| Backend | `uv run --extra advanced pytest -q --cov=services/api/baseera --cov-report=term --cov-report=xml:docs/evidence/backend-coverage.xml --cov-fail-under=80 --junitxml=docs/evidence/backend-junit.xml` | Exit 0; 106 passed, 3 skipped; 85.05 s; 85.31% statement coverage |
| PostgreSQL source | `.venv/bin/pytest -q tests/connectors/test_postgres_live.py --junitxml=docs/evidence/postgres-junit.xml` with injected dedicated local source DSN | Exit 0; 3 passed, 1.05 s; keyset ties/precision, null watermark and read-only transaction checks |
| Web tests | `npm run test --workspace @baseera/web -- --reporter=default --reporter=junit --outputFile=../../docs/evidence/web-junit.xml` | Exit 0; 20 passed in 9 files |
| Production build | `npm run build --workspace @baseera/web` | Exit 0; Next 15.5.25; 137 kB first-load JS on dynamic product route; standalone output present |
| Production server | `npm run start --workspace @baseera/web` | Standalone web on loopback 3100, API on 8100; assets staged by `apps/web/scripts/start.mjs` |
| Browser | `PLAYWRIGHT_JUNIT_OUTPUT_FILE=../../docs/evidence/browser-junit.xml BASEERA_LIVE_E2E=1 PLAYWRIGHT_EXECUTABLE_PATH=/snap/bin/chromium PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 npm run test:e2e --workspace @baseera/web -- --workers=1 --output=test-results-release-check --reporter=list,junit` | Exit 0; 8 passed in 11.7 s; 2 full real-API journeys plus 6 contract/mock tests |
| Python quality | `uv run ruff format --check services tests scripts`; `uv run ruff check services tests scripts`; `uv run mypy services/api/baseera` | Passed; 17 typed source files |
| Web quality | Workspace scripts `lint`, `typecheck`, `format:check` | Passed |
| Advisory audit | `npm audit --json` | Exit 0; all severity counts 0 at check time; no application/container security certification |
| Compose | `docker compose config --quiet` | Exit 0; configuration only, no image-build/runtime claim |
| Ollama | `uv run --extra advanced python scripts/smoke_local_ollama.py --output docs/evidence/local-ollama-smoke.json` | Exit 0; two live requests, matching result ID/value and overview reporting cutoff |
| Health smoke | `uv run python scripts/performance_smoke.py --url http://127.0.0.1:8100/api/v1/health/ready --provider-mode ollama --output docs/evidence/local-health-smoke.json` | 30/30 HTTP 200; p50 8.509 ms, p95 12.761 ms; one endpoint only |

Python emitted one upstream `BlockingPortal` deprecation warning. The worker subprocess test checks
real persistence, but its child process is outside coverage collection. PostgreSQL DSN credentials
were injected from a dedicated test container and were not printed or retained.

## Scope and independent checks

- Browser fixture: duplicate ID 001 has revenue 100; another row has -10. Reviewed deduplication
  yields exactly 90. A saved dashboard survives reload. Report JSON retains its result reference,
  exact value and a SHA-256 checksum. Both locales assert no page errors or horizontal overflow.
  Tests append fictional demo reports; they do not erase user data.
- Evidence-scope tests deny broader results after department-manager demotion, reject cross-scope
  report references and preserve historical dashboard widgets with optimistic version conflicts.
  A future-dated order test checks overview/assistant/worker equality at the reporting cutoff.
- A deterministic competing-transaction regression test reproduced an unhandled uniqueness error
  during cleaning publication. Cleaned artifacts now use unique version IDs in their paths, and
  conflicts at flush/commit return HTTP 409. The winning version still calculates 777 and its raw
  source still calculates 100 after the losing write; numeric-path legacy artifacts stay intact.
  Failed publication can leave an unreferenced immutable file; garbage collection is not implemented.
  Retained targeted result: `cleaning-concurrency-junit.xml` (1 passed); the final backend suite also
  includes this regression test.
- Worker tests cover real result publication, a separate process, revoked membership and malformed
  identifiers. Recovery tests manipulate persisted heartbeat state; they are not exhaustive
  process-kill/chaos or multiple-worker SQLite testing.
- Unicode PDF tests verify Arabic text/pagination and deny network/file/data URL fetching.
  A generated Arabic sample retained Arabic characters through `pdftotext`; complex chart/table
  print layout is not comprehensively certified.
- REST/Odoo adapters use mocked transports; PostgreSQL uses a disposable local source. Automatic
  remote fetch plus credential/mapping/publication workflows are not yet integrated end to end.

## Visual inspection

Inspected [Arabic dark mobile report](visual/ar-dark-mobile-report.png): joined Arabic, readable
forms and saved titles, reachable six-format export controls, no document horizontal overflow.
The assistant shortcut is below content rather than covering mobile export controls.

Inspected [English dark desktop overview](visual/en-dark-desktop-overview.png): visible cutoff and
fictional-data labels, readable metrics and exceptions, explicit unavailable chart values. The fixed
assistant shortcut still occupies part of the desktop right edge. Comprehensive keyboard/zoom,
contrast and every-screen review remain outstanding.

No full held-out model benchmark, private-source test, OIDC flow, clean Compose runtime,
backup/restore drill, representative load profile or independent security audit is claimed.

The CI workflow was updated to install advanced test dependencies, enforce 80% Python coverage,
and run seeded real-API journeys against the production standalone web build. Its YAML was parsed
locally; no GitHub Actions execution or success is claimed. Local equivalent journey results are above.
