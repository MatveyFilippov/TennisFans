from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tennisfans.db.base import Base, Created, Identity, Timestamps
from tennisfans.domain.scoring import Discipline, Outcome


class Match(Identity, Timestamps, Base):
    __tablename__ = "matches"
    fixture_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), unique=True
    )
    discipline: Mapped[Discipline]
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB)
    played_at: Mapped[datetime | None] = mapped_column(index=True)
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    winner: Mapped[int | None]
    outcome: Mapped[Outcome | None]
    blocked: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        CheckConstraint("winner IN (0,1)", name="winner"),
        CheckConstraint(
            "(outcome IS NULL AND played_at IS NULL AND winner IS NULL) OR "
            "(outcome IS NOT NULL AND played_at IS NOT NULL AND winner IS NOT NULL AND author_id IS NOT NULL)",
            name="result",
        ),
    )


class MatchSide(Base):
    __tablename__ = "match_sides"
    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    side: Mapped[int] = mapped_column(primary_key=True)
    __table_args__ = (CheckConstraint("side IN (0,1)", name="side"),)


class SidePlayer(Base):
    __tablename__ = "match_side_players"
    match_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    side: Mapped[int]
    __table_args__ = (
        ForeignKeyConstraint(
            ["match_id", "side"], ["match_sides.match_id", "match_sides.side"], ondelete="CASCADE"
        ),
    )


class MatchSet(Base):
    __tablename__ = "match_sets"
    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    a: Mapped[int]
    b: Mapped[int]
    tiebreak_a: Mapped[int | None]
    tiebreak_b: Mapped[int | None]
    __table_args__ = (
        CheckConstraint("a >= 0 AND b >= 0", name="games"),
        CheckConstraint(
            "(tiebreak_a IS NULL AND tiebreak_b IS NULL) OR "
            "(tiebreak_a IS NOT NULL AND tiebreak_b IS NOT NULL AND tiebreak_a >= 0 AND tiebreak_b >= 0)",
            name="tiebreak",
        ),
        CheckConstraint("position BETWEEN 1 AND 3", name="position"),
    )


class Revision(Identity, Created, Base):
    __tablename__ = "match_result_revisions"
    match_id: Mapped[UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str]
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Dispute(Identity, Created, Base):
    __tablename__ = "disputes"
    match_id: Mapped[UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str]
    resolved_at: Mapped[datetime | None]
    resolver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str | None] = mapped_column(String(12))
    resolution_reason: Mapped[str | None]
    __table_args__ = (
        Index(
            "uq_disputes_open_match",
            "match_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )


class RatingPoint(Base):
    __tablename__ = "rating_events"
    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    played_at: Mapped[datetime]
    rating_after: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    delta: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    __table_args__ = (
        Index("ix_rating_events_user_id_played_at_match_id", "user_id", "played_at", "match_id"),
    )


class RatingConfig(Base):
    __tablename__ = "rating_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    k: Mapped[int]
    __table_args__ = (CheckConstraint("id = 1 AND k BETWEEN 1 AND 100", name="singleton"),)
