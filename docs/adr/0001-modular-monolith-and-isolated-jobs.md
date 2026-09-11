# ADR-0001: Modular monolith with isolated analytical jobs

**Date**: 2026-09-04  
**Status**: accepted  
**Deciders**: BASEERA implementation team and product specification

## Context

BASEERA needs one coherent authorization and semantic layer while supporting file parsing,
analytics, exports, and optional models that can be slow or resource intensive. An early fleet of
microservices would multiply policy and data-contract boundaries before workload measurements
justify them. Running all work in the request process would make cancellation, retries, resource
limits, and failure recovery unreliable.

## Decision

Use a tenant-aware modular monolith for the web/API control plane, with persisted background jobs
executed by a separate worker process. Keep an engine and artifact interface so measured future
needs can replace DuckDB/local storage without changing evidence and metric contracts.

## Alternatives considered

### Microservices per company module

- **Pros**: Independent scaling and deployments; strong process separation.
- **Cons**: Duplicated authorization, distributed transactions, contract/version overhead, and
  higher operational cost.
- **Why not**: Current scale and team boundaries are unmeasured; the complexity would arrive before
  a demonstrated need.

### Single synchronous web/API process

- **Pros**: Smallest local topology and simplest debugging.
- **Cons**: Slow parsing and models block request capacity; restart/retry/cancellation semantics are
  weak; resource isolation is poor.
- **Why not**: It cannot safely support the required long-running ingestion and analysis journeys.

### Warehouse-first architecture

- **Pros**: Mature large-scale concurrency and pushdown.
- **Cons**: Requires external infrastructure and credentials; makes a deterministic local demo
  dependent on a commercial or separately operated service.
- **Why not**: The first release must run locally, while an engine boundary preserves a later path.

## Consequences

### Positive

- Authorization, metric definitions, versions, and audit policy stay consistent.
- Long work gains durable status, bounded retries, cancellation points, and resource controls.
- Local development remains reproducible without a paid data warehouse or model API.

### Negative

- API and worker releases must remain schema compatible.
- PostgreSQL and the queue can become shared scaling bottlenecks.
- Strong module boundaries require code review discipline rather than network boundaries.

### Risks

- A worker could accidentally bypass authorization. Mitigation: jobs carry opaque IDs and resolve a
  fresh server-side policy context before input access and publication.
- Embedded analytics can exceed host resources. Mitigation: enforce limits, project columns, stream
  where possible, measure representative workloads, and add an engine only after a recorded ADR.

