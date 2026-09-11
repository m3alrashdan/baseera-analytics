# BASEERA design system

This document is the UI contract for BASEERA. It is deliberately calm, editorial, and evidence-led:
the dominant content is the business question and its proof, not decorative chrome. Token names are
normative; the frontend source is authoritative for the values currently wired into components.

## Principles

1. **Evidence is adjacent.** Every KPI, finding, chart, forecast, and recommendation exposes its
   definition, scope, freshness, warnings, and result lineage without leaving the task.
2. **Hierarchy reflects consequence.** One primary analytical view leads each screen; supporting
   cards do not compete at equal weight.
3. **State is explicit.** Loading, empty, partial, stale, denied, failed, cancelled, unsupported,
   not configured, and saved are visually and textually distinct.
4. **Bilingual by construction.** Logical properties, locale-aware formatting, and bidi isolation
   are primitives rather than post-processing.
5. **Density remains readable.** Tables and charts use progressive disclosure, meaningful grouping,
   and stable alignment at realistic lengths and values.

## Core tokens

Token values are starting contracts and may be tuned only with contrast and screenshot evidence.

| Family | Tokens |
| --- | --- |
| Light colors | `ink #142536`, `canvas #F5F7FA`, `surface #FFFFFF`, `surface-subtle #EDF2F4`, `teal #087F8C`, `teal-strong #066670`, `border #D7E0E5` |
| Dark colors | `ink #E9F0F3`, `canvas #0D171F`, `surface #13222D`, `surface-subtle #1A2C38`, `teal #45B8C1`, `border #304653` |
| Semantics | success `#18794E`, warning `#9A6700`, danger `#C33A3A`, info `#2563A6`, neutral `#667783`, forecast `#7657B5` |
| Comparison | current `teal`, previous `#75889A`, target `#C07A2D`; missing values use gaps plus labels, never a misleading zero |
| Space | `1=4`, `2=8`, `3=12`, `4=16`, `5=24`, `6=32`, `7=48`, `8=64` px |
| Radius | `sm=6`, `md=10`, `lg=16`, `pill=999` px; use `lg` sparingly on major surfaces |
| Type | body `16/1.55`, small `14/1.45`, label `12/1.35`, h3 `20/1.3`, h2 `28/1.2`, h1 `36/1.15` |
| Motion | fast `120ms`, normal `180ms`, deliberate `260ms`; standard easing `cubic-bezier(.2,.8,.2,1)` |
| Depth | border-first; shadow-sm `0 1px 2px rgb(20 37 54 / .08)`, shadow-md only for floating sheets/dialogs |
| Layers | base `0`, sticky `20`, popover `40`, sheet `60`, dialog `80`, toast `100` |

Use locally bundled Arabic and Latin fonts when their license files are included. Until that asset is
present, use a documented system fallback and do not claim that a particular font is bundled.
Numeric metric values use tabular figures. Do not force Arabic prose into a Latin font.

## Page composition

- Desktop uses a collapsible navigation rail, compact context bar, main content, and optional
  evidence/assistant rail. The main chart usually occupies about two-thirds of the analytical row.
- At tablet width, the side rail becomes a modal sheet with focus trapping and Escape dismissal.
- At mobile width, the summary precedes actions and evidence; wide tables scroll within a labeled
  region and retain the first identifying column where practical.
- Limit text measure to roughly 70 characters for narrative/report blocks. Dense data surfaces may
  use the full grid but keep readable column spacing.

Suggested breakpoints are content-driven: compact below `720px`, intermediate from `720–1099px`,
and full workspace at `1100px` and above. Verify actual components at 320, 768, 1024, and 1440 px.

## Reusable compositions

