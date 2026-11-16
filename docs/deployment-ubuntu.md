# Deploy on Ubuntu Server 24.04

Provision the host and PostgreSQL yourself. The examples use two independently run services per environment. You may place environments on separate hosts. On one host, use these loopback port pairs:

| Environment | UI | Backend | Frontend |
| --- | --- | --- | --- |
| production | `https://tennisfans.ru` | 8000 | 5173 |
| development | `https://dev.tennisfans.ru` | 8001 | 5174 |

## Install prerequisites and create isolated paths

```bash
sudo apt update
sudo apt install ca-certificates curl git openssh-client openssl postgresql-client-16
sudo apt install python3.12 python3.12-venv
```

Install Node.js 24 from the publisher's [Linux distribution](https://nodejs.org/download/release/v24.11.1/) for your CPU. Verify the archive against the publisher's signed checksums and make the `node` binary available at `/usr/local/bin/node` in the service unit. Install the [uv command](https://docs.astral.sh/uv/getting-started/installation/) at a system-wide path available to the application user. Check `node --version`, `python3.12 --version` and `uv --version`; the repository tests Node.js 24.11.1 and uv 0.9.21.

Retrieve the existing source and install the unit templates:

```bash
git clone https://github.com/MatveyFilippov/TennisFans.git
cd TennisFans
sudo install -m 0644 deploy/examples/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

As the host operator, create the per-environment service identities and directories. Run the block once for each environment and substitute the environment name.

```bash
env_name=development
account=tennisfans-$env_name
sudo useradd --system --create-home --shell /bin/bash "$account"
sudo install -d -m 0750 -o "$account" -g "$account" \
  "/opt/tennisfans/$env_name" "/var/lib/tennisfans/$env_name/media"
sudo install -d -m 0750 -o root -g "$account" "/etc/tennisfans/$env_name"
sudo install -m 0640 -o root -g "$account" /dev/null "/etc/tennisfans/$env_name/backend.env"
sudo install -m 0640 -o root -g "$account" /dev/null "/etc/tennisfans/$env_name/frontend.env"
sudo install -m 0640 -o root -g "$account" /dev/null "/etc/tennisfans/$env_name/deploy.env"
sudoedit "/etc/tennisfans/$env_name/backend.env"
```

## Provision PostgreSQL separately

On your PostgreSQL host, use your normal administration channel. Repeat with independent role, password, and database names for production. This example runs from an operator session connected to the external PostgreSQL server. The default database is created and owned by an operator role, with application grants scoped to the public schema. Set the passwords interactively and require the configured host/TLS controls.

```sql
CREATE ROLE tennisfans_dev LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password tennisfans_dev
CREATE DATABASE tennisfans_dev;
\connect tennisfans_dev
REVOKE ALL ON DATABASE tennisfans_dev FROM PUBLIC;
GRANT CONNECT ON DATABASE tennisfans_dev TO tennisfans_dev;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO tennisfans_dev;
```

The initial migration runs with the application role in the empty existing schema. Its rights allow table ownership and later DDL in that schema. Keep the database server bound to operator-approved interfaces and configure `pg_hba.conf`, certificate verification and firewall access as appropriate. Protect the production DB network and credentials from the development service identity.

## Set backend, frontend, and deployment environments

Example production settings for a same-origin reverse proxy. Replace values marked `YOUR_…` and use a separate random session secret per environment (`openssl rand -hex 32`). Keep URI credentials URL-encoded. Use a shell-safe single quote around the database URL and origin list so the deployment shell and systemd both parse them.

```dotenv
TENNISFANS_ENVIRONMENT=production
TENNISFANS_DATABASE_URL='postgresql+psycopg://tennisfans_prod:YOUR_URL_ENCODED_PASSWORD@YOUR_DB_HOST:5432/tennisfans_prod?sslmode=verify-full'
TENNISFANS_SESSION_SECRET=YOUR_RANDOM_PRODUCTION_SECRET
TENNISFANS_MEDIA_ROOT=/var/lib/tennisfans/production/media
TENNISFANS_BACKEND_HOST=127.0.0.1
TENNISFANS_BACKEND_PORT=8000
TENNISFANS_PUBLIC_URL=https://tennisfans.ru
TENNISFANS_ALLOWED_ORIGINS='["https://tennisfans.ru"]'
TENNISFANS_SECURE_COOKIES=true
TENNISFANS_TRUSTED_PROXY_HOSTS=127.0.0.1
```

Set development's URL, DB, media root and port using the table, distinct credentials, and `TENNISFANS_ENVIRONMENT=development`. Keep Secure cookies for hosted development. For the independent frontend, set the corresponding loopback port in `frontend.env`:

```dotenv
FRONTEND_HOST=127.0.0.1
FRONTEND_PORT=5173
PUBLIC_API_BASE_URL=
```

In the operator-owned `deploy.env` set the two exact systemd names and health URLs. It sources the backend configuration using your chosen environment path:

```bash
set -a
source /etc/tennisfans/production/backend.env
set +a
BACKEND_SERVICE=tennisfans-backend@production.service
FRONTEND_SERVICE=tennisfans-frontend@production.service
BACKEND_HEALTH_URL=http://127.0.0.1:8000
FRONTEND_HEALTH_URL=http://127.0.0.1:5173
TENNISFANS_UV=/usr/local/bin/uv
```

The service unit expects release files and a build environment at `/opt/tennisfans/ENVIRONMENT/current`. The deployment script installs the checked application under that directory layout. For an installation without GitHub Actions, check out the approved release in a staging directory, build with the [development guide](development.md), assemble the artifact with the **Package the checked revision** commands in CI, and invoke `deploy/scripts/activate /opt/tennisfans/ENVIRONMENT ENVIRONMENT /path/to/tennisfans.tar.gz COMMIT_SHA` as the environment's service account on the server. The script stops both processes, saves the old database and media when present, applies migrations, activates the new release and probes each service. Enable both unit instances after the first successful installation:

```bash
sudo systemctl enable tennisfans-backend@development.service tennisfans-frontend@development.service
```

Create the first administrator using an interactive prompt once the release is installed:

```bash
sudo -iu tennisfans-development
set -a
source /etc/tennisfans/development/backend.env
set +a
/opt/tennisfans/development/current/backend/.venv/bin/tennisfans admin create YOUR_USERNAME
```

## Configure reverse proxy, TLS, DNS and verification

1. Create appropriate A/AAAA records for `tennisfans.ru` and `dev.tennisfans.ru` at your DNS provider. Publish an AAAA record only if IPv6 is routed and configured on the host.
2. Use one optional proxy example from `deploy/examples/caddy/Caddyfile` or `deploy/examples/nginx/tennisfans.conf`. For Nginx, provision certificates and duplicate the example with the development host, ports, and certificate paths. If colocated, keep only the proxy exposed and allow HTTPS; permit HTTP for the chosen certificate/redirect setup. The direct backend and frontend processes require no proxy for local operation.
3. Check external HTTPS, installability and the build SHA after deployment.

```bash
curl --fail https://dev.tennisfans.ru/health/ready
curl --fail https://dev.tennisfans.ru/api/v1/version
curl --fail https://dev.tennisfans.ru/health/live
curl --fail https://dev.tennisfans.ru/manifest.webmanifest
sudo journalctl -u tennisfans-backend@development.service -u tennisfans-frontend@development.service --since today
```

For separate API hosts instead, create the corresponding records and TLS configurations, put the API origin in the frontend's `PUBLIC_API_BASE_URL`, and apply the [cookie and origin configuration](configuration.md).

## GitHub owner checklist

1. In **Settings → Rules → Rulesets** (or **Settings → Branches**), protect both `main` and `dev`, require pull requests and owner review, and require the **Application quality and PostgreSQL** and **Documentation build** checks. Use the exact job names displayed by the first CI run. Preserve the stable branch as the default.
2. In **Settings → Actions → General**, allow the action publishers used by the versioned workflows and keep the default token read-only. The Pages deployment job requests its scoped Pages and OIDC grants.
3. In **Settings → Environments**, create `development` and `production`. If the `development` environment restricts deployment branches, allow `dev`. Set appropriate deployment restrictions and required reviewers for production where available. Allow owner-published SemVer release tags for production.
4. In each environment, add separate `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_ROOT`, `DEPLOY_PRIVATE_KEY`, and `DEPLOY_KNOWN_HOSTS` secrets. `DEPLOY_USER` is the corresponding application account. `DEPLOY_ROOT` is its own writable environment path. Verify the SSH server's host key out of band before recording its full known-hosts line. Install the matching public key for each user. Use `visudo -f /etc/sudoers.d/tennisfans-deploy` to allow each account passwordless `/usr/bin/systemctl start` and `stop` only with its exact backend/frontend instance names (both names in the same command). Avoid wildcard service names or root SSH. Ensure `sudo -n systemctl stop SERVICE1 SERVICE2` and the corresponding start command match the allowed arguments exactly. Restrict SSH ingress and key use according to your host policy.
5. In **Settings → Pages → Build and deployment**, choose **GitHub Actions** as the source. On `main`, run **Publish documentation** from the Actions tab or push a docs change. Read the actual docs URL on the deployed Pages environment. This serves only English documentation.
6. Review and merge the development PR. The resulting push to `dev` runs CI. After the application and documentation checks pass, CI deploys its build artifact if the checked commit is still the head of `dev`. Owner-managed DNS and environment setup are required before a deployment can succeed. Promote the desired tested `dev` revision to `main` through an owner-created PR when ready for release.
7. Verify the release commit and go to **Releases → Draft a new release**. Choose a new stable `vMAJOR.MINOR.PATCH` tag pointing to the approved commit in `main`, paste the changelog, leave **pre-release** clear, and select **Publish release**. Production verifies tag ancestry, reruns checks for the release revision, then gates deployment on the production environment and smoke-tests its build SHA. A tag push or a push to `main` alone does not initiate production. Verify the Actions outcome and health endpoints. See [rollback](migrations.md) if a deployment fails.
