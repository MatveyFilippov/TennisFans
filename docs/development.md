# Development

## UI and UX skills in Codex

Open the TennisFans checkout in Codex. Project skills live in `.agents/skills/` and are available from the repository root and its subdirectories. In a prompt, type `$` to select a skill, then name the screen or flow and describe the deliverable. Use `/skills` to list skills in the CLI. If the checkout has just changed and a skill is missing, restart Codex. See [OpenAI's skills documentation](https://learn.chatgpt.com/docs/build-skills).

| Skill | Example prompt |
| --- | --- |
| `$emil-design-eng` | Review hover, keyboard focus, and motion in the match result dialog. Return findings without editing files. |
| `$prototype` | Build three isolated variants of the tournament card for me to compare. Keep integration pending until I pick a variant. |
| `$break-ui` | Stress-test the standings with synthetic data in a local preview. Report layout failures before applying fixes. |
| `$mobile-native` | Audit the result form for touch feedback, keyboard overlap, and safe areas. Identify what needs testing on a phone. |
| `$learn-taste` | Propose rules based on the design corrections in this conversation. Wait for my approval before recording the rules. |
| `$frontend-skill` | Propose a visual direction, content hierarchy, and interaction ideas for the public tournament page for my review. |

### Sources and audit

- The five Emil Kowalski skills come from [emilkowalski/skills at `64eb3de`](https://github.com/emilkowalski/skills/tree/64eb3deb9a5fbfa041faf783e0bc3fd635872e9c) under MIT. The checkout includes `PICKER.md` and `CATALOG.md`, plus the choreography guide and recipes as local references for `emil-design-eng`. `prototype` and `learn-taste` retain their explicit-only invocation policy through Codex metadata.
- The curated installer no longer resolves `frontend-skill` by name. The project includes [the original package from `openai/skills` at `82d2c5b`](https://github.com/openai/skills/tree/82d2c5b44ac234ec0f204f647562a4349d90ef43/skills/.curated/frontend-skill) under Apache-2.0, checked against the [Frontend Skill block in the OpenAI article](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4). Both upstream licenses are included.
- The packages contain guidance and examples, with no executable scripts or required application libraries. The Motion, Framer Motion, and `react-use-measure` examples are optional. Keep the prototype picker's HTML static or render with React, and render stress-test fixtures as literal text. For mobile testing, use a local preview with test data and limit any LAN access to a trusted test network. For `learn-taste`, use this conversation or prior sessions explicitly named in the task.

## Local setup and checks

Use Python 3.12, uv 0.9.21, Node.js 24, npm, and a dedicated PostgreSQL 16+ database. Keep runtime state outside Git.

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
openssl rand -hex 32
```

Set the generated value as `TENNISFANS_SESSION_SECRET` and set your test development database in `backend/.env`. Provision the database and role with your PostgreSQL operator. Local runtime uses independent terminals:

```bash
cd backend
uv sync --locked
uv run --locked tennisfans serve
```

```bash
cd frontend
npm ci
npm run dev
```

Run the checks:

```bash
cd backend
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
export TENNISFANS_TEST_DATABASE_URL='postgresql+psycopg://ROLE:PASSWORD@localhost/tennisfans_test'
uv run --locked pytest --cov=tennisfans.domain --cov=tennisfans.modules.brackets \
  --cov=tennisfans.modules.ratings --cov=tennisfans.modules.tournaments \
  --cov=tennisfans.modules.matches --cov-fail-under=85
uv run --locked tennisfans openapi openapi.json
```

Integration tests recreate the public schema of the dedicated database whose name ends in `_test`. Use a disposable database with no application data. Playwright uses a separate empty database selected by `TENNISFANS_DATABASE_URL` and a separate media root. Export the backend settings into the test shell, choose and export `TEST_ADMIN_PASSWORD`, and initialize the test administrator.

```bash
cd backend
printf '%s\n' "$TEST_ADMIN_PASSWORD" | uv run --locked tennisfans admin create browser-admin --password-stdin
cd ../frontend
npm ci
npm run generate-api
npm run lint
npm run coverage
npm run build
npx playwright install --with-deps chromium
npm run e2e
```

From the repository root, run `uv run --locked --project backend --only-group docs mkdocs build --strict`. Use `mkdocs serve` with the same group to edit documentation locally.

## Dependency security checks

CI runs `npm audit` on the full frontend dependency tree and separately on production dependencies. Both audits fail CI on moderate, high, or critical findings or an npm audit error. CI also requires `picomatch` to stay out of the installed and locked production dependency trees. The deployed frontend consists of the build output and the static server.

From the repository root, with the CI version of Node.js:

```bash
npm ci --prefix frontend
npm audit --prefix frontend --audit-level=moderate --offline=false --include=dev --include=optional --include=peer
npm audit --prefix frontend --audit-level=moderate --offline=false --omit=dev --include=optional --include=peer
```

Update dependencies in focused PRs using `uv lock --upgrade-package PACKAGE` or `npm update PACKAGE`, inspect the lockfile diff, run the dependency audits and repeat the application checks. Coordinate Python and Node major upgrades with the Ubuntu and CI setup.
