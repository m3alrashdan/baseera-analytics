# Private-host operator templates

These files are examples for a reviewed single-VM/container deployment. They are not a managed
cloud deployment, a production-security claim, or a substitute for environment-specific testing.

## Files

- `compose.private-vm.yml` removes public database/Redis ports, binds web/API to loopback, adds
  restart/log/resource defaults, and is layered over the root Compose file.
- `nginx/baseera.conf` terminates TLS and proxies `/api/` to FastAPI and other routes to Next.js.
  Its CSP begins in report-only mode because the actual production bundle must be inspected first.
- `systemd/baseera-compose.service` starts/stops the reviewed Compose project under systemd.

Render the merged configuration before use:

```sh
docker compose -f compose.yaml -f infra/compose.private-vm.yml --env-file .env config
```

CI environments without a runtime `.env` can render syntax with
`infra/compose.validate.yml`. That overlay removes service-level environment files and must never be
used to launch the application.

Then review the rendered ports, mounts, images, environment, and limits. Compose interpolation can
expose resolved values, so do not attach its output to public logs when it includes secrets.

## Required operator work

1. Put the repository in `/opt/baseera` or adapt the systemd unit. Store secrets in an unreadable-to-
   others environment file or a real secret manager; `.env.example` is not production configuration.
2. Build, pin by digest, and scan images in a trusted pipeline. The root source-build workflow is
   useful for evaluation but does not provide provenance signing or an image registry policy.
3. Issue a real certificate, replace the example hostname/paths, and test renewal. Expose only the
   TLS proxy through the host and network firewall.
4. Test CSP against the actual Next.js build, browser journeys, exports, and telemetry endpoints;
   only then convert `Content-Security-Policy-Report-Only` to an enforced policy.
5. Restrict connector and model-provider egress to approved destinations. Database/Redis must not
   be internet reachable.
6. Configure log/metric collection and alerts without protected rows or credentials. Define CPU,
   memory, storage, concurrency, and retention from measured representative workloads.
7. Schedule encrypted, off-host database + artifact backups and perform an isolated restore drill.
   Keep both at a recoverable consistency point.

See [`../docs/deployment.md`](../docs/deployment.md) and
[`../docs/security.md`](../docs/security.md) for rollout, recovery, and residual limits.
