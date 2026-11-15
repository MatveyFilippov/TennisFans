# Backup, restore, and host migration

The database stores image UUIDs and metadata. The corresponding files live under the configured media root. Preserve both in a single backup and keep the associated code release and revision file. Store encrypted backups somewhere separate and restrict access. Monitor availability, age and size. Set and review retention explicitly.

## Backup

Run the following commands using the instance's environment and with writers stopped. For scheduled nightly backups, arrange the same stop, export, backup and restart sequence in an operator-managed timer. Coordinate the window with deployments.

```bash
sudo systemctl stop tennisfans-backend@development.service
sudo -iu tennisfans-development
set -a
source /etc/tennisfans/development/backend.env
set +a
mkdir -p /opt/tennisfans/development/backups
/opt/tennisfans/development/current/deploy/scripts/backup \
  "/opt/tennisfans/development/backups/$(date -u +%Y%m%dT%H%M%SZ)"
exit
sudo systemctl start tennisfans-backend@development.service
```

The backup contains a PostgreSQL custom dump, a media archive, revision and SHA-256 checksums. Copy the whole directory as a unit. Restore only backups you trust.

## Restore to a fresh target

1. Provision an empty recovery DB and role with the same privileges and create a new empty media directory. Stop any process that may write to the target.
2. Use the matching TennisFans release and compatible PostgreSQL tooling, with credentials scoped to the recovery target. Run the script below.

```bash
export TENNISFANS_DATABASE_URL='postgresql+psycopg://RECOVERY_ROLE:YOUR_PASSWORD@RECOVERY_HOST:5432/tennisfans_recovery'
export TENNISFANS_MEDIA_ROOT=/var/lib/tennisfans/recovery/media
./deploy/scripts/restore /path/to/backup-directory --confirm-empty-target
```

3. Start the matching backend against the recovered DB and media, validate `tennisfans db check`, query `/health/ready`, view a match, and fetch an original and thumbnail. Compare a player history and tournament result against the source. Avoid bootstrapping a new administrator on top of restored user records.
4. Rotate the session secret and invalidate existing sessions if the recovery location changed trust boundaries. Old cookies are host-only. If restoring at the same host, invalidate stored sessions before serving the recovered database with `TRUNCATE sessions` through your database operator.
5. To move hosts, keep the old instance intact until checks pass. Change the operator-managed live configuration, proxy, certificates and DNS. A domain change needs updated runtime API origin, CORS origins, and TLS. Test with the new hostname before switching traffic. Retain the old read-only snapshot through the rollback window.

If archive validation or the DB load fails, investigate and provision a clean target for retry. A restored DB and failed final media rename leave the target unusable until the verified image archive has been placed under the configured root. The old live data remains available for recovery.
