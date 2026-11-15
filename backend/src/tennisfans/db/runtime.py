import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from tennisfans.core.config import Settings
from tennisfans.db import models
from tennisfans.db.base import Base

log = logging.getLogger(__name__)
MIGRATION_LOCK = 816570001
DOMAIN_LOCK = 816570002


def engine_for(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.pool_size,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": f"-c timezone=UTC -c statement_timeout={settings.statement_timeout_ms}",
        },
    )


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def lock(db: Session) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": DOMAIN_LOCK})


def migration_config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    config.attributes["connection"] = connection
    return config


def migrate(
    engine: Engine, *, explicit: bool = False, check: bool = False, replay_k: int | None = None
) -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": DOMAIN_LOCK})
        config = migration_config(conn)
        inspector = inspect(conn)
        relations = set(inspector.get_table_names()) | set(inspector.get_view_names())
        relations |= set(inspector.get_materialized_view_names()) | set(
            inspector.get_sequence_names()
        )
        current = MigrationContext.configure(conn).get_current_heads()
        head = ScriptDirectory.from_config(config).get_current_head()
        expected = set(Base.metadata.tables) | {"alembic_version"}

        if not relations:
            if check:
                raise RuntimeError("The schema is empty. Run tennisfans db upgrade first.")
            command.upgrade(config, "head")
            log.info("Installed the initial database schema")
        elif not current or len(current) != 1:
            raise RuntimeError(
                "Schema version missing or ambiguous. Verify the database and restore a consistent backup."
            )
        elif current != (head,):
            if not explicit:
                raise RuntimeError(
                    "Schema revision differs from this build. Verify the revision, back up, and run tennisfans db upgrade for known older versions."
                )
            revision = ScriptDirectory.from_config(config).get_revision(current[0])
            if revision is None:
                raise RuntimeError(
                    "Unknown database revision. Restore a compatible application or backup."
                )
            command.upgrade(config, "head")
            log.info("Upgraded the database schema")
        elif not expected <= relations:
            raise RuntimeError("Schema is incomplete. Restore a consistent backup before starting.")
        if check:
            command.check(config)
        if replay_k is not None:
            from tennisfans.modules.ratings import rebuild

            with Session(bind=conn) as db:
                old_k = db.scalar(select(models.results.RatingConfig.k))
                if old_k != replay_k:
                    rebuild(db, replay_k)
                    db.add(models.accounts.Audit(action="rating.rebuild", details={"k": replay_k}))
                    db.flush()


def check_schema(engine: Engine) -> None:
    migrate(engine, check=True)
