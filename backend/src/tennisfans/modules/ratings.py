from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from tennisfans.db.accounts import User
from tennisfans.db.results import Match, RatingConfig, RatingPoint
from tennisfans.domain.elo import INITIAL_RATING, Event, replay
from tennisfans.domain.scoring import Outcome
from tennisfans.modules.facts import eligible, sides_many


def rebuild(db: Session, k: int) -> None:
    db.flush()
    config = db.get(RatingConfig, 1)
    if config is None:
        db.add(RatingConfig(id=1, k=k))
    else:
        config.k = k
    matches = list(
        db.scalars(select(Match).where(Match.outcome == Outcome.COMPETITIVE, *eligible()))
    )
    sides = sides_many(db, [item.id for item in matches])
    events = [
        Event(item.id, item.played_at, *sides[item.id], item.winner)
        for item in matches
        if item.played_at is not None and item.winner is not None
    ]
    db.execute(delete(RatingPoint))
    latest: dict[UUID, Decimal] = {}
    points = []
    for point in replay(events, k):
        points.append(
            RatingPoint(
                match_id=point.match_id,
                user_id=point.player_id,
                played_at=point.played_at,
                delta=point.delta,
                rating_after=point.rating_after,
            )
        )
        latest[point.player_id] = point.rating_after
    db.add_all(points)
    db.execute(update(User).values(rating=INITIAL_RATING))
    for user in db.scalars(select(User).where(User.id.in_(latest))):
        user.rating = latest[user.id]
    db.flush()
