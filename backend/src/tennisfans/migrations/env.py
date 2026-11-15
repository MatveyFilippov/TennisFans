from alembic import context
from sqlalchemy import Connection

from tennisfans.db import models as models
from tennisfans.db.base import Base


def run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


run(context.config.attributes["connection"])
