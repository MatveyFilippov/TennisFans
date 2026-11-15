from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from random import Random
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tennisfans.db.base import now
from tennisfans.db.competition import (
    Entry,
    EntryMember,
    Fixture,
    Group,
    GroupEntry,
    Membership,
    PlayoffSeed,
    RotationSlot,
    Stage,
    Tournament,
)
from tennisfans.db.results import Dispute, Match
from tennisfans.domain.schedule import (
    Format,
    Seeding,
    Source,
    Status,
    TeamMode,
    groups_of,
    knockout,
    rotating,
    round_robin,
)
from tennisfans.domain.scoring import Rules
from tennisfans.domain.standings import Result, Standing, knockout_band, table
from tennisfans.modules.facts import (
    create_match,
    purge_match,
    record_audit,
    result,
    sets_many,
    sides_many,
)


def entries_for(db: Session, tournament_id: UUID) -> dict[UUID, tuple[UUID, ...]]:
    members: dict[UUID, list[UUID]] = defaultdict(list)
    for entry, player in db.execute(
        select(EntryMember.entry_id, EntryMember.user_id)
        .where(EntryMember.tournament_id == tournament_id)
        .order_by(EntryMember.user_id)
    ):
        members[entry].append(player)
    return {key: tuple(players) for key, players in members.items()}


def stage_for(db: Session, tournament_id: UUID, kind: str) -> Stage | None:
    return db.scalar(select(Stage).where(Stage.tournament_id == tournament_id, Stage.kind == kind))


def _stage(db: Session, tournament: Tournament, kind: str) -> Stage:
    stage = Stage(tournament_id=tournament.id, kind=kind)
    db.add(stage)
    db.flush()
    return stage


def _fixture(
    db: Session,
    tournament: Tournament,
    stage: Stage,
    round_: int,
    position: int,
    **refs: UUID | None,
) -> Fixture:
    item = Fixture(
        stage_id=stage.id,
        round=round_,
        position=position,
        scheduled_at=tournament.starts_at
        + timedelta(minutes=(round_ - 1) * tournament.slot_minutes),
        **refs,
    )
    db.add(item)
    db.flush()
    return item


def _league(
    db: Session,
    tournament: Tournament,
    stage: Stage,
    seeded: list[UUID],
    members: dict[UUID, tuple[UUID, ...]],
    group_id: UUID | None = None,
) -> None:
    rules = Rules.model_validate(tournament.rules_snapshot)
    is_rotation = tournament.team_mode == TeamMode.ROTATING_PARTNERS
    if is_rotation:
        player_entries = {players[0]: entry for entry, players in members.items()}
        schedule = [
            [
                (tuple(player_entries[p] for p in a), tuple(player_entries[p] for p in b))
                for a, b in round_
            ]
            for round_ in rotating(list(player_entries), tournament.seed)
        ]
    else:
        schedule = [
            [((a,), (b,)) for a, b in round_] for round_ in round_robin(seeded, tournament.cycles)
        ]
    for round_number, day in enumerate(schedule, 1):
        for position, (a, b) in enumerate(day, 1):
            entry_a, entry_b = (None, None) if is_rotation else (a[0], b[0])
            fixture = _fixture(
                db,
                tournament,
                stage,
                round_number,
                position,
                group_id=group_id,
                seed_a_id=entry_a,
                seed_b_id=entry_b,
                entry_a_id=entry_a,
                entry_b_id=entry_b,
            )
            if is_rotation:
                db.add_all(
                    [
                        RotationSlot(fixture_id=fixture.id, entry_id=entry_id, side=side)
                        for side, entries in enumerate((a, b))
                        for entry_id in entries
                    ]
                )
            players_a = tuple(player for entry in a for player in members[entry])
            players_b = tuple(player for entry in b for player in members[entry])
            create_match(db, tournament.discipline, rules, players_a, players_b, fixture.id)


def _playoff(db: Session, tournament: Tournament, seeded: list[UUID], offset: int = 0) -> None:
    stage = _stage(db, tournament, "PLAYOFF")
    db.add_all(
        [
            PlayoffSeed(stage_id=stage.id, position=i, entry_id=entry)
            for i, entry in enumerate(seeded)
        ]
    )
    nodes: list[Fixture] = []

    def slot(source: Source, side: str) -> dict[str, UUID]:
        if source.kind == "seed":
            return {f"seed_{side}_id": seeded[source.index]}
        return {f"predecessor_{side}_id": nodes[source.index].id}

    for node in knockout(len(seeded)):
        fixture = _fixture(
            db,
            tournament,
            stage,
            node.round,
            node.position,
            **slot(node.a, "a"),
            **slot(node.b, "b"),
        )
        fixture.scheduled_at += timedelta(minutes=offset * tournament.slot_minutes)
        nodes.append(fixture)


