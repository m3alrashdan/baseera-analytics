# Governed metric contracts

BASEERA answers business questions through versioned metric definitions. The formulas below define
version `v1` of the deterministic demo semantics; a production tenant must approve its own mappings
and definitions. A missing required input produces an unavailable/partial result, never a fabricated
zero.

## Shared query context

Every result records:

```json
{
  "metricId": "net_revenue",
  "metricVersion": "v1",
  "datasetVersionIds": ["..."],
  "filters": {},
  "timeRange": {"start": "2026-06-01", "endExclusive": "2026-07-01"},
  "timeGrain": "month",
  "timezone": "Asia/Amman",
  "currency": "JOD",
  "asOf": "2026-06-30T23:59:59+03:00",
  "resultId": "...",
  "freshness": {},
  "warnings": []
}
```

Intervals are half-open `[start, end)` unless a definition explicitly states otherwise. Filter
values are typed and normalized before hashing. Identical tenant, permission revision, definition,
data versions, filters, timezone, currency, and cutoff must resolve to the same calculation across
chat, dashboard, report, and export.

## Version 1 definitions

### `net_revenue`

- **Meaning**: recognized sales net of discounts and returns in the selected period.
- **Formula**: `SUM(net_line_amount)` where
  `net_line_amount = signed_quantity * unit_price - signed_discount_amount`.
- **Sign rule**: returns use negative quantity; the discount reversal uses the same sign as gross
  line amount. A legitimate return remains negative and is never removed as an “invalid” value.
- **Time**: recognized/order-posted timestamp mapped into the reporting timezone.
- **Grain/dimensions**: day or coarser; customer, product/category, sales owner, department, channel.
- **Unit**: source currency or approved converted currency. Mixed unconverted currencies are denied.
- **Missing policy**: a missing price/quantity makes the affected amount unavailable and reports
  coverage; do not coalesce to zero.

### `order_count`

- **Meaning**: distinct non-cancelled source orders with activity in the period.
- **Formula**: `COUNT(DISTINCT (source_namespace, order_id))` after approved duplicate-batch
  reconciliation.
- **Time**: order-posted timestamp. Return lines do not create new orders unless their source has a
  distinct return order ID and the tenant definition includes it.
- **Unit**: orders; zero is valid only when source coverage for the entire period is confirmed.

### `gross_margin`

- **Meaning**: net revenue less attributable cost of goods sold.
- **Formula**: `SUM(net_line_amount - signed_quantity * unit_cost)`.
- **Sign rule**: return quantity reverses both recognized revenue and attributable cost.
- **Unit**: currency. Margin percentage, when requested, is `gross_margin / net_revenue` and is
  unavailable when net revenue is zero.
- **Missing policy**: default result is unavailable if any in-scope revenue line lacks a required
  cost. A separately labeled partial estimate may be emitted only with cost coverage and no claim of
  full margin.

### `support_case_count`

- **Meaning**: distinct cases created in the selected period.
- **Formula**: `COUNT(DISTINCT (source_namespace, case_id))`.
- **Dimensions**: department/team, priority, channel, customer, product, status.
- **Privacy**: small-group and protected-customer rules apply before drill-down.

### `avg_resolution_hours`

- **Meaning**: mean elapsed resolution time for cases resolved in the period.
- **Formula**: `AVG(resolved_at - created_at)` in elapsed hours for valid, non-negative intervals.
- **Population**: cases whose `resolved_at` falls in the period; open cases are excluded and their
  count is reported. Invalid intervals are quarantined, not clamped to zero.
- **Caveat**: this is elapsed time, not business hours, unless a later approved definition supplies a
  calendar.

### `budget_variance`

- **Meaning**: actual recognized spend minus approved budget for matching period/scope.
- **Formula**: `SUM(actual_amount) - SUM(approved_budget_amount)` after approved department/project
  mappings.
- **Direction**: positive is over budget (unfavorable); negative is under budget. UI labels the
  direction and does not depend on color alone.
- **Missing policy**: missing either side is unavailable. Unapproved commitments are not actuals and
  may be shown as a separate scenario.

### `project_delay_rate`

- **Meaning**: share of eligible projects with at least one late milestone at the reporting cutoff.
- **Numerator**: distinct eligible projects where a non-cancelled milestone finished after its
  planned finish or remained open after that date.
- **Denominator**: distinct projects with at least one non-cancelled milestone planned to finish in
  the selected period.
- **Formula**: `late_project_count / eligible_project_count`.
- **Zero denominator**: unavailable with `reason=empty_denominator`, not `0%`.

### `utilization_rate`

- **Meaning**: scheduled productive effort relative to available capacity for the selected scope.
- **Numerator**: approved/scheduled assignment hours in the period, after overlap reconciliation.
- **Denominator**: contractual capacity minus approved leave/closure hours, never below zero.
- **Formula**: `scheduled_hours / available_hours`.
- **Zero denominator**: unavailable. Values above 100% are preserved and labeled overload rather
  than capped.
- **Use limitation**: workload planning signal, not an employee performance score. Individual views
  require authorized scope; public/manager aggregates use disclosure thresholds.

## Calendar and comparison rules

- “This month” means the calendar month containing the tenant's reporting cutoff, not the machine's
  current date. The fictional demo cutoff is 2026-06-30 in `Asia/Amman`.
- Previous-period comparison uses the immediately preceding interval of the same calendar semantics;
  year-over-year uses the corresponding local calendar interval.
- Percentage change is `(current - comparison) / ABS(comparison)`. A zero comparison yields an
  unavailable percentage plus both absolute values.
- Weeks require an explicit tenant week start. Fiscal periods require an approved fiscal calendar.
- “Today” and relative dates are resolved once at request start and recorded in the result.

## Currency conversion

No implicit conversion occurs. An approved conversion records source rate provider, rate version,
rate date/time, quote direction, rounding mode, and target currency. Convert at the transaction
policy date before aggregation unless the approved definition requires period-average or closing
rates. Displayed rounding never changes stored reconciliation totals.

## Join and aggregation safety

- The semantic layer validates approved joins and expected cardinality before execution.
- A many-side join that can duplicate a measure requires pre-aggregation or an approved allocation.
- Additive measures may sum over declared dimensions; semi-additive stock values require a snapshot
  rule; ratios recompute numerator and denominator rather than averaging displayed percentages.
- Distinct counts carry their identity tuple and cannot be added across overlapping groups.

## Evidence and reconciliation

Every metric result links its definition/version, source dataset versions, normalized filters,
authorized dimensions, query fingerprint, generated time, freshness, coverage, warnings, and result
ID. Cleaning reconciliation records row counts and control totals before, rejected, transformed, and
after. The key identity is preserved as text, including leading zeros.

Golden values for the fictional demo are produced from independently defined fixture assertions and
recorded with the evaluation evidence. They must not be copied from dashboard JSON. Until those
commands run, no numeric result in documentation is described as verified.

