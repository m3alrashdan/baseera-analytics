# Connector support and configuration

Connector availability is capability-driven. The UI may show an option as ready only when the
server advertises an implemented capability; credential forms alone are not connectivity evidence.
The tables distinguish tested bounded adapters from the still-incomplete full connection lifecycle.
See [`evaluation.md`](evaluation.md) and the root capability manifest for evidence and limitations.

## File ingestion

| Format | Contract | Current verification status |
| --- | --- | --- |
| CSV | UTF-8/BOM comma-delimited records, identifier preservation and rejected-row metadata | Backend + real browser tests passed |
| TSV | Same bounded parser with tab delimiter | Backend tests passed |
| XLSX | First visible nonempty sheet, sheet inventory, explicit formula-cache warnings | Backend tests passed; no sheet/range picker |
| JSON | Top-level record array | Backend tests passed; no JSONPath selection |
| JSONL/NDJSON | One object per line with per-line rejection reasons | Backend tests passed |
| Parquet | Bounded record extraction and column metadata | Backend tests passed; no row-group selection UI |
| Legacy XLS | Not supported in the initial contract; convert to XLSX/CSV | Unsupported |

Archives, password-protected workbooks, macros, arbitrary remote URLs, and executable document
content are not accepted by default. Parsing reports selected/full/sample scope, sheets/members,
rows read/accepted/rejected, schema, warnings, and a content hash. Preview is never reported as full
coverage. Re-uploading identical tenant/source content is handled idempotently rather than silently
duplicating facts.

Spreadsheet formula cells may contain a cached value or no usable result. The parser does not run
Excel. It identifies formula/cache coverage and requires an exported calculated value or user choice
when a trustworthy total cannot be derived.

## Database and application adapters

| Adapter | Intended mode | Live verification |
| --- | --- | --- |
| PostgreSQL | Read-only bounded adapter, schema discovery and keyset resume | 3 live disposable-local tests passed; no private source verified |
| MySQL | Planned read-only mapped sync | Adapter unimplemented |
| SQL Server | Planned read-only mapped sync | Adapter unimplemented |
| Bounded REST | Allow-listed HTTPS, DNS pinning, paged JSON/cursor limits | Mocked contract tests passed; no live source verified |
| Odoo 19+ | Read-only JSON-2 fields_get/search_read with allow-lists | Mocked contract tests passed; no live Odoo verified |

Odoo's current external API direction is JSON-2. Legacy XML-RPC/JSON-RPC endpoints are deprecated
and scheduled for removal in Odoo 22, so new integration work is JSON-2-first. Actual model access
depends on the Odoo plan, version, API key/user rights, and tenant policy; no live support is claimed
without a recorded handshake and read test.

## Connection lifecycle

The steps below are target requirements, not a claim that the complete UI/server lifecycle exists.
Current publication accepts staged batches. Server secrets, live fetch orchestration, mapping UI
and canonical company publication still require implementation.

1. An administrator chooses a server-advertised adapter and reviews its exact capabilities/limits.
2. The API validates non-secret configuration separately from credentials. Secrets are encrypted or
   referenced in a secrets manager and are never returned to the browser after submission.
3. A bounded connectivity test validates DNS/IP policy, TLS, authentication, server/version, and a
   harmless read. “Saved” and “connected” are distinct states.
4. Schema discovery records tables/fields, types, keys, sample policy, and a fingerprint. The user
   approves mappings and joins before data is published.
5. Initial sync writes a staged immutable snapshot, validation counts, checkpoint, and freshness.
   Publication is atomic after reconciliation.
6. Incremental sync uses a configured immutable cursor or `(updated_at, stable_id)` tuple. Retries
   are idempotent, and source deletions are applied only where a reviewed mechanism exists.
7. Schema drift pauses affected mappings and dependent refreshes. Prior results remain visibly stale
   rather than silently changing meaning.

## Network and query limits

- Database users are read-only and restricted to approved schemas/tables. Statements are bounded
  SELECTs with allow-listed identifiers, limits/timeouts, and no user/model-supplied functions.
- REST/Odoo destinations require explicit administrator allow-list entries. Redirect targets and
  every resolved IP are checked; loopback, link-local, cloud-metadata, and unrelated private ranges
  are denied unless a specific private-company network route is approved.
- Response size, page count, runtime, concurrency, retries, and decompression are limited. Backoff
  honors upstream throttling; partial syncs do not become current.
- Connector logs contain correlation IDs and redacted error categories, not passwords, API keys,
  connection strings, or raw sensitive payloads.

## Configuration

Local service endpoints and provider toggles are illustrated in [`.env.example`](../.env.example).
Copy values into a non-versioned `.env`; use deployment secret injection outside development. Do not
put real credentials in Compose files, screenshots, CI variables printed to logs, or capability
evidence.

The only currently documented demo workspace is fictional: `tenant-demo`, reporting cutoff
2026-06-30, timezone `Asia/Amman`, and currency JOD. The empty workspace `tenant-empty` must remain
separate and must not inherit demo connector state.