| Component | Required behavior |
| --- | --- |
| Page header | Title, company/period context, freshness, primary action; wraps without hiding context |
| KPI card | Value, unit, comparison, trend semantics, status label, definition/evidence action |
| Insight card | Fact/forecast/assumption/recommendation label, concise statement, evidence, next action |
| Filter bar | URL-persisted filters when appropriate, applied count, reset, keyboard-operable controls |
| Evidence rail | Result ID, definition version, dataset version, filters, freshness, lineage, warnings, access label |
| Data table | Semantic headers, sortable state announcement, pagination/virtualization, empty/error states |
| Chart panel | Title, unit, grain, legend, selection, reset, evidence, downloadable data and accessible table |
| Status badge | Icon/shape plus text; status is never encoded by color alone |
| Approval diff | Previous/proposed values, affected scope, consequences, actor, explicit accept/reject |
| Job progress | Persisted state and measured counts; cancel/retry/resume only when supported |
| Empty state | Explains why, preserves context, offers one real next action |

## Directionality and localization

- Set `lang` and `dir` at the document boundary. Components use `margin-inline`, `padding-inline`,
  `inset-inline`, and logical text alignment.
- Navigation and chevrons mirror in RTL only when they express spatial direction. Time axes remain
  chronologically increasing according to the chart library's locale behavior.
- Wrap IDs, email addresses, file names, formulas, and mixed currency codes in an element with
  `dir="ltr"` and `unicode-bidi: isolate`, or `<bdi>` when direction is content-derived.
- Store numbers and dates as typed values. Format with the active locale and the tenant timezone;
  include ISO/code forms in accessible detail where ambiguity matters.
- Arabic translations cover navigation, validation, tooltips, chart labels, empty/error states,
  evidence terms, exports, and generated templates. A missing translation is a test failure, not an
  excuse to reverse an English string.

## Accessibility contract

- Target WCAG 2.2 AA. Measure text/non-text contrast in both themes and all semantic states.
- All operations work by keyboard with a visible `:focus-visible` indicator at least 2 CSS pixels
  in perceived thickness and not obscured by sticky elements.
- Dialogs and sheets move focus to a meaningful heading/control, trap it while open, close on Escape,
  and return it to the opener. Status changes use appropriate polite/assertive live regions.
- Charts have concise alt summaries and an equivalent table or list. Selection and comparisons use
  labels, markers, or patterns in addition to hue.
- Touch targets aim for 44×44 CSS pixels; compact exceptions retain separation and an alternate
  accessible control.
- Honor `prefers-reduced-motion`; remove nonessential transforms and preserve state feedback.
- At 200% zoom, content reflows without two-dimensional page scrolling except intentional data
  regions. Test Arabic shaping and clipping in print/PDF output.

## State language

| State | Presentation rule |
| --- | --- |
| Loading | Skeleton or spinner with a task label; never invent progress |
| Empty | “No records in this scope” plus active scope and a valid next action |
| Partial | Amber/information treatment, coverage value, missing parts, and impact |
| Stale | Last successful refresh and what remains safe to interpret |
| Denied | No sensitive existence leak; explain required permission at the correct granularity |
| Failed | Stable error summary, correlation ID, retained input, and safe retry if supported |
| Unsupported | Name the unsupported format/action and supported alternatives |
| Not configured | Identify the administrator-controlled dependency without exposing secret names/values |
| Saved | Identify the new version/time; offer undo only when it creates an auditable version |

## Data visualization rules

Use line for ordered trends, bar for discrete comparison, stacked bar only for meaningful parts,
scatter for relationships, histogram/box plot for distributions, waterfall for additive variance,
and forecast bands for uncertainty. Axes show unit and grain; zero baselines are used where omission
would distort magnitude. Downsampling is labeled and exact totals remain available. Three-dimensional
views are lazy-loaded explorations with reset, selection, and an equivalent two-dimensional/table
view—never a perspective effect on ordinary bars.

## Visual QA gate

The evidence matrix requires actual inspected captures for English/LTR and Arabic/RTL, light/dark,
desktop/tablet/mobile, plus keyboard, zoom, print, chart-table, and console-error checks. A generated
screenshot is `captured`, not `approved`, until a reviewer records the inspection result in
[`evidence/README.md`](evidence/README.md).

