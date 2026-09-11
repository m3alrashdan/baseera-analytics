# BASEERA — Complete Codex Implementation Prompt

Read this entire specification, preserve it as `PROJECT_SPEC.md` in the project, and implement the product described below. The working product name is **BASEERA | بصيرة**; keep branding configurable. Treat this as an implementation assignment with explicit acceptance criteria.

## 1. Mission and delivery standard

Build a complete, coherent AI enterprise analytics and decision-support platform from scratch. It connects to company data, understands approved business definitions, profiles and cleans data, performs reproducible analysis, builds interactive dashboards, generates editable reports, forecasts operational outcomes, and supports evidence-based management decisions through an Arabic/English AI assistant.

The platform covers the company as a whole: customers, sales, employees, teams, HR operations, projects, internal processes, costs, budgets, suppliers, inventory, support, and strategic objectives. CRM is one module within the wider product.

The frontend is a first-class deliverable. It must feel like a carefully designed executive product: clear, attractive, responsive, calm, interactive, and trustworthy. A manager should understand the current situation, identify an issue, inspect its evidence, and compare a practical response without understanding SQL, model names, or software architecture.

The ambition is to automate up to 95% of suitable repetitive analysis work. This is an evaluation objective, not a claimed accuracy rate or a promise to replace every expert judgment. Measure verified task completion, corrections, abstentions, escalations, runtime, and cost. Always distinguish observed facts, forecasts, assumptions, hypotheses, and recommendations.

Implement working software with real backend calculations and persistent state. A visual prototype, static chart collection, generic admin template, or chatbot around uploaded text is insufficient. Do not present invented metrics, fabricated citations, simulated tool activity, or unexecuted model results as real.

## 2. How to execute this assignment

- Inspect the actual repository, available tools, runtime, and applicable instructions before editing. Preserve existing work and adapt this specification to established conventions if the project is not empty.
- Follow higher-priority environment instructions, access controls, and existing authorization boundaries. This prompt does not authorize bypassing them.
- Make sensible reversible implementation decisions and record important assumptions. Ask only when missing information genuinely blocks safe progress, such as unavailable credentials or a material business definition that cannot be inferred.
- Begin implementing after a concise plan. Do not stop after scaffolding, architecture documents, a landing page, or the first successful demo screen.
- Work through the milestones in Section 28. These are implementation stages within one assignment, not permission to silently drop later requirements.
- Use maintained, compatible dependencies. Verify current APIs and licenses using official documentation; pin the actual versions used and generate lockfiles. Do not install every framework mentioned merely to include its name.
- Prefer a modular monolith and a small number of workers over premature microservices. Use one coherent implementation for each responsibility.
- Use available coding, testing, and preview capabilities. If a required capability is unavailable, record the exact unverified gate and continue with independent work. Never report a test as passed unless it ran.
- Do not acquire paid infrastructure, publish a public deployment, send external communications, or mutate a connected company's source systems without the authorization required in the actual environment.
- Preserve progress in `IMPLEMENTATION_STATUS.md`: completed requirements, evidence, current failures, environment blockers, next concrete actions. Resume from it across context limits.

## 3. Core product journeys

Deliver these complete journeys through the real interface and backend:

1. **Import to executive insight:** upload a multi-sheet workbook, inspect its structure, generate a before-cleaning profile, preview a cleaning plan, apply approved rules to a new version, compare before/after results, build analysis, and save a dashboard and report.
2. **Connected company:** connect a read-only database, map business entities, synchronize incremental changes, detect source schema changes, and refresh permitted dashboards with visible freshness.
3. **Conversational analysis:** ask an English or Arabic question, resolve its meaning and scope, execute authorized calculations, show evidence-backed findings and charts, and refine the result through follow-up questions.
4. **Company operations:** compare department workload, project progress, support demand, supplier dependencies, and budget consumption using compatible definitions and time periods.
5. **Forecast to action:** forecast workload, compare against a baseline, inspect uncertainty, propose a constrained resource plan, and save a reviewed decision with an owner and follow-up metric.
6. **Report editing:** request changes in scope, language, filters, narrative, or visualization; preview the changes, recalculate affected values, save a new version, and export the result.
7. **Failure recovery:** show meaningful states for missing data, ambiguous requests, denied access, stale sources, failed tools, interrupted jobs, unavailable models, and unsupported formats.

## 4. Frontend visual direction — highest design priority

Create an original enterprise analytics interface with strong information hierarchy and excellent typography. Its visual quality must remain high on real dense data, empty workspaces, error screens, and mobile devices.

### Brand and design system

- Use a restrained palette: deep navy or ink for navigation and primary text, warm off-white surfaces, teal for primary actions, and a limited secondary accent for comparisons. Define semantic success, warning, error, neutral, and forecast colors.
- A reasonable starting palette is ink `#142536`, canvas `#F5F7FA`, surface `#FFFFFF`, and teal `#087F8C`. Adjust shades to meet measured contrast requirements.
- Build tokens for colors, spacing, type, radii, shadows, borders, motion, z-index, and chart series. Use consistent 4/8-based spacing, readable body text, tabular numerals for metrics, and restrained depth.
- Use a licensed, locally bundled Arabic font such as IBM Plex Sans Arabic or Noto Sans Arabic and a compatible Latin font. Verify availability and licensing; avoid runtime dependence on external font delivery.
- Default to a polished light theme; implement a complete dark theme with deliberate chart palettes and readable disabled states.
- Create reusable primitives and compositions: page header, KPI card, insight card, filter bar, evidence drawer, empty state, data table, chart panel, status badge, approval diff, timeline, and job-progress panel.
- Avoid excessive gradients, glass effects, neon colors, oversized decorative cards, unrelated stock imagery, and ornamental 3D objects. Use motion to communicate state changes, not distract from information.

### Layout and navigation

- Desktop: collapsible sidebar, compact top context bar, main workspace, and an optional assistant/evidence side panel. Keep the selected company, date range, comparison period, timezone, and refresh status understandable.
- Use a flexible grid with one dominant analytical view and supporting panels. Do not give every widget equal visual weight.
- Keep a manager's primary actions visible: ask a question, inspect a metric, filter, save, compare, and export. Put administrative configuration behind role-appropriate navigation.
- Preserve filters in URLs when appropriate and saved views in persistent state. Browser back/forward and deep links must behave correctly.
- Support quick navigation, keyboard shortcuts where discoverable, and contextual actions. Do not require users to know command names to operate the product.
- On tablets and phones, turn side panels into accessible sheets, prioritize a readable summary, allow intentional table scrolling, and provide an accessible alternative for wide charts or graphs.

### Signature screen compositions

