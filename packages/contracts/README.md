# BASEERA contracts

These JSON Schema 2020-12 contracts are the stable boundary shared by the API, web application,
workers, reports, and external integrations. Runtime API models are exported to
`packages/contracts/openapi.json`; generated TypeScript must be refreshed with `npm run api:openapi`
whenever a backend schema changes.

The schemas deliberately require evidence, scope, warnings, and optimistic version information so
that a narrative or UI widget cannot detach a claim from the calculation that produced it.

