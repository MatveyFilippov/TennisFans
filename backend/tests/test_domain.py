from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import combinations
from uuid import UUID

import pytest

from tennisfans.core.errors import Problem
from tennisfans.domain.elo import Event, replay
from tennisfans.domain.permissions import (
    Role,
    require_admin,
    require_manager,
    require_opponent,
    require_participant,
    require_resolver,
)
from tennisfans.domain.schedule import (
    Format,
    TeamMode,
    groups_of,
    knockout,
    rotating,
    round_robin,
    validate_capacity,
)
from tennisfans.domain.scoring import (
    Discipline,
    Outcome,
    Rules,
    Score,
    ScoreFormat,
    SetScore,
    ShortFinish,
    score_totals,
    validate_score,
)
from tennisfans.domain.standings import Result, knockout_band, table

A, B, C, D = (UUID(int=index) for index in range(1, 5))
DAY = datetime(2026, 1, 1, tzinfo=UTC)


def score(
    sets: list[tuple[int, ...]], winner: int = 0, outcome: Outcome = Outcome.COMPETITIVE
) -> Score:
    return Score.model_validate(
        {
            "winner": winner,
            "outcome": outcome,
            "sets": [
                dict(zip(["a", "b", "tiebreak_a", "tiebreak_b"], line, strict=False))
                for line in sets
            ],
        }
    )


@pytest.mark.parametrize(
    ("rules", "sets", "win", "outcome", "stats"),
    [
        (Rules(), [(6, 4), (7, 6, 8, 6)], 0, Outcome.COMPETITIVE, (2, 0, 13, 10)),
        (Rules(), [(0, 6), (6, 0), (2, 6)], 1, Outcome.COMPETITIVE, (1, 2, 8, 12)),
        (
            Rules(deciding_match_tiebreak=True),
            [(6, 0), (0, 6), (11, 9)],
            0,
            Outcome.COMPETITIVE,
            (2, 1, 6, 6),
        ),
        (
            Rules(deciding_match_tiebreak=True),
            [(6, 0), (0, 6), (8, 8)],
            1,
            Outcome.RETIREMENT,
            (1, 1, 6, 6),
        ),
        (Rules(format=ScoreFormat.SINGLE_SET), [(5, 7)], 1, Outcome.COMPETITIVE, (0, 1, 5, 7)),
        (Rules(format=ScoreFormat.SHORT_MATCH), [(3, 0)], 0, Outcome.COMPETITIVE, (1, 0, 3, 0)),
        (Rules(format=ScoreFormat.SHORT_MATCH), [(3, 1)], 0, Outcome.COMPETITIVE, (1, 0, 3, 1)),
        (Rules(format=ScoreFormat.SHORT_MATCH), [(3, 2)], 0, Outcome.COMPETITIVE, (1, 0, 3, 2)),
        (
            Rules(format=ScoreFormat.SHORT_MATCH, short_finish=ShortFinish.TIEBREAK),
            [(2, 3, 9, 11)],
            1,
            Outcome.COMPETITIVE,
            (0, 1, 2, 3),
        ),
        (
            Rules(format=ScoreFormat.SHORT_MATCH, short_finish=ShortFinish.WIN_BY_TWO),
            [(4, 2)],
            0,
            Outcome.COMPETITIVE,
            (1, 0, 4, 2),
        ),
        (
            Rules(format=ScoreFormat.SHORT_MATCH, short_finish=ShortFinish.WIN_BY_TWO),
            [(3, 3)],
            0,
            Outcome.RETIREMENT,
            (0, 0, 3, 3),
        ),
        (Rules(format=ScoreFormat.SHORT_MATCH), [(2, 2)], 0, Outcome.RETIREMENT, (0, 0, 2, 2)),
        (Rules(), [(6, 6)], 1, Outcome.RETIREMENT, (0, 0, 6, 6)),
        (Rules(), [(5, 4)], 1, Outcome.RETIREMENT, (0, 0, 5, 4)),
        (Rules(), [], 0, Outcome.WALKOVER, (0, 0, 0, 0)),
        (Rules(), [], 1, Outcome.FORFEIT, (0, 0, 0, 0)),
    ],
)
def test_valid_scores(rules, sets, win, outcome, stats):
    result = score(sets, win, outcome)
    validate_score(rules, result, tournament=True)
    assert score_totals(rules, result) == stats


