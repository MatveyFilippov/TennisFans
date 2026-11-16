from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tennisfans.db.base import Base, Created, Identity, Timestamps
from tennisfans.domain.schedule import Format, Seeding, Status, TeamMode
from tennisfans.domain.scoring import Discipline


class Tournament(Identity, Timestamps, Base):
    __tablename__ = "tournaments"
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str]
    starts_at: Mapped[datetime]
    timezone: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    status: Mapped[Status] = mapped_column(default=Status.SCHEDULED)
    discipline: Mapped[Discipline]
    format: Mapped[Format]
    team_mode: Mapped[TeamMode | None]
    capacity: Mapped[int]
    applications_open: Mapped[bool]
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rules_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    group_count: Mapped[int | None]
    qualifiers: Mapped[int | None]
    cycles: Mapped[int]
    seed: Mapped[int]
    seeding: Mapped[Seeding]
    slot_minutes: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        CheckConstraint("capacity >= 2 AND capacity <= 128", name="capacity"),
        CheckConstraint("cycles >= 1 AND cycles <= 3", name="cycles"),
        CheckConstraint("(status = 'COMPLETED') = (completed_at IS NOT NULL)", name="completion"),
        CheckConstraint(
            "(status IN ('ACTIVE','COMPLETED')) = (started_at IS NOT NULL AND rules_snapshot IS NOT NULL)",
            name="started",
        ),
        Index("ix_tournaments_status_starts_at", "status", "starts_at"),
    )


class Organizer(Created, Base):
    __tablename__ = "tournament_organizers"
    tournament_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)


class Membership(Created, Base):
    __tablename__ = "tournament_participants"
    tournament_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    position: Mapped[int]
    __table_args__ = (UniqueConstraint("tournament_id", "position"),)


class Application(Timestamps, Base):
    __tablename__ = "tournament_applications"
    tournament_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))
    __table_args__ = (
        CheckConstraint("status IN ('PENDING','ACCEPTED','REJECTED','WITHDRAWN')", name="status"),
    )


class Stage(Identity, Base):
    __tablename__ = "tournament_stages"
    tournament_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(12))
    __table_args__ = (
        UniqueConstraint("tournament_id", "kind"),
        CheckConstraint("kind IN ('LEAGUE','GROUPS','PLAYOFF')", name="kind"),
    )


class Group(Identity, Base):
    __tablename__ = "tournament_groups"
    stage_id: Mapped[UUID] = mapped_column(ForeignKey("tournament_stages.id", ondelete="CASCADE"))
    position: Mapped[int]
    __table_args__ = (UniqueConstraint("stage_id", "position"),)


class Entry(Identity, Base):
    __tablename__ = "tournament_entries"
    tournament_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    seed_position: Mapped[int | None]
    __table_args__ = (
        UniqueConstraint("tournament_id", "id"),
        UniqueConstraint("tournament_id", "seed_position"),
    )


class EntryMember(Base):
    __tablename__ = "tournament_entry_members"
    tournament_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    entry_id: Mapped[UUID] = mapped_column(index=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tournament_id", "user_id"],
            ["tournament_participants.tournament_id", "tournament_participants.user_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tournament_id", "entry_id"],
            ["tournament_entries.tournament_id", "tournament_entries.id"],
            ondelete="CASCADE",
        ),
    )


class GroupEntry(Base):
    __tablename__ = "tournament_group_entries"
    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournament_groups.id", ondelete="CASCADE"), primary_key=True
    )
    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournament_entries.id", ondelete="CASCADE"), primary_key=True
    )


class Fixture(Identity, Base):
    __tablename__ = "fixtures"
    stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournament_stages.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tournament_groups.id", ondelete="CASCADE"), index=True
    )
    round: Mapped[int]
    position: Mapped[int]
    scheduled_at: Mapped[datetime]
    seed_a_id: Mapped[UUID | None] = mapped_column(ForeignKey("tournament_entries.id"))
    seed_b_id: Mapped[UUID | None] = mapped_column(ForeignKey("tournament_entries.id"))
    predecessor_a_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE")
    )
    predecessor_b_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE")
    )
    entry_a_id: Mapped[UUID | None] = mapped_column(ForeignKey("tournament_entries.id"))
    entry_b_id: Mapped[UUID | None] = mapped_column(ForeignKey("tournament_entries.id"))
    __table_args__ = (
        Index(
            "uq_fixtures_stage_group_round_position",
            "stage_id",
            "group_id",
            "round",
            "position",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("round >= 1 AND position >= 1", name="position"),
        CheckConstraint("seed_a_id IS NULL OR predecessor_a_id IS NULL", name="a_source"),
        CheckConstraint("seed_b_id IS NULL OR predecessor_b_id IS NULL", name="b_source"),
    )


class PlayoffSeed(Base):
    __tablename__ = "playoff_seeds"
    stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("tournament_stages.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("tournament_entries.id"))
    __table_args__ = (UniqueConstraint("stage_id", "entry_id"),)


class RotationSlot(Base):
    __tablename__ = "rotation_slots"
    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), primary_key=True
    )
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("tournament_entries.id"), primary_key=True)
    side: Mapped[int]
    __table_args__ = (CheckConstraint("side IN (0,1)", name="side"),)
