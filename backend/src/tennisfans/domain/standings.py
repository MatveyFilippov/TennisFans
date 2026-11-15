from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import groupby
from uuid import UUID

from tennisfans.domain.scoring import Rules, Score, score_totals


@dataclass(slots=True)
class Standing:
    entry_id: UUID
    rank: int = 0
    rank_end: int = 0
    played: int = 0
    wins: int = 0
    losses: int = 0
    sets_won: int = 0
    sets_lost: int = 0
    games_won: int = 0
    games_lost: int = 0

    def record(self, won: bool, sw: int, sl: int, gw: int, gl: int) -> None:
        self.played += 1
        self.wins += int(won)
        self.losses += int(not won)
        self.sets_won += sw
        self.sets_lost += sl
        self.games_won += gw
        self.games_lost += gl

    def tiebreaks(self) -> tuple[int, int, int, int]:
        return (
            self.sets_won - self.sets_lost,
            self.games_won - self.games_lost,
            self.sets_won,
            self.games_won,
        )


@dataclass(frozen=True, slots=True)
class Result:
    a: tuple[UUID, ...]
    b: tuple[UUID, ...]
    rules: Rules
    score: Score


def table(
    entries: Sequence[UUID], results: Iterable[Result], *, individual: bool
) -> list[Standing]:
    by_entry = {entry: Standing(entry) for entry in entries}
    head: dict[tuple[UUID, UUID], int] = defaultdict(int)
    together: set[frozenset[UUID]] = set()
    for match in results:
        sets_a, sets_b, games_a, games_b = score_totals(match.rules, match.score)
        for player in match.a:
            by_entry[player].record(match.score.winner == 0, sets_a, sets_b, games_a, games_b)
            for opponent in match.b:
                if match.score.winner == 0:
                    head[player, opponent] += 1
                else:
                    head[opponent, player] += 1
        if individual:
            together.update((frozenset(match.a), frozenset(match.b)))
        for player in match.b:
            by_entry[player].record(match.score.winner == 1, sets_b, sets_a, games_b, games_a)

    ordered = sorted(by_entry.values(), key=lambda row: row.wins, reverse=True)
    ranked: list[Standing] = []
    for _, tied in groupby(ordered, key=lambda row: row.wins):
        peers = list(tied)
        if len(peers) == 2:
            first, second = (row.entry_id for row in peers)
            wins = head[first, second] - head[second, first]
            if wins and frozenset((first, second)) not in together:
                if wins < 0:
                    peers.reverse()
                for row in peers:
                    row.rank = row.rank_end = len(ranked) + 1
                    ranked.append(row)
                continue
        sorted_peers = sorted(peers, key=lambda row: row.tiebreaks(), reverse=True)
        for _, subgroup in groupby(sorted_peers, key=lambda row: row.tiebreaks()):
            shared = sorted(subgroup, key=lambda row: row.entry_id)
            for row in shared:
                row.rank = len(ranked) + 1
                row.rank_end = len(ranked) + len(shared)
            ranked.extend(shared)
    return ranked


def knockout_band(round_: int, final_round: int) -> tuple[int, int]:
    upper = 2 ** (final_round - round_ + 1)
    return upper // 2 + 1, upper
