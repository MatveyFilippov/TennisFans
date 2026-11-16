from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tennisfans.api import contracts as dto
from tennisfans.db.accounts import User
from tennisfans.db.competition import Membership, Tournament
from tennisfans.db.media import Media
from tennisfans.db.results import Match, RatingPoint, SidePlayer
from tennisfans.domain.scoring import Discipline, Rules, score_totals
from tennisfans.modules.facts import eligible, load_user, result, sets_many, sides_many
from tennisfans.modules.views import (
    match_views,
    points,
    public_users,
    tournament_summaries,
    tournament_view,
)


def played(db: Session, user_id: UUID) -> list[tuple[Match, int]]:
    return [
        (match, side)
        for match, side in db.execute(
            select(Match, SidePlayer.side)
            .join(SidePlayer, Match.id == SidePlayer.match_id)
            .where(SidePlayer.user_id == user_id, *eligible())
            .order_by(Match.played_at, Match.id)
        )
    ]


def _totals(db: Session, matches: list[tuple[Match, int]]) -> dict[Discipline | None, dto.Totals]:
    sets = sets_many(db, [item.id for item, _ in matches])
    totals = {category: dto.Totals() for category in (None, Discipline.SINGLES, Discipline.DOUBLES)}
    for match, side in matches:
        score = result(match, sets.get(match.id, []))
        if score is None:
            continue
        sa, sb, ga, gb = score_totals(Rules.model_validate(match.rules), score)
        if side == 1:
            sa, sb, ga, gb = sb, sa, gb, ga
        for category in (None, match.discipline):
            row = totals[category]
            won = side == score.winner
            row.matches += 1
            row.wins += int(won)
            row.losses += int(not won)
            row.win_rate = row.wins / row.matches
            row.sets_won += sa
            row.sets_lost += sb
            row.games_won += ga
            row.games_lost += gb
            row.current_streak = row.current_streak + 1 if won else 0
            row.longest_streak = max(row.longest_streak, row.current_streak)
    return totals


def player_stats(db: Session, player_id: UUID) -> dto.PlayerStats:
    user = load_user(db, player_id)
    matches = played(db, player_id)
    total = _totals(db, matches)
    tournaments = list(
        db.scalars(
            select(Tournament)
            .join(Membership)
            .where(Membership.user_id == player_id)
            .order_by(Tournament.starts_at.desc(), Tournament.id)
        )
    )
    info = tournament_summaries(db, tournaments)
    finishes = []
    for item, summary in zip(tournaments, info, strict=True):
        placement = None
        if item.started_at:
            placement = next(
                (
                    row
                    for row in tournament_view(db, item).placements
                    if any(player.id == player_id for player in row.players)
                ),
                None,
            )
        finishes.append(
            dto.TournamentFinish(
                tournament=summary,
                rank=placement.rank if placement else None,
                rank_end=placement.rank_end if placement else None,
            )
        )
    recent = [match for match, _ in reversed(matches[-10:])]
    gallery = [
        dto.Photo.model_validate(photo)
        for photo in db.scalars(
            select(Media)
            .where(Media.match_id.in_([match.id for match in recent]))
            .order_by(Media.created_at.desc(), Media.id)
            .limit(24)
        )
    ]
    return dto.PlayerStats(
        player=public_users(db, [user])[player_id],
        overall=total[None],
        singles=total[Discipline.SINGLES],
        doubles=total[Discipline.DOUBLES],
        recent=match_views(db, recent),
        gallery=gallery,
        tournaments=finishes,
        history=points(db, [player_id]).get(player_id, []),
    )


def pair(db: Session, a: UUID, b: UUID) -> dto.PairStats:
    all_ = played(db, a)
    sides = sides_many(db, [match.id for match, _ in all_])
    opponents, partners = [], []
    a_wins = partner_wins = 0
    for match, side in reversed(all_):
        if b in sides[match.id][side]:
            partners.append(match)
            partner_wins += int(match.winner == side)
        elif b in sides[match.id][1 - side]:
            opponents.append(match)
            a_wins += int(match.winner == side)
    return dto.PairStats(
        a=player_stats(db, a),
        b=player_stats(db, b),
        opponent_matches=match_views(db, opponents[:30]),
        partner_matches=match_views(db, partners[:30]),
        opponent_total=len(opponents),
        partner_total=len(partners),
        a_wins=a_wins,
        b_wins=len(opponents) - a_wins,
        partner_wins=partner_wins,
    )


def leaderboard(db: Session, q: str, offset: int, limit: int) -> dto.Page[dto.Leader]:
    ranked = select(
        User.id.label("id"), func.rank().over(order_by=User.rating.desc()).label("rank")
    ).subquery()
    query = select(User, ranked.c.rank).join(ranked, ranked.c.id == User.id)
    if q:
        query = query.where(
            User.username.icontains(q, autoescape=True)
            | User.display_name.icontains(q, autoescape=True)
        )
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.execute(query.order_by(User.rating.desc(), User.id).offset(offset).limit(limit)).all()
    users = public_users(db, [user for user, _ in rows])
    ids = set(users)
    count = {
        player: (matches, wins)
        for player, matches, wins in db.execute(
            select(
                SidePlayer.user_id,
                func.count(),
                func.count().filter(Match.winner == SidePlayer.side),
            )
            .join(Match, SidePlayer.match_id == Match.id)
            .where(SidePlayer.user_id.in_(ids), *eligible())
            .group_by(SidePlayer.user_id)
        )
    }
    limited = (
        select(
            RatingPoint.user_id.label("user_id"),
            RatingPoint.rating_after.label("rating"),
            func.row_number()
            .over(
                partition_by=RatingPoint.user_id,
                order_by=(RatingPoint.played_at.desc(), RatingPoint.match_id.desc()),
            )
            .label("position"),
        )
        .where(RatingPoint.user_id.in_(ids))
        .subquery()
    )
    trends: dict[UUID, list[float]] = {}
    for player, rating in db.execute(
        select(limited.c.user_id, limited.c.rating)
        .where(limited.c.position <= 12)
        .order_by(limited.c.position.desc())
    ):
        trends.setdefault(player, []).append(float(rating))
    out = []
    for user, rank in rows:
        matches, wins = count.get(user.id, (0, 0))
        out.append(
            dto.Leader(
                **users[user.id].model_dump(),
                rank=rank,
                matches=matches,
                wins=wins,
                losses=matches - wins,
                win_rate=wins / matches if matches else 0,
                trend=trends.get(user.id, []),
            )
        )
    return dto.Page(items=out, total=total)
