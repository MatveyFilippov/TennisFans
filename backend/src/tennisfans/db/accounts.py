from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tennisfans.db.base import Base, Created, Identity, Timestamps
from tennisfans.domain.elo import INITIAL_RATING
from tennisfans.domain.permissions import Role


class User(Identity, Timestamps, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str]
    role: Mapped[Role] = mapped_column(default=Role.PLAYER)
    active: Mapped[bool] = mapped_column(default=True)
    reset_expires_at: Mapped[datetime | None]
    rating: Mapped[Decimal] = mapped_column(Numeric(24, 12), default=INITIAL_RATING)

    __table_args__ = (Index("uq_users_username_lower", func.lower(username), unique=True),)


class LoginSession(Created, Base):
    __tablename__ = "sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    restricted: Mapped[bool] = mapped_column(default=False)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    count: Mapped[int]


class Audit(Identity, Created, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[UUID | None] = mapped_column(index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)

    __table_args__ = (Index("ix_audit_events_created_at_id", "created_at", "id"),)


class Notification(Identity, Created, Base):
    __tablename__ = "notifications"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[UUID | None] = mapped_column(ForeignKey("matches.id", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(20))


class Idempotency(Created, Base):
    __tablename__ = "idempotency_keys"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    key: Mapped[UUID] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    match_id: Mapped[UUID | None] = mapped_column(ForeignKey("matches.id", ondelete="SET NULL"))
    resource_id: Mapped[UUID]