- **Executive home:** a compact company/period header; a short editable executive brief; four to six relevant KPI cards; a large primary trend/comparison area occupying roughly two-thirds of the next row; an attention panel beside it; and a lower section for department/project detail and reviewed actions. Adapt this composition to actual data rather than reserving large empty spaces.
- **Analytical investigation:** preserve a dominant chart/table canvas with a narrow contextual assistant. Selecting a point opens its breakdown and evidence without losing the question or filters. Users can pin a verified finding into a dashboard or report in one clear action.
- **Cleaning review:** put the issue list, transformation preview, and affected-row details in a focused workspace. Keep the apply action tied to a visible change summary and dataset version; retain the original profile for comparison.
- **Project/people detail:** use a readable identity/context header, a few meaningful indicators, timeline/workload evidence, and relevant related records. Avoid turning an employee profile into a leaderboard or a decorative scorecard.
- **Report composition:** use a clean document canvas with a section navigator and optional assistant. Clearly distinguish editable narrative from linked metric/chart blocks. Provide a readable before/after preview for a proposed change.
- **Scenario comparison:** show current and proposed assumptions alongside a shared comparison chart, resource implications, uncertainty, and an explicit “Save scenario” action. Keep sliders labeled with units and valid ranges and provide numerical inputs for precision.

Use realistic long names, large values, negative changes, missing data, and Arabic paragraphs during design. Ensure the product still looks deliberate under these conditions. Review the executive screen as a manager would: identify an issue, find its evidence, and locate a next action without guidance.

### Arabic, English, and accessibility

- Implement genuine internationalization. Arabic uses RTL; English uses LTR. Use logical CSS properties and correct bidirectional isolation for IDs, emails, formulas, currencies, and code.
- Translate navigation, tooltips, errors, validation, empty states, chart labels, report templates, and generated summaries. Do not mirror text or reverse chronological meaning mechanically.
- Store numeric values separately from formatting. Localize dates, number separators, currencies, and labels consistently. Support JOD and SAR as examples without assuming every company uses them.
- Aim for WCAG 2.2 AA: measured contrast, keyboard operation, visible focus, appropriate semantics, focus management, dialog escape behavior, reduced motion, and text alternatives for data graphics.
- Never rely on color alone. Provide meaningful labels, patterns, markers, or a corresponding table. Keep dense interfaces readable at browser zoom.

### Interaction quality

- Implement deliberate loading, empty, partial-data, stale-data, permission-denied, error, retry, and success states on every route.
- Show actual job progress and concise action descriptions. Do not fabricate percentages, streaming events, or private model reasoning.
- Offer cancel, retry, and resume when supported. Prevent accidental duplicate submissions and show whether a change has been saved.
- Include undo/version recovery for supported report, dashboard, and cleaning operations. Use explicit review for changes with meaningful business consequences.
- Validate inputs near their fields, preserve user input after errors, and provide actionable messages instead of stack traces.

## 5. Information architecture and screen requirements

Organize navigation into sensible groups such as Overview, Explore, Company, and Manage. The following screens are required, but may share reusable layouts and drill-downs instead of becoming disconnected applications.

### A. Executive overview

- Show a short executive brief answering what changed, what needs attention, and which action is worth reviewing.
- Present a small set of role-relevant KPIs with current value, unit, comparison, trend, definition, and source freshness.
- Show a primary trend chart, department or project comparison, important exceptions, and a decision/action list.
- Every metric must open its definition, filters, provenance, and permitted details. Explain unavailable metrics rather than displaying zero.
- A request such as “Show project delays and support pressure this month” must open or generate the relevant real analysis.
- Do not invent a universal company health score. If a composite index is added, show its weights, missing components, and approved definition.

### B. Data sources and onboarding

- Provide “Upload files,” “Connect database,” and “Connect application” paths with only genuinely implemented connectors shown as available.
- Show supported capabilities before connection, validate credentials securely, preview schemas and mappings, configure sync, and show connection health.
- Include a guided first-run path: company context, reporting timezone/currency, data connection, semantic mapping, validation, and first dashboard.
- Offer a clearly marked fictional demo workspace and a separate empty workspace. Do not mix demo data into connected company data.

### C. Data explorer and catalog

- Search datasets, tables, columns, descriptions, owners, classifications, and business terms.
- Provide a virtualized or paginated table, column profiles, relationship suggestions, lineage, and version history.
- Make selected-sheet, selected-range, preview, sample, and full-dataset scopes visible.
- Display row counts, rejected records, partition coverage, and last successful refresh.

### D. Data quality and cleaning studio

- Use a coherent journey: original profile, proposed changes, preview, apply, validation, and before/after report.
- Show each issue with count, affected fields, examples, severity, recommended treatment, and rationale.
- Preview transformations with concrete differences and effects on key totals. Support accept, edit, reject, save recipe, and rerun.
- Allow users to inspect retained exceptions and unresolved issues. A green status must correspond to real checks.
- Show original and cleaned versions side by side, with lineage and rollback to an earlier published version.

### E. Analysis workspace and dashboard builder

- Support selecting a metric, dimensions, filters, time grain, comparison, and chart type through both controls and chat.
- Allow resize/reorder, widget duplication/removal, save, personal/team views, and version history with permissions.
- The assistant proposes typed dashboard changes, shows a preview, and persists accepted changes. A prose claim that the dashboard was updated is insufficient.
- Support cross-filtering and drill-down where the underlying data permits it. Show active filters and an obvious reset action.

### F. AI consultant

- Use a dedicated conversation page and an optional contextual drawer beside dashboards and reports.
- Show the dataset or module in scope, current filters, concise execution status, answer, supporting charts, and evidence links.
- Render rich results: tables, KPI cards, chart previews, forecast panels, source citations, recommended actions, and report/dashboard change previews.
- Support interruption, cancellation, follow-up questions, conversation history, and pinned results.
- Ask a focused clarification when an ambiguity materially changes the answer. Show actionable requests for missing data.
- Keep SQL, model metadata, and diagnostic traces in an authorized technical disclosure, not the manager's default view.

### G. Company modules

- **Customers and sales:** customer overview, opportunity pipeline, activities, sales trends, returns, margin when costs exist, and customer segments.
- **People and teams:** organization view, role context, approved skills, workload/capacity, goals, leave coverage, training needs, and aggregate HR trends.
- **Projects:** portfolio view, milestones, task board, dependency/timeline view, planned versus actual effort and budget, and delay risks.
- **Operations:** process map, waiting versus processing time, rework, bottlenecks, and selected event traces.
- **Costs and budgets:** actual versus budget, expense categories, commitments where available, recurring spend, and explained variances.
- **Support and suppliers:** demand, response/resolution time, reopened cases, supplier delivery performance, and affected downstream projects.
- **Objectives:** department-level goals, approved KPI linkage, owners, review dates, progress, and explicit missing evidence.

### H. Forecasts and scenario lab

- Show historical observations and forecasts with distinct visual styles, backtest results, horizon, uncertainty, and model availability.
- Provide baseline/current/proposed scenario comparison, editable assumptions, capacity or budget constraints, and a clear reset.
- Distinguish a calculated scenario from an observed outcome or a causal estimate.
- Include a resource schedule preview, constraint violations, and infeasibility explanations. Do not force a plausible-looking plan if constraints cannot be satisfied.

### I. Reports and decision center