def start(db: Session, tournament: Tournament) -> bool:
    roster = list(
        db.scalars(
            select(Membership.user_id)
            .where(Membership.tournament_id == tournament.id)
            .order_by(Membership.position)
        )
    )
    members = entries_for(db, tournament.id)
    fixed = tournament.team_mode == TeamMode.FIXED_TEAMS
    if len(roster) != tournament.capacity or (
        fixed
        and (len(members) * 2 != len(roster) or any(len(team) != 2 for team in members.values()))
    ):
        tournament.status = Status.ACTION_REQUIRED
        tournament.version += 1
        record_audit(db, "tournament.action_required", tournament.id)
        return False

    tournament.rules_snapshot = tournament.rules
    tournament.status = Status.ACTIVE
    tournament.started_at = now()
    tournament.version += 1
    if not fixed:
        for player in roster:
            entry = Entry(tournament_id=tournament.id)
            db.add(entry)
            db.flush()
            db.add(EntryMember(tournament_id=tournament.id, user_id=player, entry_id=entry.id))
            members[entry.id] = (player,)

    order = {player: i for i, player in enumerate(roster)}
    seeded = sorted(
        members, key=lambda entry_id: min(order[player] for player in members[entry_id])
    )
    if tournament.seeding == Seeding.SEEDED_DRAW:
        Random(tournament.seed).shuffle(seeded)  # noqa: S311 - public draw
    for index, entry_id in enumerate(seeded, 1):
        seeded_entry = db.get(Entry, entry_id)
        if seeded_entry is not None:
            seeded_entry.seed_position = index

    if tournament.format == Format.ROUND_ROBIN:
        _league(db, tournament, _stage(db, tournament, "LEAGUE"), seeded, members)
    elif tournament.format == Format.SINGLE_ELIMINATION:
        _playoff(db, tournament, seeded)
    else:
        stage = _stage(db, tournament, "GROUPS")
        for number, entries in enumerate(groups_of(seeded, tournament.group_count or 2), 1):
            group = Group(stage_id=stage.id, position=number)
            db.add(group)
            db.flush()
            db.add_all([GroupEntry(group_id=group.id, entry_id=entry) for entry in entries])
            _league(db, tournament, stage, entries, members, group.id)
    record_audit(db, "tournament.start", tournament.id, seed=tournament.seed)
    reconcile(db, tournament)
    return True


@dataclass
class Board:
    fixtures: list[Fixture]
    matches: dict[UUID, Match]
    disputed: set[UUID]

    def resolved(self, fixture: Fixture) -> Match | None:
        match = self.matches.get(fixture.id)
        if match and match.outcome and not match.blocked and match.id not in self.disputed:
            return match
        return None

    def temporary(self, fixture_id: UUID) -> bool:
        match = self.matches.get(fixture_id)
        return bool(match and (match.blocked or match.id in self.disputed))


def board_for(db: Session, stage_id: UUID) -> Board:
    fixtures = list(
        db.scalars(
            select(Fixture)
            .where(Fixture.stage_id == stage_id)
            .order_by(Fixture.round, Fixture.position, Fixture.id)
        )
    )
    matches = {
        match.fixture_id: match
        for match in db.scalars(
            select(Match).where(Match.fixture_id.in_([fixture.id for fixture in fixtures]))
        )
        if match.fixture_id
    }
    disputed = set(
        db.scalars(
            select(Dispute.match_id).where(
                Dispute.match_id.in_([match.id for match in matches.values()]),
                Dispute.resolved_at.is_(None),
            )
        )
    )
    return Board(fixtures, matches, disputed)


