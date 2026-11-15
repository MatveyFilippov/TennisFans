from collections import defaultdict
from dataclasses import asdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tennisfans.api import contracts as dto
from tennisfans.db.accounts import User
from tennisfans.db.competition import (
    Entry,
    Fixture,
    Membership,
    Organizer,
    PlayoffSeed,
    Stage,
    Tournament,
)
from tennisfans.db.media import Media
from tennisfans.db.results import Dispute, Match, RatingPoint
from tennisfans.domain.schedule import TeamMode
from tennisfans.domain.scoring import Rules
from tennisfans.domain.standings import Standing
from tennisfans.modules.brackets import (
    board_for,
    entries_for,
    group_tables,
    playoff_placements,
    standings_for,
)
from tennisfans.modules.facts import result, sets_many, sides_many
from tennisfans.modules.tournaments import Config


def public_users(db: Session, users: list[User]) -> dict[UUID, dto.PublicUser]:
    avatars = {
        user_id: photo
        for user_id, photo in db.execute(
            select(Media.user_id, Media.id).where(Media.user_id.in_([user.id for user in users]))
        )
    }
    return {
        user.id: dto.PublicUser(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            active=user.active,
            rating=float(user.rating),
            avatar_id=avatars.get(user.id),
        )
        for user in users
    }


def users_for(db: Session, ids: set[UUID]) -> dict[UUID, dto.PublicUser]:
    return public_users(db, list(db.scalars(select(User).where(User.id.in_(ids)))))


def points(db: Session, ids: list[UUID]) -> dict[UUID, list[dto.Point]]:
    output: dict[UUID, list[dto.Point]] = defaultdict(list)
    for point in db.scalars(
        select(RatingPoint)
        .where(RatingPoint.user_id.in_(ids))
        .order_by(RatingPoint.played_at, RatingPoint.match_id)
    ):
        output[point.user_id].append(point_view(point))
    return output


def point_view(point: RatingPoint) -> dto.Point:
    return dto.Point(
        match_id=point.match_id,
        user_id=point.user_id,
        played_at=point.played_at,
        rating_after=float(point.rating_after),
        delta=float(point.delta),
    )


def match_views(db: Session, matches: list[Match], *, details: bool = False) -> list[dto.MatchView]:
    ids = [item.id for item in matches]
    if not ids:
        return []
    side_map = sides_many(db, ids)
    users = users_for(db, {user for a, b in side_map.values() for user in a + b})
    sets = sets_many(db, ids)
    dates = {
        fixture.id: (fixture.scheduled_at, tournament_id)
        for fixture, tournament_id in db.execute(
            select(Fixture, Stage.tournament_id)
            .join(Stage)
            .where(
                Fixture.id.in_(
                    [match.fixture_id for match in matches if match.fixture_id is not None]
                )
            )
        )
    }
    disputes: dict[UUID, list[dto.DisputeView]] = defaultdict(list)
    active = set()
    for dispute in db.scalars(
        select(Dispute).where(Dispute.match_id.in_(ids)).order_by(Dispute.created_at, Dispute.id)
    ):
        if details:
            disputes[dispute.match_id].append(dto.DisputeView.model_validate(dispute))
        if dispute.resolved_at is None:
            active.add(dispute.match_id)
    galleries: dict[UUID, list[dto.Photo]] = defaultdict(list)
    ratings: dict[UUID, list[dto.Point]] = defaultdict(list)
    if details:
        for photo in db.scalars(
            select(Media).where(Media.match_id.in_(ids)).order_by(Media.created_at, Media.id)
        ):
            if photo.match_id:
                galleries[photo.match_id].append(dto.Photo.model_validate(photo))
        for point in db.scalars(
            select(RatingPoint).where(RatingPoint.match_id.in_(ids)).order_by(RatingPoint.user_id)
        ):
            ratings[point.match_id].append(point_view(point))
    return [
        dto.MatchView(
            id=match.id,
            category="TOURNAMENT" if match.fixture_id else "FRIENDLY",
            discipline=match.discipline,
            rules=Rules.model_validate(match.rules),
            a=[users[player] for player in side_map[match.id][0]],
            b=[users[player] for player in side_map[match.id][1]],
            score=result(match, sets.get(match.id, [])),
            status=(
                "DISPUTED"
                if match.id in active
                else "BLOCKED"
                if match.blocked
                else "COMPLETED"
                if match.outcome is not None
                else "SCHEDULED"
            ),
            played_at=match.played_at,
            scheduled_at=dates[match.fixture_id][0] if match.fixture_id else None,
            author_id=match.author_id,
            tournament_id=dates[match.fixture_id][1] if match.fixture_id else None,
            version=match.version,
            gallery=galleries[match.id],
            rating=ratings[match.id],
            disputes=disputes[match.id],
        )
        for match in matches
    ]