- Provide an executive report editor with sections, linked metrics, evidence, charts, comments, version comparison, and chat editing.
- Provide a decision log with problem, evidence, options, chosen action, owner, review date, and expected versus observed result.
- Provide an approval inbox for material transformations and permitted operational actions, with a concrete diff and consequence summary.

### J. Administration

- Manage users, roles, department scopes, data permissions, connectors, model providers, resource limits, approved business definitions, retention, audit events, and in-app schedules.
- Show feature availability honestly: ready, needs configuration, unsupported, or temporarily unavailable. Never use “connected” for an untested credential form.

## 6. Charting, 3D, maps, and visual evidence

- Implement appropriate line, bar, stacked bar, scatter, histogram, box plot, heatmap, waterfall, and forecast interval charts. Use treemaps, funnels, Sankey diagrams, timelines, process maps, and relationship graphs when the data semantics support them.
- Choose chart types through validated rules plus user intent. Label axes, units, date grain, source, and aggregation clearly.
- Use honest scales, consistent category colors, sensible tick density, and explicit handling of missing values and zero denominators.
- Use geographic maps only when relevant locations and permitted geospatial data exist.
- Provide at least one functional 3D exploration, such as a three-variable scatterplot or dependency view, with hover details, filtering, selection, reset, and an accessible 2D/table alternative.
- Use 3D selectively and lazy-load it. Do not use 3D bars or perspective effects that distort ordinary comparisons.
- For large data, aggregate or downsample deliberately and label the method. Keep exact underlying totals available; never imply every point is displayed if it is not.
- Produce charts from validated specifications referencing authorized result sets. Do not execute arbitrary model-generated JavaScript, HTML, SQL, or remote URLs in chart specifications.
- Support chart export and report rendering without clipped labels, broken Arabic shaping, or missing legends.

## 7. Business meaning and metric contracts

Implement a versioned semantic layer before allowing unrestricted business questions.

Each approved metric needs: stable ID, display names, description, owner, formula or safe query definition, source lineage, grain, dimensions, join paths, unit, currency behavior, timezone, period rules, exclusions, permissions, and definition version.

- Distinguish orders, invoiced revenue, collected cash, refunds, gross margin, and profit. Do not compute profit without the required cost information.
- Define customer, employee, department, project, order, task, and supplier IDs explicitly. Names are not unique identifiers.
- Validate relationship cardinality and prevent join fan-out from multiplying totals. Keep distinct-count and additive/semi-additive metric rules explicit.
- Separate stocks from flows: month-end headcount is not the sum of daily headcount, and inventory balance is not the sum of historical balances.
- Model effective dates for employee assignments, organizational changes, prices, and business definitions so historical reports remain reproducible.
- Configure fiscal calendar, reporting timezone, week start, currency precision, taxes, and exchange-rate source/date. Preserve original currencies and explain conversions.
- Resolve ambiguous business terms through approved definitions or focused clarification. Proposed definitions remain drafts until authorized approval.
- The chat, dashboard, exports, and scheduled reports must request the same metric definitions and produce the same values for the same scope and data version.

## 8. Ingestion, synchronization, and real data coverage

Implement a connector capability contract: authentication, discovery, preview, full/incremental read, pagination, checkpoint, schema mapping, health, and any explicitly permitted writes.

### File ingestion

- Implement CSV, TSV, XLSX, JSON/JSONL, and Parquet readers. Provide a separate legacy XLS reader if the supported library can safely handle it; otherwise report the exact limitation and conversion path.
- For Excel, discover sheets and tables, merged headers, blank rows, multiple header lines, formulas versus cached values, selected ranges, hidden sheets, and locale-sensitive values. Make extraction scope explicit.
- Detect potentially stale or absent formula results. Never claim to recalculate a workbook when only cached values were read. Do not execute workbook macros or external links.
- Handle encoding, delimiters, decimal conventions, leading-zero IDs, nested JSON, null markers, long text, duplicate column names, and mixed types.
- Retain original row/sheet/page locations where possible. Reject malformed records into a visible error ledger rather than silently dropping them.
- Include document/table extraction for PDF and images using a maintained parser and OCR/layout tooling such as Docling when appropriate. Treat extraction as a separate uncertain stage with provenance and review. Document Arabic OCR limitations found during evaluation.
- Never treat “any file” as a promise of universal support. Validate formats, file sizes, decompression limits, encrypted-file states, and parse failures.

### Databases and company systems

- Implement PostgreSQL as the first full read-only connector, followed by MySQL and SQL Server adapters with real integration tests where available.
- Implement a bounded configurable REST ingestion connector with approved endpoints, pagination, rate limits, retries, and secrets handling.
- Deliver one concrete company-system adapter, preferably Odoo if compatible with the target environment. Verify its current API and licensing conditions rather than assuming a particular RPC interface.
- Google Sheets, other CRM/ERP systems, and additional databases must use the same connector contract. Do not expose unimplemented adapters as working integrations.
- Prefer approved replicas, extracts, or bounded source queries to avoid overloading transactional databases. Credentials must enforce the intended database permissions independently of the agent.
- Support scheduled incremental synchronization using reliable cursors/watermarks, overlap handling, deduplication, idempotent upserts, and checkpoint recovery. Support deletions only through an explicit source capability.
- Make refresh frequency and observed lag visible. Use CDC/webhooks only for connectors that actually support them; do not label periodic polling as instantaneous real time.
- Detect schema drift and block unsafe mappings while preserving the last valid published snapshot. Reconcile counts and key control totals after ingestion.

### Processing coverage

The analytical engine must process the full authorized scope for final calculations. Sampling is acceptable for labeled previews or explicitly approximate analysis. Record rows discovered, parsed, accepted, rejected, sampled, and analyzed. Large inputs should stream or partition instead of being loaded blindly into model context or RAM.

## 9. Profiling and reversible cleaning

Produce a persisted original-data profile with dataset scope, row/column counts, date coverage, inferred types, nulls, duplicates, validity rules, distributions, suspected outliers, referential integrity, unit/currency issues, and suitability for requested analyses.

Implement a typed cleaning recipe. Each step contains its rule, selected columns, rationale, affected-row estimate, preview, assumptions, review requirement, and postconditions.

- Normalize harmless formatting through approved rules. Preserve leading zeros and distinguish identity fields from numeric measures.
- Resolve dates and number conventions explicitly; do not guess ambiguous dates silently.
- Determine duplicates using business keys and provenance. Repeated amounts or matching names do not prove duplication.
- Distinguish missing, unknown, not applicable, and zero. Do not fabricate missing financial facts or automatically mean-impute every numeric column.
- Investigate negative values as possible returns/adjustments and extreme values as possible legitimate events.
- For uncertain entity matches, provide candidates and supporting evidence instead of automatically merging identities.
- Keep analytical cleaning separate from model-specific preprocessing. Fit imputers, scalers, encoders, selectors, and learned cleaning components using training data only inside each evaluation split.
- Preserve immutable raw files and snapshots. Apply changes to a new version, retain an operation ledger, and support re-execution and rollback of publication pointers.
- Generate a before/after summary and a cleaning-method report explaining changed values, excluded/quarantined rows, unresolved issues, reconciled totals, and effects on downstream analysis.
- Do not claim quality improved merely because missingness decreased. Any quality score must expose its component rules and weights.