@pytest.mark.parametrize(
    ("rules", "sets", "winner", "outcome", "tournament"),
    [
        (Rules(), [(6, 5), (6, 2)], 0, Outcome.COMPETITIVE, False),
        (Rules(), [(6, 2)], 0, Outcome.COMPETITIVE, False),
        (Rules(), [(6, 2), (6, 2)], 1, Outcome.COMPETITIVE, False),
        (Rules(), [(6, 2), (6, 2), (6, 2)], 0, Outcome.COMPETITIVE, True),
        (Rules(), [(6, 2), (4, 6, 2)], 0, Outcome.COMPETITIVE, True),
        (Rules(), [(6, 2), (7, 6, 6, 8)], 0, Outcome.COMPETITIVE, True),
        (Rules(), [(6, 2), (7, 6, 12, 3)], 0, Outcome.COMPETITIVE, True),
        (Rules(), [(6, 2), (6, 4, 7, 4)], 0, Outcome.COMPETITIVE, True),
        (Rules(), [(6, 4), (4, 6), (9, 9)], 0, Outcome.COMPETITIVE, True),
        (Rules(), [(6, 9)], 0, Outcome.RETIREMENT, True),
        (Rules(), [(3, 4), (1, 0)], 0, Outcome.RETIREMENT, True),
        (Rules(), [(6, 7, 6, 8), (2, 4, 7, 3)], 1, Outcome.RETIREMENT, True),
        (Rules(format=ScoreFormat.SINGLE_SET), [(6, 0)], 0, Outcome.RETIREMENT, True),
        (
            Rules(format=ScoreFormat.SHORT_MATCH, short_finish=ShortFinish.WIN_BY_TWO),
            [(3, 2)],
            0,
            Outcome.COMPETITIVE,
            False,
        ),
        (Rules(), [(6, 1)], 0, Outcome.WALKOVER, True),
        (Rules(), [], 0, Outcome.WALKOVER, False),
    ],
)
def test_reject_impossible_scores(rules, sets, winner, outcome, tournament):
    with pytest.raises(Problem):
        validate_score(rules, score(sets, winner, outcome), tournament=tournament)


def test_schema_rejects_invalid_games_and_config():
    with pytest.raises(ValueError, match="greater than or equal"):
        SetScore(a=-1, b=2)
    with pytest.raises(ValueError, match="requires a standard match"):
        Rules(format=ScoreFormat.SINGLE_SET, deciding_match_tiebreak=True)


def test_precise_replay_orders_events_and_uses_average():
    first = Event(A, DAY, (A,), (B,), 0)
    second = Event(B, DAY, (A, C), (B, D), 1)
    third = Event(C, DAY + timedelta(days=1), (A,), (D,), 1)
    points = list(replay([third, second, first]))
    assert points == list(replay([first, second, third]))
    assert points[0].rating_after == Decimal(1516)
    assert points[1].rating_after == Decimal(1484)
    assert points[2].delta == points[3].delta == Decimal("-16.736306793522")
    assert points[4].delta == points[5].delta == -points[2].delta
    assert next(replay([second], 16)).delta == Decimal(-8)
    assert list(replay([])) == []


@pytest.mark.parametrize("count", [4, 5, 6, 7, 8, 11, 16, 24, 64])
def test_rotating_players_balanced(count):
    players = [UUID(int=i) for i in range(count)]
    rounds = rotating(players, 929092)
    assert rounds == rotating(players, 929092)
    by_player = Counter()
    partnership = Counter()
    opposition = Counter()
    for day in rounds:
        played = [p for a, b in day for p in a + b]
        assert len(played) == len(set(played)) == count - count % 4
        by_player.update(played)
        for a, b in day:
            partnership.update([frozenset(a), frozenset(b)])
            opposition.update(frozenset((p, q)) for p in a for q in b)
    assert len(by_player) == count and len(set(by_player.values())) == 1
    assert max(partnership.values()) <= 3
    assert max(opposition.values()) <= 6
    if count == 4:
        assert len(partnership) == len(opposition) == 6


def test_round_robin_and_seed_slots():
    players = [A, B, C, D, UUID(int=5)]
    grid = round_robin(players, 2)
    assert len(grid) == 10
    assert Counter(frozenset(pair) for day in grid for pair in day) == {
        frozenset(pair): 2 for pair in combinations(players, 2)
    }
    assert groups_of(players, 2) == [[players[i] for i in (0, 3, 4)], [players[i] for i in (1, 2)]]
    for count in (2, 3, 4, 5, 8, 9, 32):
        nodes = knockout(count)
        assert len(nodes) == count - 1
        sources = [item for node in nodes for item in (node.a, node.b)]
        assert {item.index for item in sources if item.kind == "seed"} == set(range(count))
        assert {item.index for item in sources if item.kind == "fixture"} == set(range(count - 2))
    assert knockout_band(1, 3) == (5, 8)
    assert knockout_band(3, 3) == (2, 2)


