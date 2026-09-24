# BASEERA security model

This document describes required controls, test targets, and known deployment limits. It is not a
claim of regulatory certification or a substitute for a production threat assessment. A control is
considered verified only when its evidence entry is passed.

## Assets and trust boundaries

Protected assets include connector secrets, sessions, source rows, protected HR fields, semantic
definitions, results, evidence/citations, exports, model prompts/responses, audit records, and backup
material. Trust boundaries exist between browser and web/API, API and worker, tenant contexts,
source connectors, artifact storage, model providers, and deployment operators.

| Threat | Required control | Evidence gate |
| --- | --- | --- |
| Cross-tenant object reference | Server-side tenant predicate and current policy context on every row/artifact/result lookup | Direct API IDs, jobs, exports, citations, graph, cache tests |
| Protected HR disclosure | Field projection, role plus purpose/scope grant, aggregate small-group suppression | Role matrix and threshold tests |
| Session theft/CSRF | Secure HttpOnly SameSite cookies, expiry/revocation, CSRF protection for cookie mutations, origin checks | Browser/API session tests |
| Injection in query/tool input | Typed tools, allow-listed identifiers/operators, bound values, SQL AST/function restrictions | SQL/function/tool fuzz tests |
| Prompt injection in documents | Treat source text as data, isolate instructions, restrict tools by server policy, cite retrieved chunks | Adversarial document evals |
| SSRF/credential exfiltration | Destination allow-list, DNS/IP/redirect validation, no credentials sent to models | Network policy tests |
| Malicious upload/archive | Size/decompression limits, content sniffing, safe paths, isolated parser, no macros/model pickles | File corpus and traversal tests |
| Rich-output XSS | Sanitized markdown, escaped labels, CSP and secure headers, no arbitrary generated HTML/JS | Browser injection tests |
| Stale authorization | Permission revision in caches/jobs/schedules; re-check on access and execution | Revocation and retry tests |
| Sensitive logs/traces | Structured allow-listed metadata and redaction; no raw payload by default | Log inspection tests |
| Backup/export leakage | Encryption and access policy, expiring scoped retrieval, inventory and restore/revocation process | Artifact and restore tests |

## Authentication and sessions

Local development login must be visibly development-only and use established password hashing when
passwords are stored. Enterprise SSO follows an OIDC authorization-code flow with PKCE/state/nonce,
issuer/audience/signature checks, and explicit organization membership mapping. OIDC remains
unimplemented; it needs an adapter as well as configuration and a verified provider flow.

Session cookies use `Secure` outside local HTTP, `HttpOnly`, appropriate `SameSite`, constrained path,
rotation on authentication, absolute/idle expiry, and server-side revocation. State-changing browser
requests validate CSRF/origin according to the chosen session library. Error responses never reveal
whether an inaccessible tenant/resource exists.

## Authorization model

Roles include administrator, executive, analyst, department manager, HR specialist, and viewer, but
permissions are actions over resources rather than role-name checks scattered in routes. The policy
context includes tenant, membership, department/row scope, protected-field grants, artifact access,
and a monotonic permission revision.

Enforcement belongs in API dependencies plus repository/query projection and artifact retrieval.
Workers and schedules resolve current policy before input access and publication. Search results,
retrieval chunks, relationship traversal, cached results, citations, and export downloads receive the
same checks. A prior approval or signed URL is not unlimited future authority.

## Secrets and providers

- Secrets enter through protected server configuration or an external secrets manager, never
  `NEXT_PUBLIC_*`, source control, client state, model context, or evidence artifacts.
- Stored connector credentials require authenticated encryption with a separately managed key and a
  rotation/version field. Development environment variables are not a production secrets manager.
- Provider policy states which classifications may leave the deployment. Prompts are minimized and
  carry pseudonymous IDs where possible. Local inference still requires log, model, embedding,
  artifact, and backup controls.
- Arbitrary user-supplied model files, pickles, remote model code, and unpinned executable plugins are
  denied pending explicit review.
- The AI analyst team sends a hosted model (Claude) only column names and roles, up to eight
  category labels per dimension, aggregate findings and compact tool digests; raw rows, record-level
  anomaly context, credentials and session material are never sent. Configuring
  `BASEERA_ANTHROPIC_API_KEY` is the operator's explicit opt-in; without it analyses stay on the
  host. Models can call only read-only analysis tools with server-validated arguments; they cannot
  execute code, SQL or reach the network, and data text is framed as data, not instructions.

## Data and execution controls

Uploads enforce byte, row, member, decompressed-size, nesting, and runtime budgets; file names never
become filesystem paths. Analytical jobs use a dedicated process/container with constrained CPU,
memory, time, mounts, and network. No model-authored Python, shell, JavaScript, HTML, or remote URL is
executed. Typed chart specifications refer only to authorized result IDs.

Database and REST adapters are read-only, allow-listed, time-bounded, paged, and audited. Generated
query fragments are parsed/validated and values are bound. Query results apply row/column policy
before caching or provider use.

## Browser and transport controls

Private deployments terminate TLS at a reviewed reverse proxy. Required headers include a tailored
Content-Security-Policy, HSTS on HTTPS-only hosts, `X-Content-Type-Options: nosniff`, an explicit
`Referrer-Policy`, frame restrictions, and a restrictive `Permissions-Policy`. CSP must be tested
against the actual Next.js build; the example proxy policy in `infra/` is a starting template, not a
verified production policy.

## Audit and privacy

Audit records capture actor, tenant, action, resource, outcome, time, policy revision, and correlation
ID with redacted structured context. Read auditing is proportional to sensitivity. Access to audit
records is itself audited. Standard database durability is not described as tamper-proof; stronger
append-only/external retention requires deployment-specific implementation.

Small-group reporting uses tenant-approved thresholds and complementary suppression where needed.
Null, unavailable, suppressed, and denied are different states. Exports inherit classifications and
include tenant/version metadata without embedding secrets.

## Current residual limits

- The checked-in Compose baseline publishes PostgreSQL and Redis host ports and does not configure
  TLS, a secrets manager, container privilege restrictions, high availability, or network policy.
  It is for local/private-host evaluation until hardened.
- Local filesystem/named-volume artifacts do not provide object-lock guarantees or managed key
  rotation.
- OIDC, external databases/Odoo, hosted model providers, and production backup destinations require
  credentials and environment-specific verification.
- Passing unit tests would demonstrate selected behavior only; penetration testing, dependency/image
  review, operator controls, legal retention review, and disaster-recovery exercises remain separate
  gates.

See [`deployment.md`](deployment.md) for hardening responsibilities and
[`evidence/README.md`](evidence/README.md) for actual verification status.