## 10. Analytical engine and professional reasoning behavior

Use SQL, dataframe operations, and statistical tools to calculate results. The LLM selects tools, resolves intent, proposes a plan, explains verified outputs, and requests missing context.

Implement descriptive analysis, comparisons, cohort/segment analysis, distributions, concentration, budget variance, trend decomposition, contribution analysis, anomaly candidates, and appropriate statistical tests. Choose a method based on the question, data types, sample size, and assumptions.

- Distinguish percentage change from percentage-point change; handle zero and negative baselines explicitly.
- Report uncertainty, small samples, incomplete periods, seasonality, and multiple-testing concerns where relevant.
- Separate association from causation. A contribution calculation can locate a decline without proving why it occurred.
- Do not produce conclusions from an unauthorized or conveniently selected subset while implying company-wide coverage.
- Each significant finding must reference a reproducible result, metric definition, time/filter scope, data version, and relevant limitation.
- When data cannot support a conclusion, explain what can be answered and which additional data would resolve the gap.

## 11. Company-wide modules and people analytics

Use a shared organizational model and semantic layer so findings can connect departments, projects, customers, suppliers, costs, and tasks.

### Customers, sales, and CRM

Implement customer and contact records, opportunity stages, internal activities, follow-up tasks, order/invoice references, segments, and customer history. Support authorized local create/update operations and explicit ownership of records imported from external systems. Track sync conflicts; do not silently overwrite the external source of record.

Calculate revenue, conversion, retention, returns, and margin only when the relevant definitions and data exist. Segmentation should describe observed business behavior without inventing sensitive personal traits.

### People, teams, and HR operations

- Model departments, roles, effective-dated assignments, approved skills, availability, leave coverage, project allocation, goals, and training records.
- Support aggregate headcount, hiring lead time, vacancy coverage, training completion, team capacity, workload distribution, and retention trends.
- Show individual work context only to authorized viewers. Compare work in context: role, complexity, quality, dependencies, available hours, and support work matter.
- Do not equate task count, online time, keyboard activity, messages, or attendance alone with productivity.
- Do not infer health, emotions, personality, protected attributes, or intent to resign from private communications. Do not create hidden surveillance, employee “worth” rankings, or automatic disciplinary decisions.
- Keep compensation and other restricted fields separately protected. Aggregate reporting needs minimum cohort sizes and protection against disclosure through repeated filtering or subtraction.
- Support record correction and review. Employment-impacting judgments remain human decisions with documented evidence; the system can organize relevant information and propose questions for review.
- Training recommendations should use approved role requirements and verified skill gaps. Do not assign deficits merely from an LLM impression.

### Projects, support, suppliers, budgets, and strategy

- Track task dependencies, milestones, actual/planned work, budget changes, commitments where available, and documented blockers.
- Calculate waiting time, resolution time, and SLA results using the correct business calendar and policy version.
- Keep invoicing, expense recognition, cash movement, and commitments distinct; avoid double counting.
- Use supplier lead times and project dependencies to identify potential downstream exposure.
- Connect objectives to approved KPIs, owners, targets, and review dates. Do not invent causal links between an employee's activity and company revenue.

## 12. Agent orchestration and model strategy

Implement a stateful workflow with explicit routing and termination rules. Functional roles may share a model and run as graph nodes; do not create separate autonomous agents or services for every label by default.

Required responsibilities:

| Responsibility | Required behavior |
| --- | --- |
| Request coordinator | Resolve intent, authorized scope, necessary clarification, plan, budget, and output format. |
| Data understanding | Discover schemas, inspect profiles, propose mappings, identify missing inputs. |
| Data quality | Generate typed cleaning plans, preview, apply permitted steps, validate results. |
| Analyst | Request approved metrics and run bounded analytical tools. |
| Forecasting | Validate eligibility, train/evaluate candidates, return tested predictions. |
| Operations and resources | Analyze event logs, dependencies, and constrained scheduling problems. |
| Reporting | Produce narratives and typed dashboard/report changes from verified results. |
| Verification | Check claims, units, filters, lineage, consistency, and unresolved limitations. |

Use LangGraph or a justified equivalent for explicit state, checkpoints, streaming, clarification, review, retries, and resumption. Isolate deterministic computation from LLM interpretation. Build idempotency for side effects because a resumed or retried step may execute more than once.

Use a configurable LLM provider interface supporting a local deployment such as Ollama and an authorized hosted provider. Select actual model IDs through configuration and evaluate them on this product's English/Arabic tasks. Do not hard-code an assumed “best” model, silently download huge weights, or require a paid key for deterministic functions.

Route inexpensive tasks to an appropriate smaller model when quality is sufficient. Reserve more capable models for complex planning where tests justify their cost. Model routing is an optimization, not a reason to lower validation standards.

Memory must be tenant-scoped and access-controlled. Separate conversation context, user presentation preferences, proposed business knowledge, and approved definitions. Store provenance, version, effective date, expiry where applicable, and an explicit correction mechanism. Do not automatically train on private company data or treat prior generated answers as verified truth.

If model access is absent, preserve real ingestion, profiling, SQL metrics, dashboards, and supported statistical tools. Show that conversational AI is unavailable and provide configuration guidance. Never use canned answers as an undisclosed replacement for a model.

## 13. Typed tools, execution, and evidence contracts

Expose a small, explicit tool registry, for example:

`list_sources`, `inspect_schema`, `profile_dataset`, `preview_cleaning`, `apply_cleaning_recipe`, `query_metric`, `run_analysis`, `search_documents`, `query_relationships`, `train_forecast`, `run_backtest`, `analyze_process`, `optimize_resources`, `simulate_scenario`, `create_chart`, `propose_dashboard_patch`, `propose_report_patch`, and `create_action_draft`.

Validate tool inputs with typed schemas. Resolve permissions server-side for every call. The agent must not choose its own tenant, role, filesystem scope, or authorization context.

Use structured outputs for analysis requests, tool results, chart specifications, findings, recommendations, and change proposals. At minimum:

- **Analysis request:** question, dataset versions, approved metric IDs, dimensions, filters, period, timezone, requested output.
- **Result:** run/result ID, status, row coverage, values/table schema, units, provenance, warnings, and reproducibility metadata.
- **Finding:** claim, linked evidence IDs, fact/forecast/hypothesis classification, assumptions, and limitations.
- **Recommendation:** proposed action, evidence, expected benefit or explicit uncertainty, prerequisites, owner suggestion, and review requirement.
- **Change proposal:** target artifact/version, typed operations, preview, affected dependencies, and expected current version.

Prefer parameterized metric queries and prebuilt analytical functions. For advanced SQL, validate dialect and AST, enforce approved schemas/tables/functions, read-only execution, query cost/timeout/row limits, and database-side permissions. Checking that text begins with SELECT is insufficient; read-only syntax can still invoke unsafe functions or expose disallowed data.

