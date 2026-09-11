# Test-driven delivery plan

The unit of delivery is a business invariant, not a screen. Each slice starts with a failing
deterministic assertion, implements the smallest end-to-end behavior, refactors behind stable
contracts, and then adds adversarial/regression coverage.

## Loop

1. **Red**: add a test tied to a requirement and expected result/evidence category. Confirm it fails
   for the intended reason; a syntax/import failure is not the desired red state.
2. **Green**: implement the smallest API, persistence, worker, and UI path that satisfies it with
   real state.
3. **Refactor**: remove duplication while preserving generated contracts and authorization checks.
4. **Adversarial**: add tenant, malformed input, stale version, duplicate request, interruption, and
   unavailable-provider cases appropriate to the slice.
5. **Evidence**: run the exact gate, store output, and update `docs/evidence/index.json` and
   `capabilities.json` without promoting unrelated capabilities.

## Risk-ordered suites

| Priority | Suite | Essential assertions |
| --- | --- | --- |
| P0 | Tenant and protected-field isolation | IDs, query filters, artifacts, jobs, caches, search, citations, graph, exports, revoked access |
| P0 | Analytical correctness | Golden metric formulas, joins/fan-out, currencies, timezone boundaries, null/zero, cross-surface equality |
| P0 | Cleaning/version integrity | Original immutability, preview/apply binding, leading-zero IDs, legitimate returns, missing cost, quarantine, reconciliation, rollback |
| P1 | Idempotency/recovery | Duplicate upload/mutation, checkpoint replay, retry, cancel, process restart, version conflict |
| P1 | Assistant/tool trust | Typed arguments, evidence IDs, clarification/abstention, provider failure, injection, no unsupported claims |
| P1 | Report/dashboard persistence | Accepted diff, optimistic conflict, dependency recalculation, history, authorized export |
| P1 | Connector behavior | Capability discovery, schema drift, cursor retry, deletion policy, SSRF and query bounds |
| P2 | Forecast/process/optimization | Temporal split, baseline, intervals, eligibility, infeasibility, event-time math, reproducibility |
| P2 | Browser/a11y/i18n | Core journeys, RTL/LTR, keyboard/focus, zoom, themes, mobile, errors, print |
| P2 | Operational | Health/readiness, migrations, backup/restore, load profile, logs without secrets |

## Layering

- **Pure unit tests** cover formulas, normalization, policies, state machines, schemas, and chart/tool
  validators. They run without network, Redis, or a model.
- **Repository tests** use isolated tenant fixtures and the same query layer as production.
- **API integration tests** authenticate representative roles and exercise persistence, idempotency,
  errors, and artifact access.
- **Worker tests** use deterministic queues/clocks and real small files; restart tests exercise a
  separate process and durable checkpoint.
- **Contract tests** compare generated frontend/OpenAPI shapes and every connector/provider adapter
  against deterministic doubles.
- **Browser tests** use the integrated stack. Assertions include persistence after reload/back,
  evidence rail content, usable focus, and meaningful failure states—not only screenshots.
- **Product evals** use the held-out bilingual corpus. Deterministic graders own numbers, evidence,
  tools, and policy; model/human graders are limited to qualitative clarity.

## Fixture strategy

The fictional demo fixture is versioned and seeded through normal ingestion paths. It has an
independent oracle describing expected row counts, control totals, metric values, known dirty rows,
schema drift, and access results. Dashboard/report JSON is never the oracle. The reporting cutoff is
2026-06-30, timezone `Asia/Amman`, currency JOD; the empty tenant is separate.

Each test creates or namespaces its own tenant and idempotency keys. Tests never depend on execution
order or today's wall clock. Random generators require an explicit stable seed recorded in output.

## Release gates

```text
fast:       format + lint + type + pure tests + schema/eval validators
integration: database/queue + API + worker + migration forward/back compatibility
browser:    core journey + RTL/LTR + a11y + print/export
security:   cross-tenant + field/artifact + injection/SSRF + revocation
resilience: restart + retry + duplicate + partial upstream
live:       provider/source smoke (credentialed, separate, never replaced by mocks)
```

Release-critical regression tests target `pass^3 = 1.00` when run repeatedly. Capability evals
report pass@1 and pass@3 where multiple attempts are meaningful; retries cannot hide the first-attempt
rate. A gate near the threshold remains failed until the defined threshold is met.

## Minimum vertical-slice acceptance

- Dirty multi-sheet XLSX reaches an immutable original version with full sheet/row coverage.
- Profile/quality issues identify duplicate batch, mixed locales, leading-zero IDs, missing costs,
  malformed rows, and legitimate negative returns correctly.
- Preview is version-bound; apply creates a new version and reconciles counts/control totals;
  rollback preserves history.
- `net_revenue` and another approved metric match the independent oracle and the same result appears
  in API/chat/dashboard/report/export for identical scope.
- Executive UI exposes definition, filters, freshness, lineage, warnings, and result ID.
- A second tenant and a restricted role cannot infer or fetch the data through any alternate path.
- Persistence survives controlled service restart.

Use [`evidence-template.md`](evidence-template.md) for every manual or automated gate result.

