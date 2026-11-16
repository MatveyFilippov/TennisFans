from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from uuid import UUID

INITIAL_RATING = Decimal(1500)
QUANTUM = Decimal("0.000000000001")


@dataclass(frozen=True, slots=True)
class Event:
    match_id: UUID
    played_at: datetime
    a: tuple[UUID, ...]
    b: tuple[UUID, ...]
    winner: int


@dataclass(frozen=True, slots=True)
class Point:
    match_id: UUID
    played_at: datetime
    player_id: UUID
    rating_after: Decimal
    delta: Decimal


def replay(events: Iterable[Event], k: int = 32) -> Iterator[Point]:
    ratings: dict[UUID, Decimal] = {}
    with localcontext() as ctx:
        ctx.prec = 44
        for event in sorted(events, key=lambda item: (item.played_at, item.match_id)):
            left = [ratings.get(player, INITIAL_RATING) for player in event.a]
            right = [ratings.get(player, INITIAL_RATING) for player in event.b]
            difference = sum(right, Decimal(0)) / len(right) - sum(left, Decimal(0)) / len(left)
            expected = 1 / (1 + Decimal(10) ** (difference / 400))
            delta = k * (int(event.winner == 0) - expected)
            for players, change in ((event.a, delta), (event.b, -delta)):
                for player in players:
                    after = ratings.get(player, INITIAL_RATING) + change
                    ratings[player] = after
                    yield Point(
                        event.match_id,
                        event.played_at,
                        player,
                        after.quantize(QUANTUM, rounding=ROUND_HALF_EVEN),
                        change.quantize(QUANTUM, rounding=ROUND_HALF_EVEN),
                    )