If arbitrary Python analysis is supported, run it in an isolated worker with no company credentials, no host mount or Docker socket, no default network, controlled packages, non-root execution, and time/CPU/memory/output limits. Give it only the authorized dataset snapshot and a scoped output directory. A Python `exec` call inside the API process is not a sandbox. If isolation cannot be provided, disable arbitrary code and use vetted tools.

For evidence, retain input versions, transformation lineage, metric/query reference, result checksum or stable ID, filters, period, execution timestamp, model/prompt version where relevant, and document locations. Expose useful provenance without exposing secrets or unauthorized rows.

## 14. RAG, document understanding, and enterprise relationships

- Implement document ingestion with layout-aware extraction, chunk provenance, document version, page/section references, and access metadata.
- Use hybrid lexical/vector retrieval and reranking only where measured improvements justify it. Evaluate Arabic, English, mixed-language terms, and business abbreviations.
- Apply access restrictions before retrieval/ranking and when resolving citations. Recheck permissions when opening a source or downloading an artifact.
- Use documents for policies, definitions, contracts, procedures, and explanatory context. Use governed queries for numerical aggregation across structured data.
- A table-aware retrieval path may select relevant schemas/tables/columns, but it must not substitute a few retrieved rows for complete aggregation.
- Build an enterprise relationship graph linking departments, roles, employees, projects, tasks, customers, suppliers, documents, and policies. Use canonical IDs and effective-dated, sourced edges.
- Implement graph-supported retrieval (GraphRAG) and dependency exploration with bounded traversal. Use PostgreSQL adjacency structures initially or Neo4j when traversal requirements justify a separate graph engine; record the choice.
- Show uncertain extracted relationships as candidates. Do not treat a relationship graph as a proven causal graph.
- Integrations through MCP may be added when they simplify access to approved tools. MCP is a connection protocol, not a substitute for tool validation, authorization, or evidence.
- Treat retrieved documents, table cells, comments, and external tool text as untrusted content. Instructions embedded in them must not override application policy or trigger actions.

## 15. Predictive modeling and modern foundation models

Implement actual data eligibility checks, training/evaluation runs, model artifacts, and prediction endpoints. Require a defined target, observation unit, prediction horizon where relevant, leakage controls, and enough representative history.

### Tabular tasks

- Implement a practical baseline and a strong tabular candidate such as gradient boosting for supported classification/regression tasks.
- Provide a real optional TabPFN adapter when its current license, data limits, and compute requirements fit. Benchmark it instead of assuming a foundation model wins.
- Examples include project delay, transaction processing duration, support case reopening, customer churn with an approved definition, and estimated workload. Keep employee-level high-impact profiling out of default predictive tasks.
- Use group-aware and time-aware splits where records from the same entity or future periods would leak. Keep feature engineering and preprocessing inside the split.
- Report suitable metrics, class balance, threshold tradeoffs, calibration where probabilities are shown, and subgroup performance where appropriate and permitted.

### Time-series tasks

- Implement naive/seasonal-naive baselines and a suitable statistical model. Add a real configurable Chronos-family adapter, including Chronos-2 where supported and appropriate.
- Forecast sales, support demand, project workload, or operational volume using well-defined series and horizons.
- Use rolling-origin backtests and preserve temporal order. Future covariates must be known at forecast time or be explicitly forecast/scenario inputs.
- Report horizon-specific errors and suitable metrics such as MAE, MASE, WAPE, and interval coverage, with safeguards for undefined denominators and intermittent series.
- Show prediction intervals only when the method generates them and evaluation supports their interpretation. Conformal calibration is an optional method when its assumptions and evaluation design are appropriate; it is not universal coverage under drift.
- Reject or narrow forecasts when history, granularity, data freshness, or validation is inadequate. Retain the baseline if a complex model does not improve validated performance.

Track dataset version, feature set, split definition, seed, model/provider version, evaluation metrics, status, and artifact location for each run. Feature explanations such as SHAP describe model behavior, not proven real-world causes.

Keep heavier model dependencies in optional execution profiles. A configuration screen or an uncalled import is not a completed model integration. Mark adapters as implemented, tested, unavailable, or awaiting credentials/weights accurately.

## 16. Process mining, optimization, causal analysis, and simulation

### Process intelligence

Implement an event-log schema with stable event ID, activity, timestamp, lifecycle state where available, source, and related object IDs. Use pseudonymous resource references unless individual visibility is authorized.

Support simple case-based analysis and one meaningful object-centric workflow connecting orders, invoices, deliveries, or project tasks. Calculate throughput, processing/waiting time, rework, paths, bottlenecks, and conformance to an approved process where defined.

Incomplete timestamps and ambiguous start/end events must produce explicit uncertainty. Do not infer a complete process history from a final-state table. Deliver a real interactive process map and drill-down to permitted event traces.

### Resource optimization

Use a constraint solver such as OR-Tools for at least one functioning workload/shift allocation problem. Include skills, availability, approved maximum hours/rest rules, deadlines, workload balance, coverage, and budget constraints where supplied.

Distinguish hard constraints from preferences and expose objective weights. Return a proposal, feasibility status, objective values, unresolved coverage, and solver termination status. Claim optimality only if the solver certifies it. Do not silently relax hard constraints.

### Causal analysis

Provide a limited causal-analysis workflow using a library such as DoWhy when data and study design support it. Require treatment, outcome, time ordering, stated assumptions, confounders, identification strategy, and appropriate sensitivity/refutation checks.

Deliver one transparent synthetic example, such as a process-policy change, with known data-generating assumptions. Keep “causal effect unavailable” as a valid result. Automated causal discovery or an LLM explanation does not establish causation or validate all assumptions.

### Operational simulation

Implement one reproducible discrete-event or queue/capacity simulation, such as support requests or approval processing. Estimate or configure arrival rates, service times, capacities, priorities, and routing with visible provenance.

Compare baseline and proposed staffing/process scenarios. Run repeated simulations, show variability, fix random seeds for reproducibility, and validate baseline behavior against observed data where available. State the model boundary.

A simulation plus a 3D scene is not automatically a company-wide digital twin. Use that label only when the modeled process, calibration, synchronization, and limitations are clear.

## 17. Reports, recommendations, and editable artifacts

Implement report templates for data quality, cleaning methods, executive analysis, department/project review, forecasts, and scenario comparison.

Reports must include relevant context, scope, data freshness, findings, evidence-linked charts, recommendations, assumptions, unresolved issues, and analysis/model limitations. Keep executive prose concise and put technical details in an appendix or disclosure.

- Store reports as structured, versioned documents with editable narrative sections and referenced metric/chart blocks.
- Natural-language edits generate a typed patch against an expected version. Preview changes, detect conflicts, and preserve history.
- Changing a period, filter, or metric definition must invalidate/recalculate affected numbers and charts. Editing wording must not silently modify data.
- Differentiate immutable snapshot reports from live views. A historic export must remain reproducible.
- Implement PDF and HTML export, CSV/XLSX data export, and DOCX report export when the chosen rendering stack supports it. Include accessible titles, complete legends, page breaks, Arabic shaping, units, and source details.
- Export permissions must match viewing permissions. Protect spreadsheet exports from formula injection and avoid placing secrets or hidden unauthorized fields in files.

