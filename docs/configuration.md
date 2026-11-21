# Runtime configuration

Backend variables use the `TENNISFANS_` prefix. The backend reads `.env` in its working directory and honors environment overrides. Use a service-readable file with restricted permissions.

| Backend setting | Default or requirement |
| --- | --- |
| `DATABASE_URL` | Required. Existing `postgresql+psycopg://` connection URI |
| `SESSION_SECRET` | Required random string of at least 32 characters |
| `ENVIRONMENT` | `development`, `test`, or `production` |
| `BACKEND_HOST` / `BACKEND_PORT` | `127.0.0.1` / `8000` |
| `PUBLIC_URL` / `ALLOWED_ORIGINS` | Exact API origin and JSON list of UI origins. No trailing slashes |
| `SECURE_COOKIES` / `SAME_SITE` | `false` / `lax`. HTTPS and Secure cookies are required in production |
| `SESSION_HOURS` / `RESET_MINUTES` | 168 hours / 30 minutes |
| `TRUSTED_PROXY_HOSTS` | `127.0.0.1`. Set only trusted proxy addresses |
| `MEDIA_ROOT` | `media`. Set an absolute persistent path on hosted installations |
| `UPLOAD_BYTES` / `UPLOAD_REQUEST_BYTES` | 12 MiB per file / 64 MiB total per request |
| `IMAGE_PIXELS` / `STORAGE_QUOTA_BYTES` | 25 million pixels / 0 for no application quota |
| `ELO_K` | 32. Coordinate all workers and rebuild on changes |
| `RECONCILE_SECONDS` | 30 seconds |
| `POOL_SIZE` / `STATEMENT_TIMEOUT_MS` | 8 pooled connections per worker / 30 seconds per statement |
| `LOG_LEVEL` | DEBUG in development and INFO in production |
| `BUILD_SHA` | `local`. The deployment writes the checked commit SHA |

The independent frontend reads `FRONTEND_HOST` and `FRONTEND_PORT` (defaults `127.0.0.1:5173`) and `PUBLIC_API_BASE_URL`. A blank API URL in the reference production server uses the UI origin. Set a full HTTP(S) origin for separate hosting. Restart the frontend for a configuration change. An alternate static server must serve `config.json` with `{"apiBaseUrl":"https://YOUR_API_ORIGIN"}`, fall back to `index.html` on SPA routes, and avoid long caching of the configuration, shell HTML, or service worker. Hashed assets can use immutable caching.

For `api.tennisfans.ru` and `api.dev.tennisfans.ru`, set each UI's exact corresponding API origin and allow only the associated UI in CORS. Keep the cookie host-only, use Secure and SameSite=Lax for HTTPS same-site subdomains. A truly cross-site deployment also needs `SameSite=None` and a browser that allows the cookie. A same-origin proxy on each UI origin works with the default SameSite mode.