@pytest.mark.parametrize(
    ("discipline", "format_", "mode", "capacity", "groups", "qualifiers", "valid"),
    [
        (Discipline.SINGLES, Format.ROUND_ROBIN, None, 2, None, None, True),
        (Discipline.SINGLES, Format.ROUND_ROBIN, TeamMode.FIXED_TEAMS, 2, None, None, False),
        (Discipline.SINGLES, Format.ROUND_ROBIN, None, 1, None, None, False),
        (Discipline.DOUBLES, Format.ROUND_ROBIN, None, 4, None, None, False),
        (Discipline.DOUBLES, Format.ROUND_ROBIN, TeamMode.FIXED_TEAMS, 3, None, None, False),
        (Discipline.DOUBLES, Format.ROUND_ROBIN, TeamMode.FIXED_TEAMS, 5, None, None, False),
        (Discipline.DOUBLES, Format.ROUND_ROBIN, TeamMode.ROTATING_PARTNERS, 5, None, None, True),
        (
            Discipline.DOUBLES,
            Format.SINGLE_ELIMINATION,
            TeamMode.ROTATING_PARTNERS,
            5,
            None,
            None,
            False,
        ),
        (Discipline.DOUBLES, Format.GROUPS_THEN_PLAYOFFS, TeamMode.FIXED_TEAMS, 8, 2, 1, True),
        (Discipline.SINGLES, Format.GROUPS_THEN_PLAYOFFS, None, 4, 2, 2, False),
        (Discipline.SINGLES, Format.GROUPS_THEN_PLAYOFFS, None, 3, None, None, False),
        (Discipline.SINGLES, Format.SINGLE_ELIMINATION, None, 10, 2, 1, False),
    ],
)
def test_capacity(discipline, format_, mode, capacity, groups, qualifiers, valid):
    arguments = discipline, format_, mode, capacity, groups, qualifiers
    if valid:
        validate_capacity(*arguments)
    else:
        with pytest.raises(Problem):
            validate_capacity(*arguments)


def test_standings_head_to_head_and_ranges():
    rules = Rules(format=ScoreFormat.SINGLE_SET)
    rows = table(
        [A, B, C],
        [
            Result((A,), (B,), rules, score([(6, 4)])),
            Result((B,), (C,), rules, score([(6, 3)])),
        ],
        individual=False,
    )
    assert [row.entry_id for row in rows] == [A, B, C]
    assert [row.rank for row in rows] == [1, 2, 3]
    rows = table(
        [A, B, C],
        [
            Result((A,), (B,), rules, score([(6, 4)])),
            Result((B,), (C,), rules, score([(6, 4)])),
            Result((C,), (A,), rules, score([(6, 4)])),
        ],
        individual=False,
    )
    assert [row.rank for row in rows] == [1, 1, 1]
    assert [row.rank_end for row in rows] == [3, 3, 3]
    rows = table(
        [A, B, C],
        [
            Result((A,), (B,), rules, score([(6, 4)])),
            Result((C,), (A,), rules, score([(6, 4)])),
        ],
        individual=False,
    )
    assert [row.entry_id for row in rows] == [C, A, B]


def test_rotating_tiebreak_does_not_rank_partners_by_head_to_head():
    rules = Rules(format=ScoreFormat.SINGLE_SET)
    rows = table(
        [A, B, C, D],
        [
            Result((A, B), (C, D), rules, score([(6, 4)])),
            Result((B, D), (A, C), rules, score([(6, 4)])),
            Result((A, D), (B, C), rules, score([(6, 4)])),
        ],
        individual=True,
    )
    assert {row.entry_id: (row.wins, row.rank, row.rank_end) for row in rows} == {
        A: (2, 1, 3),
        B: (2, 1, 3),
        D: (2, 1, 3),
        C: (0, 4, 4),
    }


def test_permissions():
    require_admin(Role.ADMIN)
    require_manager(Role.PLAYER, True)
    require_manager(Role.ADMIN, False)
    require_participant(A, (A, B))
    require_resolver(Role.PLAYER, True, False)
    require_resolver(Role.ADMIN, False, True)
    require_opponent(A, B, (A, C), (B, D))
    require_opponent(D, A, (A, C), (B, D))
    for operation, args in [
        (require_admin, (Role.PLAYER,)),
        (require_manager, (Role.PLAYER, False)),
        (require_participant, (A, (B, C))),
        (require_resolver, (Role.PLAYER, False, False)),
        (require_resolver, (Role.PLAYER, True, True)),
        (require_opponent, (A, A, (A, C), (B, D))),
        (require_opponent, (A, None, (A, C), (B, D))),
    ]:
        with pytest.raises(Problem) as error:
            operation(*args)
        assert error.value.status == 403