## 18. Proactive monitoring and the action loop

Implement in-app schedules for source synchronization, quality checks, KPI refreshes, reports, and operational alerts. These are application features, separate from any chat-platform automation.

Support timezones, recurrence, pause/resume, run history, retries, cancellation where possible, and idempotent delivery. Store schedule ownership and re-evaluate its permissions at execution time.

Detect significant changes, stale data, schema drift, repeated failures, project risks, and workload exceptions. Use configurable thresholds, anomaly methods where useful, deduplication, cooldowns, and severity. Avoid floods of minor or repeated alerts.

Allow an authorized user to turn a recommendation into an internal action draft with owner, due date, evidence, and success metric. Track outcome reviews so the company can compare expectations with observed results.

For external emails, messages, CRM updates, or other side effects, require an explicit configured permission and concrete review policy. Do not ship demo actions that contact real people. Enforce idempotency and revalidate data/permissions at execution; a prior draft is not unlimited future authorization.

## 19. Architecture and preferred implementation stack

Use these as defaults, adapting only for documented compatibility or deployment constraints:

| Layer | Preferred starting point |
| --- | --- |
| Web application | Next.js App Router, TypeScript, React, a coherent CSS/token system, accessible component primitives. |
| Client data/state | A query cache such as TanStack Query; minimal local state; schema-validated forms. |
| Tables and visualizations | TanStack Table plus virtualization where needed; Apache ECharts or Plotly as the principal chart system. |
| Process and graph views | A suitable graph library such as React Flow or Cytoscape, integrated with the same design system. |
| Backend API | FastAPI, typed Python models, SQLAlchemy, and Alembic migrations. |
| Application metadata | PostgreSQL with explicit tenant and authorization controls. |
| Raw and generated artifacts | S3-compatible object storage; a local filesystem adapter for development if needed. |
| Analysis | DuckDB, Polars, and selected statistical libraries; bounded queries against approved source systems. |
| Background work | One queue system with Redis, explicit job records, retry policy, and isolated analysis workers. |
| Agents | LangGraph with typed tools and a provider abstraction. |
| Retrieval | PostgreSQL/pgvector plus lexical search initially; add another retrieval service only for a measured requirement. |
| Predictive/advanced analysis | scikit-learn/statistical baselines, selected boosting, optional TabPFN/Chronos adapters, OR-Tools, and bounded causal/simulation components. |
| Monitoring | Structured logs, metrics, tracing through OpenTelemetry where appropriate, and persisted evaluation records. |
| Local deployment | Docker Compose with explicit core and optional model/advanced profiles. |

Keep a single chart specification and metric-result contract even if a specialized 3D renderer is necessary. Avoid installing overlapping charting or agent frameworks without a concrete need.

A reasonable repository layout is `apps/web`, `services/api`, `services/worker`, `packages/contracts`, `infra`, `scripts`, `tests`, and `docs`. Adapt to the language tooling instead of forcing unnecessary package boundaries.

Separate the control plane from heavy data execution. PostgreSQL stores users, permissions, definitions, jobs, and artifact metadata; raw/cleaned datasets and model artifacts live in versioned object storage. Analytical workers process permitted snapshots or push bounded work to approved sources. Keep persistence authoritative; Redis is not the sole record of critical jobs or decisions.

DuckDB is an initial analytical engine, not an unsupported promise of unlimited concurrent warehouse scale. Define an engine interface so a larger warehouse can be added later after measured requirements justify it.

## 20. Data model and lifecycle

Implement migrations and consistent identifiers for these logical entities, combining tables where it genuinely simplifies the design:

- Organization/tenant, user, membership, role, department scope, and access policy.
- Data source, connector configuration, secret reference, sync job, checkpoint, and schema version.
- Dataset, dataset version, table/column metadata, extraction record, profile, quality issue, cleaning recipe, transformation step, and lineage edge.
- Business entity, relationship, glossary term, metric definition/version, approved join, and semantic mapping.
- Customer/contact/opportunity/activity; employee/department/role/skill/assignment; project/task/milestone; supplier/order/invoice/expense; support case; objective/target.
- Document/version/chunk, access metadata, and evidence reference.
- Analysis run, tool execution, structured result, finding, chart specification, dashboard/version, report/version, and export.
- Model run/artifact, backtest, forecast, scenario, optimization run, and process event/object mapping.
- Conversation/message, action proposal, approval, decision, notification, schedule, audit record, and evaluation case/result.

All tenant-owned records and object keys must preserve tenant isolation. Imported entity IDs require source namespaces and canonical mapping. Track created/updated timestamps, source identity, effective dates where needed, and version relationships.

Define deletion and retention behavior for originals, derived snapshots, indexes, caches, reports, model artifacts, and backups. A source deletion or revoked permission must not leave its contents exposed through old retrieval results or shared exports.

## 21. API and frontend/backend integration

Provide documented, versioned APIs for authentication/context, connectors, datasets, profiling, cleaning preview/apply, semantic definitions, analysis, jobs, conversations, charts, dashboards, company modules, forecasting, scenarios, reports, exports, approvals, schedules, and administration.

- Generate or validate frontend contracts against the backend schema. Do not maintain incompatible independent types.
- Use cursor/paged responses for large collections and explicit filter/sort schemas.
- Use accepted-job responses and polling/SSE for long operations. Design reconnect behavior and status recovery; keep status IDs scoped to the requester.
- Use idempotency keys for retriable mutations and optimistic version checks for artifact edits.
- Return structured error codes, a readable message, field details where applicable, and a correlation ID. Never expose secrets, raw SQL credentials, or stack traces.
- Distinguish unsupported, not configured, insufficient data, denied, failed, and empty results. Do not return an empty success when the connector failed.
- Bind chart, report, and assistant outputs to real result IDs so the frontend cannot silently substitute arbitrary values.
- Make every visible primary control functional. Hide unfinished capabilities or show an honest unavailable state with a reason; do not use buttons that only display “coming soon” throughout the product.

## 22. Security, access, and data handling

Implement security as executable application behavior, not only documentation.