def tournament_summaries(db: Session, tournaments: list[Tournament]) -> list[dto.TournamentSummary]:
    ids = [t.id for t in tournaments]
    counts = {
        id_: count
        for id_, count in db.execute(
            select(Membership.tournament_id, func.count())
            .where(Membership.tournament_id.in_(ids))
            .group_by(Membership.tournament_id)
        )
    }
    covers = {
        id_: photo
        for id_, photo in db.execute(
            select(Media.tournament_id, Media.id).where(Media.tournament_id.in_(ids), Media.cover)
        )
    }
    return [
        dto.TournamentSummary(
            id=t.id,
            title=t.title,
            description=t.description,
            starts_at=t.starts_at,
            timezone=t.timezone,
            completed_at=t.completed_at,
            status=t.status,
            discipline=t.discipline,
            format=t.format,
            team_mode=t.team_mode,
            capacity=t.capacity,
            accepted=counts.get(t.id, 0),
            applications_open=t.applications_open and t.started_at is None,
            cover_id=covers.get(t.id),
        )
        for t in tournaments
    ]


def tournament_view(db: Session, tournament: Tournament) -> dto.TournamentView:
    info = tournament_summaries(db, [tournament])[0]
    config = Config.model_validate(tournament, from_attributes=True)
    roster = list(
        db.scalars(
            select(Membership.user_id)
            .where(Membership.tournament_id == tournament.id)
            .order_by(Membership.position)
        )
    )
    organizers = list(
        db.scalars(
            select(Organizer.user_id)
            .where(Organizer.tournament_id == tournament.id)
            .order_by(Organizer.created_at, Organizer.user_id)
        )
    )
    users = users_for(db, set(roster + organizers))
    members = entries_for(db, tournament.id)
    rotating = tournament.team_mode == TeamMode.ROTATING_PARTNERS

    def row(item: Standing, is_individual: bool = False) -> dto.StandingView:
        data = asdict(item)
        del data["entry_id"]
        return dto.StandingView(
            players=[
                users[user]
                for user in ((item.entry_id,) if is_individual else members[item.entry_id])
            ],
            **data,
        )

    groups = []
    fixtures = []
    standings: list[dto.StandingView] = []
    placements = []
    qualified: list[UUID] = []
    for stage in db.scalars(
        select(Stage).where(Stage.tournament_id == tournament.id).order_by(Stage.kind)
    ):
        board = board_for(db, stage.id)
        descriptions = {match.id: match for match in match_views(db, list(board.matches.values()))}
        for fi in board.fixtures:
            match = board.matches.get(fi.id)
            fixtures.append(
                dto.FixtureView(
                    id=fi.id,
                    stage=stage.kind,
                    group_id=fi.group_id,
                    round=fi.round,
                    position=fi.position,
                    predecessor_a_id=fi.predecessor_a_id,
                    predecessor_b_id=fi.predecessor_b_id,
                    scheduled_at=fi.scheduled_at,
                    match=descriptions.get(match.id) if match else None,
                )
            )
        if stage.kind == "LEAGUE":
            standings = [
                row(item, rotating)
                for item in standings_for(
                    db,
                    roster if rotating else list(members),
                    board,
                    rotating_partners=rotating,
                )
            ]
        elif stage.kind == "GROUPS":
            groups = [
                dto.GroupView(
                    id=group.id, position=group.position, standings=[row(item) for item in rows]
                )
                for group, rows in group_tables(db, stage, board)
            ]
        else:
            qualified = list(
                db.scalars(select(PlayoffSeed.entry_id).where(PlayoffSeed.stage_id == stage.id))
            )
            if not board.matches or not all(not match.blocked for match in board.matches.values()):
                qualified = (
                    []
                    if groups and all(match.blocked for match in board.matches.values())
                    else qualified
                )
            placements = [
                dto.Placement(players=[users[p] for p in members[entry]], rank=rank, rank_end=end)
                for entry, (rank, end) in playoff_placements(board, len(qualified)).items()
            ]
    if groups and qualified:
        for entry_id, ids in members.items():
            if entry_id not in qualified:
                placements.append(
                    dto.Placement(
                        players=[users[p] for p in ids],
                        rank=len(qualified) + 1,
                        rank_end=len(members),
                    )
                )
    if standings:
        placements = [
            dto.Placement(players=item.players, rank=item.rank, rank_end=item.rank_end)
            for item in standings
        ]
    placements.sort(
        key=lambda item: (item.rank, item.players[0].display_name.lower(), item.players[0].id)
    )
    teams_by_id = (
        list(
            db.scalars(
                select(Entry.id)
                .where(Entry.tournament_id == tournament.id)
                .order_by(Entry.seed_position.asc().nulls_last(), Entry.id)
            )
        )
        if tournament.team_mode == TeamMode.FIXED_TEAMS
        else []
    )
    gallery = [
        dto.Photo.model_validate(photo)
        for photo in db.scalars(
            select(Media)
            .where(Media.tournament_id == tournament.id)
            .order_by(Media.cover.desc(), Media.created_at, Media.id)
        )
    ]
    return dto.TournamentView(
        **info.model_dump(),
        config=config,
        version=tournament.version,
        organizers=[users[x] for x in organizers],
        roster=[users[x] for x in roster],
        teams=[[users[p] for p in members[x]] for x in teams_by_id],
        gallery=gallery,
        standings=standings,
        groups=groups,
        fixtures=fixtures,
        placements=placements,
    )
