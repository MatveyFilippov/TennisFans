# Security and troubleshooting

## Threat model

- **Account takeover.** Store Argon2id hashes and server-side session digests. Use an expiring Secure, HTTP-only cookie for HTTPS and invalidate sessions on reset or privilege change. Temporary credentials are short-lived and single-use. Account restriction persists until the user changes the temporary password.
- **Cross-origin actions and IDOR.** Every browser mutation requires an explicit allowed origin. Authenticated mutations also require a session-bound CSRF header. The server checks role, specific tournament assignment, and match participation. Revoke a tournament assignment to remove its authority immediately.
- **Abusive submissions.** PostgreSQL-backed fixed-window rate limits throttle registrations, login attempts, score submissions and uploads. Trusted proxies must only forward the true client address. Disputes exclude a result immediately and corrections leave an audit trail. Admin access is limited to trusted operators.
- **Unsafe images.** JPEG, PNG, and WebP are decoded, size- and pixel-checked, then re-encoded with metadata removed. The server uses UUID-derived filenames. User paths, uploaded filenames and SVG are outside the gallery interface. Define proxy request limits as well as app limits. Every service UID should own only its environment's media.
- **Browser and infrastructure.** The reference frontend uses a content security policy, denies framing, and limits connection and image origins. Alternate servers should apply the same policy, serve frontend content over HTTPS, and use HSTS after confirming your TLS setup. The service worker caches public routes with an explicit API response marker and a bounded cache. Use separate host-only cookies, credentials, DB roles, storage and secrets per environment.

Audit and logs contain operational IDs. Protect database credentials, reset secrets and backups. Use the relevant private reporting channel for sensitive disclosures.

## Logs and capacity

Use `journalctl` by unit, filter by the `X-Request-Id` returned by the API, and correlate scheduler failures with the tournament ID. The backend formats production output as JSON. Configure journal rotation and retention with the host operator. Monitor disk usage, database connection pool saturation, statement timeouts, memory during image processing, backup age, and release health. The full Elo replay and instance-wide lock cap write throughput on large installations; benchmark the intended scale before changing operational limits.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Backend fails before ready | Check DB URL, role and PostgreSQL grants, Alembic revision, media directory permissions and the unit journal. Follow the [migration guide](migrations.md) for revision errors. |
| Browser rejects sign-in | Compare exact UI and API origins, TLS/Secure cookie setting and system clock. For separate sites verify browser cookie policy. |
| A due tournament needs action | Check capacity and fixed teams. Fill the roster and have an administrator set a new start time. |
| Uploaded files fail | Compare multipart request size, image count per batch, actual still image format, decoded pixel limit, quota and reverse-proxy body limit. |
| Frontend updated to an old API URL | Verify `/config.json`, service environment, and the current installed PWA update. |
| Dev deploy did not run | Verify the workflow exists on `main`, the CI push run on `dev` is green, and the matching SHA artifact exists. |
| Deployment fails | Inspect SSH known hosts, environment restrictions, systemd authorization, database revision, and the release smoke-test output. |
