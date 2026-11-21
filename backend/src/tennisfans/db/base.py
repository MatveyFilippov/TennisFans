from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tennisfans.domain.permissions import Role
from tennisfans.domain.schedule import Format, Seeding, Status, TeamMode
from tennisfans.domain.scoring import Discipline, Outcome


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
        }
    )
    type_annotation_map: ClassVar[dict[object, Enum | DateTime]] = {
        datetime: DateTime(timezone=True),
        Role: Enum(Role, native_enum=False, create_constraint=True),
        Format: Enum(Format, native_enum=False, create_constraint=True),
        Seeding: Enum(Seeding, native_enum=False, create_constraint=True),
        Status: Enum(Status, native_enum=False, create_constraint=True),
        TeamMode: Enum(TeamMode, native_enum=False, create_constraint=True),
        Discipline: Enum(Discipline, native_enum=False, create_constraint=True),
        Outcome: Enum(Outcome, native_enum=False, create_constraint=True),
    }


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Created:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Timestamps(Created):
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
