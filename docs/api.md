# REST API

FastAPI serves Swagger UI at `/docs`, ReDoc at `/redoc`, and the OpenAPI document at `/openapi.json` on the backend origin. The [Ubuntu examples](deployment-ubuntu.md) show how to expose these paths with your web proxy. The source-controlled TypeScript contract is generated from that document.

- `GET /api/v1/public/users`, `/public/users/{id}`, `/public/stats/compare/{a}/{b}`
- `GET /api/v1/public/ratings`, `/public/ratings/{id}/history`
- `GET /api/v1/public/matches` and `/public/tournaments` and their detail paths
- `POST /api/v1/auth/register`, `/auth/login`, `/auth/logout`, `/auth/password` and `GET /auth/session`
- `POST /api/v1/matches/friendly`, `/matches/{id}/result`, `/matches/{id}/disputes`, `/matches/{id}/resolution`
- `/api/v1/tournaments`, nested `/organizers`, `/application`, `/applications`, `/roster`, `/teams`, and `/cover`
- `POST /api/v1/media/{user|match|tournament}/{owner_id}` with repeated multipart `files`
- `/api/v1/admin/users`, `/admin/audit`, `/admin/ratings/rebuild`, and administrative match and media actions

Lists with pagination use `offset`, `limit` (maximum 100), and a stable ordering by the chosen sort and ID. Errors contain `code`, `detail`, `context` and `request_id`. Validation responses specify affected fields without echoing their values.

```bash
API=http://localhost:8000
curl --fail "$API/health/ready"
curl --fail "$API/api/v1/public/ratings?limit=10"
curl --fail "$API/api/v1/public/matches?discipline=DOUBLES&category=FRIENDLY"
```

Use an allowed `Origin` for every state-changing request. Sign-in returns an HTTP-only session cookie plus a CSRF value. Send the cookie and `X-CSRF-Token` for protected mutations, and pass a new UUID `Idempotency-Key` for friendly creation, result submission, resolution, correction, and deletion. Retry the identical request with the same key. Match actions include the version from the most recent detail response. A `cascade_confirmation` conflict includes the affected match IDs and a token bound to the exact request. Review those fixtures before resubmitting with `confirmation`.

Example, assuming an existing authenticated cookie jar and participant UUIDs:

```bash
curl --fail-with-body -b /path/to/private-cookie-jar \
  -H 'Origin: http://localhost:5173' -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" -H 'Content-Type: application/json' \
  --data @friendly.json http://localhost:8000/api/v1/matches/friendly
```

```json
{
  "discipline": "SINGLES",
  "rules": {"format": "SHORT_MATCH", "short_games": 3},
  "a": ["00000000-0000-4000-8000-000000000001"],
  "b": ["00000000-0000-4000-8000-000000000002"],
  "played_at": "2026-01-06T18:00:00Z",
  "score": {"winner": 0, "sets": [{"a": 3, "b": 2}]}
}
```
