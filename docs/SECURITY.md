# Security and responsible operation

## Implemented controls

- JPEG, PNG, and WebP allowlist; decoder validation; 10 MB per-file cap plus a complete-body cap with 64 KiB multipart allowance before parsing; 16 MP source cap; a 1600-pixel working long edge; minimum normalized dimensions; EXIF orientation correction.
- No uploaded file name is used as a path. Source arrays are discarded after analysis. Retained evidence is capped at 100 records and 128 MiB of PNG bytes; this is not a cap on all process memory. Expired records become inaccessible after 30 minutes of inactivity and are swept every 30 seconds. Multipart parsing can use ephemeral OS temporary files, which close after the request. No S3, database, or durable image storage is configured.
- Request IDs, structured event logs, and no image pixels, filenames, calibration identifiers, or bearer tokens in logs.
- API token enforcement when configured; production startup fails without `QYVORIQ_API_TOKEN`. Health checks are public; API docs are disabled in production.
- Bounded process-local request limits, strict CORS origin allowlist, no credentialed CORS, planned managed HTTPS ingress, no application task role, and a seven-day application log group.
- The image runs as a non-root user. Compose additionally drops capabilities and sets a read-only filesystem and no-new-privileges; these Compose settings are not a claim about an uninspected managed AWS task.
- No model downloads, external inference calls, analytics scripts, or third-party font requests.

## Deployment conditions

The API token is a shared bearer secret rather than per-user authentication. The bootstrap generates it in Secrets Manager. The judge-demo design uses ECS Express Mode's HTTPS endpoint, a single steady-state task, a token on processing/result endpoints, and application request limits. A broader public launch requires separate traffic/load and WAF decisions. The limiter resets on task replacement; inspection IDs are not authorization secrets. No AWS network configuration or task settings are claimed verified until the live deployment is inspected.

The container disables proxy-header interpretation, so a client-supplied forwarding chain cannot choose the rate-limit identity. Behind an ALB, these best-effort limits can group requests by the observed proxy peer and are not individual-user quotas. The application uses relative URLs and does not require forwarded URL-scheme headers. Keep task port 8080 behind the managed load balancer; use a separate trusted-proxy/WAF design for a larger public service.

## Threats and residual risks

- A valid but adversarial image can still consume CPU/memory up to the configured upload and pixel limits.
- A public API token can be shared or stolen; this demo does not provide per-user identity, billing, or revocation workflow.
- Per-process rate limiting does not protect a horizontally scaled service.
- Memory may persist until expiry, process exit, or eviction; a deployment should document its memory/dump controls and keep task access restricted.
- A reading can be wrong while passing the current synthetic-derived threshold; the safe response is human verification.

## Data deletion

The API expires each inspection after 30 minutes of inactivity. Evidence is removed on access/creation cleanup or the next 30-second sweep; earlier eviction is possible when the count or evidence byte budget is full. A process restart drops all records. Browser previews remain in the operator's browser until cleared or closed. No external object storage is configured. The benchmark fixtures are generated and contain no user data.