- Use established authentication/session libraries. Provide a secure local development login and an OIDC integration path for enterprise SSO. SSO is not “verified” until its real flow has been tested.
- Use secure HTTP-only cookies or an equivalently justified pattern, CSRF protection where applicable, session expiry/revocation, and backend authorization.
- Implement roles such as administrator, executive, analyst, department manager, HR specialist, and viewer with explicit resource and field scopes. Administrator access is not automatically a business need to read every HR field.
- Enforce tenant, department, row, column, and artifact permissions server-side across API, SQL, retrieval, graph traversal, files, scheduled jobs, caches, and exports. UI hiding is not authorization.
- Scope caches by tenant, user permission context, data/metric version, and filters. Invalidate them when relevant permissions or source data change.
- Keep secrets in protected server configuration or a secrets manager; encrypt stored connector credentials and separate encryption keys. Never send credentials to the model.
- Restrict connector endpoints, redirects, and DNS resolution to approved network destinations; prevent access to cloud metadata or unrelated internal services. Allow legitimate private company hosts only through explicit administrative configuration.
- Limit uploads, decompression, query cost, tool calls, job concurrency, and artifact sizes. Validate paths and MIME/content before parsing. Isolate document processing where appropriate.
- Use trusted dependency/model distribution paths and pinned revisions where practical. Do not load arbitrary user-supplied pickle/model artifacts or enable remote model code without review.
- Sanitize rendered markdown/HTML and file exports. Content security policy, secure headers, and escaped chart labels must protect rich AI output surfaces.
- Apply provider policies controlling which data may leave the deployment. Local inference is an option, not proof of complete privacy; logs, embeddings, traces, exports, and backups must follow the same policy.
- Record auditable reads/changes appropriate to sensitivity, while redacting sensitive content from operational logs. Use tamper-resistant audit storage design without casually claiming immutability.
- Prepare backup/restore and revocation tests. Describe actual protections and limitations; do not claim regulatory certification, legal compliance, or production security from a passing unit test suite alone.

## 23. Demonstration data that proves the product works

Create a deterministic fictional company dataset spanning at least 24 months with related sales, customers, support cases, projects, departments, employees, skills, assignments, expenses, suppliers, orders, and event logs. Use fictional people and company names, not real employee records.

Include a modest default size that runs on a normal development machine, plus a separate configurable scale generator. Suggested default: 6–8 departments, approximately 100 employees, 15–25 projects, a few hundred customers, and enough transactions/events to demonstrate trends. These are seed-design targets, not performance claims.

Design coherent scenarios with independently calculable truth:

- Increased revenue alongside reduced margin due to documented discount/product-mix effects.
- Support demand spikes and known capacity constraints.
- A project delayed by a supplier or approval dependency.
- A team carrying more assigned workload relative to available capacity.
- A duplicated import batch, inconsistent date/number formats, missing costs, and legitimate negative returns.
- A source schema change and an interrupted synchronization run.
- Different access scopes for an executive, department manager, HR user, and viewer.

Generate raw dirty files and independently defined expected values, not hand-authored dashboard JSON. Feed them through the same ingestion, cleaning, analytics, and API paths as real data.

Keep a visible “Demo data” designation and use a documented demo reporting date so screenshots remain coherent. Do not pretend demo observations occurred today. Provide reset/reseed commands and a clean empty-workspace path.

Synthetic data proves implementation behavior, not real-world model accuracy or commercial readiness. Evaluate actual company performance later on representative, authorized data.

## 24. Evaluation, correctness tests, and failure tests

Implement risk-focused tests that verify business behavior and isolation rather than merely mirroring implementation.

### Data and analytical correctness

- Golden calculations for metrics, currencies, timezones, effective dates, joins, distinct counts, and stock/flow semantics.
- Before/after reconciliation for cleaning, preserving legitimate returns and identity fields.
- Full-scope versus preview/sample behavior, malformed rows, Excel formula-cache limitations, and duplicate ingestion.
- Incremental sync, checkpoint recovery, idempotent updates, deletion handling where supported, and schema drift.
- Report/chart/chat equality for identical filters and data versions; report edits must update dependencies and preserve historical versions.

### AI evaluation

Create a versioned evaluation set with at least 60 meaningful English/Arabic questions across sales, people, projects, operations, budgets, sources, ambiguity, insufficient data, forecasts, and authorization. Include cross-module and follow-up tasks.

Define expected outcome categories, reference values or source evidence, allowed tolerances, expected clarifications/abstentions, and prohibited exposures. Keep development examples separate from held-out evaluation cases.

Measure factual/numeric correctness, evidence support, tool execution success, clarification quality, unsupported-claim rate, and access-policy compliance. LLM-as-judge may assist qualitative review but is not the sole oracle for numbers or security.

Report the full denominator: attempted, verified automatic completion, completed with human correction, correct abstention, incorrect abstention, failed, and timed out. Do not inflate the 95% automation objective by silently excluding failures or difficult in-scope tasks. Report accuracy and automation separately.

Use deterministic provider doubles for repeatable workflow tests, clearly labeled as tests. Separately run and record real-provider smoke/evaluation tests when credentials and models are available. A mocked test cannot certify live AI behavior.

### Security and resilience

- Attempt cross-tenant access through object IDs, direct API calls, exported files, caches, search, citations, graph traversal, and job IDs.
- Test revoked permissions, expired sessions, invalid credentials, protected HR fields, and small-group disclosure protections.
- Test document prompt injection, unsafe tool arguments, SQL function abuse, output rendering, SSRF controls, and sandbox boundaries.
- Test cancellation, process restarts, queue retries, duplicate submissions, unavailable providers, and partial upstream failures.

### Frontend and visual QA

Use available browser automation such as Playwright to test the actual integrated interface. Capture and inspect important screens in English/LTR and Arabic/RTL, light and dark themes, desktop, tablet, and mobile widths.

Verify at least: onboarding, upload, cleaning preview/apply, dashboard drill-down, chat result, report editing/export, people/project pages, process map, scenario comparison, denied access, and empty/error states.

Inspect overflow, text wrapping, Arabic glyph shaping, charts, focus, contrast, scroll behavior, mobile panels, console errors, and print/export layout. Fix visible defects rather than treating screenshot generation itself as visual approval.

## 25. Performance and operational visibility

Set a documented performance profile with dataset size, machine/container resources, concurrency, and model configuration. Measure actual results before declaring any target achieved.

- Keep navigation and filtering responsive; paginate/virtualize large tables and lazy-load heavy graph/3D/model components.
- Render useful executive content progressively. Run long ingestion, OCR, analysis, and model work asynchronously.
- Use query pushdown, column projection, partitioning, streaming, and validated caching where appropriate.
- Record p50/p95 latency for selected interactions, job completion time, peak memory, ingestion throughput, model latency/token usage, and failure rate under a defined load.
- Show per-source freshness and per-job state. Track model/metric drift, queue backlog, repeated failures, permission denials, and alert volume.
- Record tool count, cost estimates where pricing is known/configured, timeout cause, and run lineage without logging sensitive raw payloads by default.
- Do not publish unmeasured speed, cost savings, prediction accuracy, or “enterprise scale” claims.

## 26. Deployment and local developer experience

- Provide a documented local startup path, migrations, seed/reset commands, health/readiness checks, environment examples without secrets, and shutdown/cleanup guidance.
- Make the deterministic core run without a mandatory GPU or paid model API. Document separate requirements for local LLMs, optional foundation models, graph engines, and OCR.
- Use separate API, background worker, and isolated code-execution responsibilities. Restrict container privileges, mounts, and network exposure.
- Configure durable volumes, migration ordering, startup health checks, and basic backup/restore procedures.
- Provide CI for formatting/linting, type checks, risk-focused tests, build, and the available integration gates. Keep secrets out of logs and artifacts.
- Prepare a deployment guide for a private VM/container environment with TLS, secrets, monitoring, storage, and backup responsibilities. Add cloud-specific manifests only for an actual target.
- If the repository contains `.openai/hosting.json`, follow the environment's Sites workflow and hosting constraints. Do not force unsupported backend services into a frontend-only hosting environment.
- Do not silently publish company data or infer permission to activate an externally reachable production service.