def standings_for(
    db: Session,
    entries: list[UUID],
    board: Board,
    group_id: UUID | None = None,
    *,
    rotating_partners: bool = False,
) -> list[Standing]:
    results = []
    fixtures = [fixture for fixture in board.fixtures if fixture.group_id == group_id]
    relevant = [item for fixture in fixtures if (item := board.resolved(fixture))]
    sets = sets_many(db, [item.id for item in relevant])
    players = sides_many(db, [item.id for item in relevant]) if rotating_partners else {}
    for fixture in fixtures:
        match = board.resolved(fixture)
        if not match:
            continue
        score = result(match, sets.get(match.id, []))
        if score is None:
            continue
        rules = Rules.model_validate(match.rules)
        if rotating_partners:
            results.append(Result(*players[match.id], rules, score))
        elif fixture.entry_a_id and fixture.entry_b_id:
            results.append(Result((fixture.entry_a_id,), (fixture.entry_b_id,), rules, score))
    return table(entries, results, individual=rotating_partners)


def group_tables(db: Session, stage: Stage, board: Board) -> list[tuple[Group, list[Standing]]]:
    groups = list(
        db.scalars(select(Group).where(Group.stage_id == stage.id).order_by(Group.position))
    )
    return [
        (
            group,
            standings_for(
                db,
                list(
                    db.scalars(select(GroupEntry.entry_id).where(GroupEntry.group_id == group.id))
                ),
                board,
                group.id,
            ),
        )
        for group in groups
    ]


def _qualify(
    db: Session, tournament: Tournament, stage: Stage, board: Board
) -> tuple[list[UUID], list[dict[str, object]]]:
    count = tournament.qualifiers or 1
    draw = []
    seeds = []
    for group, rows in group_tables(db, stage, board):
        rng = Random(tournament.seed + group.position)  # noqa: S311 - public draw
        priority = sorted(row.entry_id for row in rows)
        # Frozen entrant seed positions define reproducibility independently of generated UUIDs.
        positions = {
            id_: position
            for id_, position in db.execute(
                select(Entry.id, Entry.seed_position).where(Entry.id.in_(priority))
            )
        }
        priority.sort(key=lambda entry: positions[entry] or 0)
        rng.shuffle(priority)
        priority_by_id = {entry: index for index, entry in enumerate(priority)}
        ranked = sorted(rows, key=lambda row: (row.rank, priority_by_id[row.entry_id]))
        for i, row in enumerate(ranked[:count], 1):
            seeds.append((i, group.position, row.entry_id))
            if row.rank != row.rank_end:
                draw.append({"group": group.position, "rank": i, "entry": str(row.entry_id)})
    return [entry for _, _, entry in sorted(seeds)], draw


@dataclass(frozen=True)
class Impact:
    match_id: UUID
    version: int
    has_result: bool


def _remove(db: Session, match: Match, impacted: list[Impact]) -> None:
    impacted.append(Impact(match.id, match.version, match.outcome is not None))
    purge_match(db, match)


def _delete_playoff(db: Session, stage: Stage, board: Board, impacted: list[Impact]) -> None:
    for match in board.matches.values():
        _remove(db, match, impacted)
    db.execute(delete(Stage).where(Stage.id == stage.id))


def _playoff_progress(
    db: Session, tournament: Tournament, board: Board, impacted: list[Impact]
) -> bool:
    entries = entries_for(db, tournament.id)
    winners: dict[UUID, UUID] = {}
    temporary: set[UUID] = set()
    complete = bool(board.fixtures)
    for fixture in board.fixtures:
        a = fixture.seed_a_id or (
            winners.get(fixture.predecessor_a_id) if fixture.predecessor_a_id else None
        )
        b = fixture.seed_b_id or (
            winners.get(fixture.predecessor_b_id) if fixture.predecessor_b_id else None
        )
        prior = board.matches.get(fixture.id)
        if not a or not b:
            complete = False
            unavailable = [
                predecessor
                for side, predecessor in (
                    (a, fixture.predecessor_a_id),
                    (b, fixture.predecessor_b_id),
                )
                if side is None
            ]
            if unavailable and all(source in temporary for source in unavailable):
                temporary.add(fixture.id)
                if prior:
                    prior.blocked = True
                continue
            if prior:
                _remove(db, prior, impacted)
            fixture.entry_a_id, fixture.entry_b_id = a, b
            continue

        if prior and (fixture.entry_a_id, fixture.entry_b_id) != (a, b):
            _remove(db, prior, impacted)
            prior = None
        fixture.entry_a_id, fixture.entry_b_id = a, b
        if prior is None:
            prior = create_match(
                db,
                tournament.discipline,
                Rules.model_validate(tournament.rules_snapshot),
                entries[a],
                entries[b],
                fixture.id,
            )
        prior.blocked = False
        if prior.id in board.disputed:
            temporary.add(fixture.id)
            complete = False
        elif prior.winner is not None:
            winners[fixture.id] = a if prior.winner == 0 else b
        else:
            complete = False
    return complete


