from collections import defaultdict
from uuid import UUID

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.orm import Session

from tennisfans.core.errors import missing
from tennisfans.db.accounts import Audit, User
from tennisfans.db.competition import Fixture, Stage
from tennisfans.db.media import Media, MediaDeletion
from tennisfans.db.results import Dispute, Match, MatchSet, MatchSide, SidePlayer
from tennisfans.domain.schedule import Team
from tennisfans.domain.scoring import Discipline, Rules, Score, Side


def record_audit(
    db: Session, action: str, target_id: UUID, actor_id: UUID | None = None, **details: object
) -> None:
    db.add(Audit(action=action, actor_id=actor_id, target_id=target_id, details=details))


def load_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise missing()
    return user


def sides_many(db: Session, matches: list[UUID]) -> dict[UUID, tuple[Team, Team]]:
    found: dict[UUID, tuple[list[UUID], list[UUID]]] = defaultdict(lambda: ([], []))
    for m, player, side in db.execute(
        select(SidePlayer.match_id, SidePlayer.user_id, SidePlayer.side)
        .where(SidePlayer.match_id.in_(matches))
        .order_by(SidePlayer.user_id)
    ):
        found[m][side].append(player)
    return {key: (tuple(a), tuple(b)) for key, (a, b) in found.items()}


def sides(db: Session, match: Match) -> tuple[Team, Team]:
    return sides_many(db, [match.id])[match.id]


def create_match(
    db: Session,
    discipline: Discipline,
    rules: Rules,
    a: Team,
    b: Team,
    fixture_id: UUID | None = None,
) -> Match:
    match = Match(discipline=discipline, rules=rules.model_dump(mode="json"), fixture_id=fixture_id)
    db.add(match)
    db.flush()
    db.add_all([MatchSide(match_id=match.id, side=0), MatchSide(match_id=match.id, side=1)])
    db.flush()
    for index, players in enumerate((a, b)):
        db.add_all(
            [SidePlayer(match_id=match.id, side=index, user_id=player) for player in players]
        )
    db.flush()
    return match


def sets_many(db: Session, matches: list[UUID]) -> dict[UUID, list[MatchSet]]:
    found: dict[UUID, list[MatchSet]] = defaultdict(list)
    for item in db.scalars(
        select(MatchSet).where(MatchSet.match_id.in_(matches)).order_by(MatchSet.position)
    ):
        found[item.match_id].append(item)
    return found


def result(match: Match, sets: list[MatchSet]) -> Score | None:
    if match.outcome is None or match.winner is None:
        return None
    winner: Side = 0 if match.winner == 0 else 1
    return Score(
        outcome=match.outcome,
        winner=winner,
        sets=[
            {"a": item.a, "b": item.b, "tiebreak_a": item.tiebreak_a, "tiebreak_b": item.tiebreak_b}
            for item in sets
        ],
    )


def open_dispute(db: Session, match_id: UUID) -> Dispute | None:
    return db.scalar(
        select(Dispute).where(Dispute.match_id == match_id, Dispute.resolved_at.is_(None))
    )


def eligible() -> tuple[ColumnElement[bool], ...]:
    return (
        Match.outcome.is_not(None),
        Match.blocked.is_(False),
        ~select(Dispute.id)
        .where(Dispute.match_id == Match.id, Dispute.resolved_at.is_(None))
        .exists(),
    )


def tournament_id_for(db: Session, match: Match) -> UUID | None:
    if match.fixture_id is None:
        return None
    return db.scalar(
        select(Stage.tournament_id).join(Fixture).where(Fixture.id == match.fixture_id)
    )


def delete_photos(db: Session, photos: list[Media]) -> None:
    for photo in photos:
        db.add(MediaDeletion(id=photo.id))
        db.delete(photo)


def purge_match(db: Session, match: Match) -> None:
    delete_photos(db, list(db.scalars(select(Media).where(Media.match_id == match.id))))
    db.execute(delete(Match).where(Match.id == match.id))
    db.flush()
