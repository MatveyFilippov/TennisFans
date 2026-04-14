from .base import ENGINE
from utils.datetime_utils import UTC_TIMEZONE, utc_datetime
from datetime import datetime
from typing import Optional, Type
import sqlalchemy
from sqlalchemy import Column, CheckConstraint, ForeignKey, Index, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import declarative_base


EntityBase = declarative_base()


class DateTimeUTC(TypeDecorator):
    impl = sqlalchemy.DateTime(True)
    cache_ok = True

    @property
    def python_type(self) -> Type[datetime]:
        return datetime

    def process_bind_param(self, value: Optional[datetime], dialect: sqlalchemy.Dialect):
        if value is None:
            return None
        if not isinstance(value, self.python_type):
            raise ValueError(f"Expected {self.python_type} object, not {type(value)}")

        return utc_datetime(value)

    def process_result_value(self, value: Optional[datetime], dialect: sqlalchemy.Dialect):
        if value is None:
            return None

        return utc_datetime(value)

    def process_literal_param(self, value: Optional[datetime], dialect: sqlalchemy.Dialect) -> str:
        return "NULL" if value is None else f"'{utc_datetime(value)}'"


class PlayerEntity(EntityBase):
    __tablename__ = "players"

    id = Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = Column(sqlalchemy.Text, nullable=False)
    registered_at = Column(DateTimeUTC, nullable=False, default=lambda: datetime.now(UTC_TIMEZONE))

    __table_args__ = (
        Index("idx_players_registered_at", registered_at),
    )


class TourEntity(EntityBase):
    __tablename__ = "tours"

    id = Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = Column(sqlalchemy.Text, nullable=False)
    started_at = Column(DateTimeUTC, nullable=False, default=lambda: datetime.now(UTC_TIMEZONE))
    ended_at = Column(DateTimeUTC, nullable=True)

    __table_args__ = (
        CheckConstraint("ended_at IS NULL OR started_at < ended_at", name="check_tour_started_before_ended"),
    )


class PlayersPairEntity(EntityBase):
    __tablename__ = "players_pairs"

    id = Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    player1_id = Column(sqlalchemy.Integer, ForeignKey("players.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    player2_id = Column(sqlalchemy.Integer, ForeignKey("players.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint(player1_id, player2_id, name="uq_players_pairs_players_id"),
        Index("idx_players_pairs_player1_id", player1_id),
        Index("idx_players_pairs_player2_id", player2_id),
    )


class MatchEntity(EntityBase):
    __tablename__ = "matches"

    id = Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    played_at = Column(DateTimeUTC, nullable=False, default=lambda: datetime.now(UTC_TIMEZONE))
    players_pair_id_1 = Column(sqlalchemy.Integer, ForeignKey("players_pairs.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    players_pair_id_2 = Column(sqlalchemy.Integer, ForeignKey("players_pairs.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    score_players_pair_1 = Column(sqlalchemy.Integer, nullable=False)
    score_players_pair_2 = Column(sqlalchemy.Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("players_pair_id_1 != players_pair_id_2", name="check_unique_players_pair_in_match"),
        CheckConstraint("score_players_pair_1 >= 0", name="check_score_players_pair_1_positive"),
        CheckConstraint("score_players_pair_2 >= 0", name="check_score_players_pair_2_positive"),
        Index("idx_matches_players_pair_id_1", players_pair_id_1),
        Index("idx_matches_players_pair_id_2", players_pair_id_2),
    )


EntityBase.metadata.create_all(ENGINE)