## 27. Required repository deliverables

Deliver the working source, migrations, real seed pipeline, connector adapters, model/tool interfaces, tests, build/deployment configuration, and concise documentation including:

1. `PROJECT_SPEC.md` — this specification, preserved.
2. `README.md` — setup, run, configure AI, seed, test, and demo walkthrough.
3. `IMPLEMENTATION_STATUS.md` — honest requirement-by-requirement completion and blockers.
4. `docs/architecture.md` — system boundaries, data flow, execution isolation, and key decisions.
5. `docs/design-system.md` — tokens, layouts, RTL rules, states, accessibility, and component guidance.
6. `docs/data-model.md` and `docs/metrics.md` — entities, joins, definitions, currency/time rules, and lineage.
7. `docs/connectors.md` — actual supported formats/systems, sync behavior, limits, and configuration.
8. `docs/security.md` — threat model, enforced permissions, secrets, tenant isolation, and residual limitations.
9. `docs/evaluation.md` — test data, metrics, executed commands, results, and provider verification status.
10. `docs/deployment.md` — deployment, backups, restore, operations, and resource profiles.
11. A machine-readable capability manifest distinguishing implemented/tested, implemented/unverified, configuration-blocked, and unimplemented capabilities.
12. Browser screenshots and an evidence index for important workflows, stored appropriately for the actual environment.

Documentation must describe what the final implementation actually does. Do not write reports claiming tests passed before running them. Keep known limitations specific and reproducible.

## 28. Implementation milestones and continuation

1. **Foundation and design:** inspect the environment; define data/API contracts, metric semantics, design tokens, main layouts, accessibility, demo schema, and a brief architecture decision record. Render the core executive shell early.
2. **Complete vertical slice:** implement upload, storage, profiling, cleaning recipe/preview/apply, governed metric queries, an evidence-backed dashboard, and report persistence using real seeded data.
3. **AI and report interaction:** implement typed tools, provider configuration, stateful chat, verified answers, dashboard/report patches, citations, and failure recovery.
4. **Company intelligence:** implement customer, people, project, operations, cost, supplier, support, and objective views using the shared definitions and permissions. Complete database sync and the selected business-system adapter.
5. **Advanced analysis:** implement baseline forecasting/backtests, optional foundation-model adapters, relationship exploration, process mining, constrained scheduling, and bounded causal/simulation workflows.
6. **Operational product:** complete notifications/schedules, approvals, exports, auditability, retention, backup procedures, resilience, and deployment configuration.
7. **Release verification:** run correctness and isolation tests, real-provider checks where possible, browser journeys, visual inspection, RTL/accessibility checks, and defined performance measurements; fix material failures.

During every milestone, keep the frontend and backend integrated. Prioritize a polished functioning journey, then extend it without leaving false-ready screens. Maintain a coverage matrix so breadth does not hide incomplete behavior.

If blocked by credentials, compute, network, or unavailable tools, identify the exact dependency and continue all feasible work. Mark the affected feature accurately; do not downgrade the entire specification to a mockup or pretend the blocked integration succeeded.

## 29. Acceptance matrix — evidence required before completion

| Requirement | Required evidence |
| --- | --- |
| Executive frontend | Inspected screenshots and functioning navigation, filters, detail drawers, and meaningful states. |
| Arabic/English | Working RTL/LTR routes, localized labels and formatting, readable exports, keyboard checks. |
| File ingestion | Actual parsing of supported formats with row coverage and explicit parse errors. |
| Cleaning | Before profile, reviewed recipe, new cleaned version, reconciliation, method report, and rollback. |
| Metric consistency | Reference calculations match chat, dashboards, reports, and exports for identical scope. |
| AI assistant | Real tool executions, evidence-linked answers, clarification/abstention, and recorded provider status. |
| Interactive dashboard | Persisted create/edit/filter/drill-down behavior through UI and chat. |
| Company modules | Linked data and functioning views for people, projects, operations, costs, customers, and related entities. |
| Database sync | Successful connection/read, incremental update, duplicate/retry handling, and freshness indicators. |
| External adapter | Implemented protocol and tests; explicit live-verification status if credentials are unavailable. |
| Forecasting | Baseline comparison, temporal backtest, stored run, forecast display, and eligibility handling. |
| Modern model adapters | Real invocation tests when available; honest unavailable state otherwise. |
| Process/resource analysis | Event-based calculations, interactive process view, and a feasible or explicitly infeasible solver result. |
| Simulation/causal workflow | Reproducible bounded example with assumptions and limits, not fabricated business effects. |
| Reports | Real edits, recalculation, version history, valid exports, and correct permissions. |
| Security | Executed cross-tenant, protected-field, injection, and artifact-access tests. |
| Reliability | Restart/retry/idempotency checks and observable failures without data corruption. |
| Deployment | Reproducible startup/build and documented environment-specific gates. |
| Readiness claims | Completion manifest matches evidence; no invented performance, accuracy, or compliance claims. |

## 30. Final execution instruction

Start by inspecting the repository and environment. Write a short implementation plan, preserve this specification, and build the first integrated product slice immediately. Continue through the milestones while keeping design quality, data correctness, and authorization intact.

When reporting completion, lead with what a manager can actually do, provide startup/demo instructions, summarize verified tests and visual QA, and identify any concrete unresolved gate. Do not present a long list of technologies as proof of a working product. The deliverable is the functioning system and its evidence.

## Reference starting points

These are official references for implementation research, not guarantees that a particular package version or model is appropriate. Recheck documentation, licenses, and compatibility when building.

- [Next.js App Router documentation](https://nextjs.org/docs/app)
- [WCAG accessibility guidance](https://www.w3.org/WAI/standards-guidelines/wcag/)
- [LangGraph workflow capabilities](https://docs.langchain.com/oss/python/langgraph/overview)
- [DuckDB supported data sources](https://duckdb.org/docs/current/data/data_sources.html)
- [Cube semantic-layer documentation](https://docs.cube.dev/docs/introduction)
- [Chronos forecasting models](https://github.com/amazon-science/chronos-forecasting)
- [TabPFN tabular models](https://github.com/PriorLabs/TabPFN)
- [OR-Tools employee scheduling](https://developers.google.com/optimization/scheduling/employee_scheduling)
- [DoWhy causal-inference documentation](https://www.pywhy.org/dowhy/)
- [Object-centric process mining overview](https://learn.microsoft.com/en-us/power-automate/object-centric-overview)

Use these sources to validate concrete implementation decisions. Do not copy a vendor's branding, interface, or unsupported performance claims. BASEERA should have its own clear identity and measured behavior.
