# Evaluation protocol and current results

BASEERA uses deterministic tests for calculations and policy, a versioned bilingual product-eval
corpus for assistant behavior, manual inspection for visual judgment, and separate credentialed
smoke tests for external providers. A mock or provider double never certifies a live integration.

## Test assets

| Asset | Purpose |
| --- | --- |
| `tests/evaluation/held_out_cases.v1.jsonl` | 72 held-out English/Arabic assistant cases; never use as prompt examples |
| `tests/evaluation/held_out_manifest.v1.json` | Fixed fixture, split, defaults, and expected JSONL count |
| `tests/evaluation/development_cases.v1.json` | Small visible examples for local harness development |
| `tests/evaluation/ai-case.schema.json` | Case/result contract |
| `tests/evaluation/ai-result.schema.json` | One recorded assistant attempt for result JSONL |
| `scripts/validate_ai_evals.py` | Dependency-free structural and coverage validator |
| `scripts/summarize_ai_evals.py` | Full-denominator metrics from recorded result JSONL |
| `docs/evidence/index.json` | Machine-readable gate status and artifact locations |

The held-out corpus has 36 English and 36 Arabic records and covers sales, people, projects, operations, budgets, source provenance,
ambiguity, insufficient data, forecasts, authorization, cross-module reasoning, and stateful
follow-ups. Each locale/topic combination has multiple cases. Cases specify expected outcome,
authorized tool family, evidence/fixture oracle, tolerances where numerical, clarification or
abstention requirements, and prohibited disclosures.

The case text lives in the repository to make evaluation reproducible; application prompts and
few-shot examples must not copy the held-out prompts or expected answers. Changes require a corpus
version bump and a reason in review.

## Outcome contract

| Outcome | Required behavior |
| --- | --- |
| `answer` | Execute approved tools; return result-backed values with evidence and scope |
| `clarify` | Ask one focused question because alternatives materially change the calculation |
| `abstain_insufficient_data` | Name missing inputs and a concrete way to provide them; invent nothing |
| `deny` | Enforce access without leaking whether protected resources/values exist |
| `unavailable` | Name an unsupported/not-configured dependency and preserve any safe deterministic result |

Facts, forecasts, assumptions, hypotheses, and recommendations are graded as distinct claim types.
A recommendation must identify evidence and assumptions; it cannot be presented as an observed fact.

## Grading

Deterministic graders take precedence for:

- numeric values against the independent fixture oracle, including currency and tolerance;
- metric/data version, filters, timezone, reporting cutoff, coverage, and evidence/result IDs;
- expected tool family and successful execution status;
- response outcome and stable error category;
- authorization, field suppression, cross-tenant access, and prohibited exposure;
- dashboard/report/export equality and accepted version change.

A rule grader checks required clarification fields, uncertainty language, source freshness, and claim
labels. A model grader may score concise usefulness and Arabic/English quality using a fixed rubric,
but it cannot override a deterministic numeric or security failure. Human review adjudicates genuine
semantic ambiguity and visually inspects rendered results.

## Metrics and denominator

Every attempted case ends in exactly one denominator bucket:

- `verified_automatic_completion`
- `completed_with_human_correction`
- `correct_abstention`
- `incorrect_abstention`
- `failed`
- `timed_out`

Report `attempted` as the sum of all six, including tool/provider failures. Accuracy is
`(verified automatic + correct abstention) / attempted`; automation is
`verified automatic / attempted`. Report these separately. Also report:

- numeric/factual correctness among applicable attempted cases;
- evidence support rate among answers requiring evidence;
- tool execution success among required tool calls;
- clarification quality among clarification cases;
- unsupported-claim rate among attempted cases;
- access-policy compliance among authorization/adversarial cases;
- latency p50/p95, tool count, token use, and cost only when captured consistently.

For repeated stochastic trials, report pass@1 directly, pass@3 for at-least-one success, and pass^3
for three consecutive successes. Critical authorization and regression suites require pass^3 = 1.00;
retries never erase first-attempt failures.

## Commands

```sh
# Structural validation only; does not call an assistant
python scripts/validate_ai_evals.py

# Run all repository tests when dependencies are installed
uv run pytest
npm test

# Summarize a result file emitted by an evaluation runner
python scripts/summarize_ai_evals.py path/to/results.jsonl

# Integrated browser journey, after the stack is healthy and seeded
npm run test:e2e --workspace @baseera/web
```

Provider-double runs must record `providerMode=deterministic_double`. Live provider runs use a
separate evidence record with provider/model/revision, policy, sanitized configuration, timeouts,
and rate limits. The installed local Ollama model has been exercised with real Arabic/English
requests; see `evidence/local-ollama-smoke.json`. Hosted-provider integration is not implemented.

## Current recorded results

Results below summarize the scoped checks recorded in the evidence index, not the entire
acceptance specification:

| Gate | Status | Reason |
| --- | --- | --- |
| Held-out corpus structure/coverage | Passed | 72 held-out cases: 36 English, 36 Arabic, all 12 topics represented at least three times per locale; no model executed |
| Backend/frontend unit and integration suites | Passed | Retained JUnit and Python coverage reports |
| Integrated browser journey | Passed | Real upload → clean → metric → saved dashboard → report export in English and Arabic/mobile |
| Deterministic provider workflow | Passed | Typed plans, invalid-plan rejection, real deterministic tools, scoped history |
| Local Ollama smoke | Passed | qwen3.5:9b; bilingual all-history revenue queries returned the same governed value |
| Hosted model smoke | Not run | Hosted adapter is unimplemented |
| PostgreSQL adapter live smoke | Passed | Disposable local read-only source; not a real company's source |
| External company database and Odoo live smoke | Configuration-blocked | No authorized endpoint/credentials supplied; full connector workflow also remains incomplete |
| Representative performance profile | Not run | Dataset/resource/concurrency profile must be fixed first |

The authoritative mutable status is [`evidence/index.json`](evidence/index.json). Do not edit a
table here to contradict it; add an evidence record and update both when a run occurs.

## Visual and accessibility evaluation

Capture the actual integrated UI in English/LTR and Arabic/RTL, light/dark, at desktop, tablet, and
mobile widths. Inspect—not merely capture—onboarding, ingestion/profile/cleaning, dashboard evidence
and drill-down, assistant result, report edit/export, people/projects, process map, scenario, denied,
empty, stale, and error states. Record focus order/return, Escape behavior, keyboard chart/table
alternative, 200% zoom, contrast, overflow, Arabic shaping, print layout, and browser console errors.

## Performance profile

A performance record must name CPU/RAM/container limits, dataset rows/bytes/tables, concurrency,
cache state, model/provider, run count, warm-up, endpoint/journey, and tool/worker configuration.
Measure p50/p95 latency, throughput or completion time, peak memory, failure/timeout rate, and queue
backlog where relevant. `scripts/performance_smoke.py` proves only that the measurement harness can
sample an HTTP endpoint; it is not evidence of enterprise scale.
