# Verification evidence index

This directory distinguishes an implementation claim from proof. The machine-readable index is
[`index.json`](index.json). Initial entries are `not_run` or credential-blocked; promote an entry
only after its exact command completes and durable, non-sensitive artifacts are stored.

## Status meanings

| Status | Meaning |
| --- | --- |
| `passed` | The recorded command/check ran successfully in the named environment and evidence is retained |
| `failed` | The check ran and a required assertion failed; the failure remains visible |
| `not_run` | No result has been recorded; never phrase this as passing |
| `blocked` | A named external dependency, credential, or unavailable facility prevented execution |

The capability manifest uses a separate product state vocabulary. `implemented_tested` requires at
least one matching passed evidence entry and no contradictory unresolved critical failure.

## Current gate summary

| Gate | Recorded scope | Evidence |
| --- | --- | --- |
| AI corpus structure | Passed; no model benchmark | 72 held-out cases validated structurally |
| Backend and frontend tests/build | Passed | JUnit, coverage and verification summary |
| Import → clean → metric → dashboard/report | Passed | Two production-mode real API journeys |
| Metric equality and cleaning reconciliation | Passed for tested scopes | Fixture oracle and reporting-cutoff equality |
| Tenant/field/artifact isolation | Passed for implemented routes tested | Negative scope/revocation API tests |
| Visual/RTL/accessibility | Partial | Two inspected captures; full zoom/a11y review not run |
| Deterministic assistant | Passed | Typed provider-double workflow tests |
| Live Ollama/local PostgreSQL | Passed | Separate sanitized local smoke records |
| Live Odoo/private company database | Blocked | No authorized external source credentials; full integration incomplete |
| Performance baseline | Health endpoint only | p50/p95/error counts; no product-scale benchmark |
| Backup/restore | Not run | Isolated restore, checksum, migrations, health and data checks |

## Artifact naming

Use UTC timestamps and a stable gate ID, for example:

```text
docs/evidence/runs/20260904T153000Z/backend.unit-integration.log
docs/evidence/runs/20260904T160000Z/visual.ar-dark-mobile.png
docs/evidence/runs/20260904T160000Z/visual.ar-dark-mobile.review.md
```

Do not retain secrets, raw connector strings, session cookies, protected source rows, unrestricted
model prompts, or personal data in CI artifacts. Redact first, then attach a checksum where useful.
For each run record commit/worktree state, OS/runtime versions, relevant non-secret configuration,
command, start/end time, exit code, counts, and limitations using
[`../testing/evidence-template.md`](../testing/evidence-template.md).
