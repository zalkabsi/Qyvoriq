# Security and responsible operation

## Implemented controls

- JPEG, PNG, and WebP allowlist; signature/decoder validation; 10 MB upload cap; 16 MP dimension cap; minimum dimensions; image integrity and channel checks; EXIF orientation correction.
- No uploaded file name is used as a path. Images are held in process memory, limited to 100 active inspections, and pruned after 30 minutes. There is no S3, database, or disk retention.
- Request IDs, structured event logs, and no image pixels, filenames, calibration identifiers, or bearer tokens in logs.
- API token enforcement when configured; production startup fails without `QYVORIQ_API_TOKEN`. Health checks are public; API docs are disabled in production.
- Process-local request limits, strict CORS origin allowlist, no credentialed CORS, TLS termination in the AWS template, narrow task inbound security-group rule, an empty application task role, and a short CloudWatch log retention period.
- Container runs as non-root with no Linux capabilities, a read-only filesystem in Compose, and no-new-privileges.
- No model downloads, external inference calls, analytics scripts, or third-party font requests.

## Deployment conditions

The API token is a simple shared bearer secret, not user-level authentication. Store it in Secrets Manager and rotate it outside the image. Do not expose an internet-facing endpoint without a trusted DNS/TLS setup and a public rate-control/WAF decision. The in-memory rate limiter is per-process and resets on task replacement. The AWS template's single task has no persistence; inspection IDs are not authorization secrets.

The container trusts forwarded headers because its task security group only accepts traffic from the ALB. Do not expose port 8080 directly. For local direct access, forwarded headers only influence best-effort rate limiting and URL scheme.

## Threats and residual risks

- A valid but adversarial image can still consume CPU/memory up to the configured upload and pixel limits.
- A public API token can be shared or stolen; this demo does not provide per-user identity, billing, or revocation workflow.
- Per-process rate limiting does not protect a horizontally scaled service.
- Memory may persist until expiry, process exit, or eviction; a deployment should document its memory/dump controls and keep task access restricted.
- A reading can be wrong while passing the current synthetic-derived threshold; the safe response is human verification.

## Data deletion

The API expires each inspection after 30 minutes of inactivity and clears the associated image/evidence bytes when the record is pruned. A process restart drops all records. No external object storage is configured. The benchmark fixtures are generated and may be deleted by removing `frontend/public/scenarios/`; regenerated assets contain no user data.
