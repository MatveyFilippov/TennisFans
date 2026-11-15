# Migrations and rollback

The backend automatically applies the committed initial Alembic revision on a completely empty existing PostgreSQL schema. It refuses missing, unknown, newer, or incomplete schema revisions. Database creation and privilege setup belong to the operator.

Run migrations through the application's packaged `tennisfans db upgrade`. Back up PostgreSQL and media while writes are stopped before upgrading. The migration service holds a PostgreSQL transaction lock around DDL and checks the installed revision. `tennisfans db check` compares the schema revision and SQLAlchemy metadata with Alembic.

```bash
set -a
source /etc/tennisfans/development/backend.env
set +a
/opt/tennisfans/development/current/backend/.venv/bin/tennisfans db check
```

To prepare a future version, generate a revision against a disposable database at the previous head using Alembic's programmatic config in `tennisfans.db.runtime`. Review each DDL and backfill operation. Test upgrading a copy of real-shaped data and run the consistency check. Keep older migrations immutable, design expand/backfill/contract steps when a rolling upgrade is required, and document compatibility for each release.

## Recover from a failed deployment

1. Read the workflow error and both unit journals. Preserve the release directory, backup, DB and media for inspection.
2. If the schema revision stayed the same, the deployment script switches back to the previous release and restarts it. Confirm both health endpoints and the previous build SHA.
3. If it changed, the script restores the previous release symlink and leaves both services stopped. Recover forward if possible. To roll back data, first reconcile writes since backup, then restore the matched snapshot into an empty recovery database and media directory. Follow [Backup, restore, and host migration](backup-and-restore.md).
4. Point the service environment at the chosen recovered database and media. Update the systemd media path and permissions if needed. Start both units and check the release via `/health/ready`, `/health/live`, and `/api/v1/version` before restoring traffic.

A failed first deployment leaves no active release symlink. Inspect the journals, rectify host/database configuration and retry with an approved checked artifact. If the migration already succeeded, the next run checks its committed revision.