def _restore_league_fixtures(db: Session, tournament: Tournament, board: Board) -> None:
    missing = [fixture for fixture in board.fixtures if fixture.id not in board.matches]
    if not missing:
        return
    entries = entries_for(db, tournament.id)
    rules = Rules.model_validate(tournament.rules_snapshot)
    for fixture in missing:
        if fixture.entry_a_id and fixture.entry_b_id:
            left, right = entries[fixture.entry_a_id], entries[fixture.entry_b_id]
        else:
            slots = list(
                db.scalars(select(RotationSlot).where(RotationSlot.fixture_id == fixture.id))
            )
            left = tuple(
                player for slot in slots if slot.side == 0 for player in entries[slot.entry_id]
            )
            right = tuple(
                player for slot in slots if slot.side == 1 for player in entries[slot.entry_id]
            )
            if len(left) != 2 or len(right) != 2:
                raise RuntimeError("A rotating fixture has lost its structural slots")
        board.matches[fixture.id] = create_match(
            db, tournament.discipline, rules, left, right, fixture.id
        )


def reconcile(db: Session, tournament: Tournament) -> list[Impact]:
    db.flush()
    impacted: list[Impact] = []
    league = stage_for(db, tournament.id, "LEAGUE")
    groups = stage_for(db, tournament.id, "GROUPS")
    playoff = stage_for(db, tournament.id, "PLAYOFF")
    requirements_met = False
    if league:
        schedule = board_for(db, league.id)
        _restore_league_fixtures(db, tournament, schedule)
        requirements_met = bool(schedule.fixtures) and all(
            schedule.resolved(fixture) for fixture in schedule.fixtures
        )
    if groups:
        schedule = board_for(db, groups.id)
        _restore_league_fixtures(db, tournament, schedule)
        group_complete = all(schedule.resolved(fixture) for fixture in schedule.fixtures)
        if not group_complete and playoff:
            board = board_for(db, playoff.id)
            if all(schedule.resolved(fi) or schedule.temporary(fi.id) for fi in schedule.fixtures):
                for match in board.matches.values():
                    match.blocked = True
            else:
                _delete_playoff(db, playoff, board, impacted)
            playoff = None
        if group_complete:
            seeded, draw = _qualify(db, tournament, groups, schedule)
            if playoff:
                old = list(
                    db.scalars(
                        select(PlayoffSeed.entry_id)
                        .where(PlayoffSeed.stage_id == playoff.id)
                        .order_by(PlayoffSeed.position)
                    )
                )
                if old != seeded:
                    _delete_playoff(db, playoff, board_for(db, playoff.id), impacted)
                    playoff = None
            if playoff is None:
                _playoff(db, tournament, seeded, max(fi.round for fi in schedule.fixtures))
                playoff = stage_for(db, tournament.id, "PLAYOFF")
                record_audit(
                    db,
                    "tournament.qualify",
                    tournament.id,
                    draw=draw,
                    seed=tournament.seed,
                    qualifiers=[str(item) for item in seeded],
                )
    if playoff:
        requirements_met = _playoff_progress(db, tournament, board_for(db, playoff.id), impacted)

    if requirements_met and tournament.status != Status.COMPLETED:
        tournament.status = Status.COMPLETED
        tournament.completed_at = now()
        tournament.version += 1
        record_audit(db, "tournament.complete", tournament.id)
    elif not requirements_met and tournament.status == Status.COMPLETED:
        tournament.status = Status.ACTIVE
        tournament.completed_at = None
        tournament.version += 1
        record_audit(db, "tournament.reopen", tournament.id)
    db.flush()
    return impacted


def playoff_placements(board: Board, entry_count: int) -> dict[UUID, tuple[int, int]]:
    places = {}
    final_round = max((fixture.round for fixture in board.fixtures), default=0)
    for fixture in board.fixtures:
        match = board.resolved(fixture)
        a, b = fixture.entry_a_id, fixture.entry_b_id
        if match is None or a is None or b is None:
            continue
        winner, loser = (a, b) if match.winner == 0 else (b, a)
        low, high = knockout_band(fixture.round, final_round)
        places[loser] = (low, min(high, entry_count))
        if fixture.round == final_round:
            places[winner] = (1, 1)
    return places
