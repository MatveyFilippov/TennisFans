from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from random import Random
from typing import Literal
from uuid import UUID

from tennisfans.core.errors import invalid
from tennisfans.domain.scoring import Discipline

Team = tuple[UUID, ...]


class Format(StrEnum):
    ROUND_ROBIN = "ROUND_ROBIN"
    SINGLE_ELIMINATION = "SINGLE_ELIMINATION"
    GROUPS_THEN_PLAYOFFS = "GROUPS_THEN_PLAYOFFS"


class TeamMode(StrEnum):
    FIXED_TEAMS = "FIXED_TEAMS"
    ROTATING_PARTNERS = "ROTATING_PARTNERS"


class Status(StrEnum):
    SCHEDULED = "SCHEDULED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class Seeding(StrEnum):
    SEED_ORDER = "SEED_ORDER"
    SEEDED_DRAW = "SEEDED_DRAW"


def validate_capacity(
    discipline: Discipline,
    format_: Format,
    mode: TeamMode | None,
    capacity: int,
    groups: int | None,
    qualifiers: int | None,
) -> None:
    entries = capacity
    if discipline == Discipline.SINGLES and mode is not None:
        raise invalid("invalid_configuration", "Singles has no doubles team mode")
    if discipline == Discipline.DOUBLES:
        if capacity < 4 or mode is None:
            raise invalid("invalid_configuration", "Doubles requires a team mode and four players")
        if mode == TeamMode.ROTATING_PARTNERS and format_ != Format.ROUND_ROBIN:
            raise invalid("invalid_configuration", "Rotating partners requires round robin")
        if mode == TeamMode.FIXED_TEAMS:
            if capacity % 2:
                raise invalid("invalid_configuration", "Fixed doubles requires even capacity")
            entries = capacity // 2
    if entries < 2:
        raise invalid("invalid_configuration", "At least two entries are required")
    if format_ == Format.GROUPS_THEN_PLAYOFFS:
        if (
            groups is None
            or qualifiers is None
            or groups < 2
            or qualifiers < 1
            or entries // groups < max(2, qualifiers + 1)
        ):
            raise invalid(
                "invalid_configuration",
                "Each group requires at least two entries and at least one non-qualifier",
            )
    elif groups is not None or qualifiers is not None:
        raise invalid("invalid_configuration", "Group settings require groups and playoffs")


def groups_of[T](entries: Sequence[T], count: int) -> list[list[T]]:
    groups: list[list[T]] = [[] for _ in range(count)]
    for i, entry in enumerate(entries):
        block, offset = divmod(i, count)
        groups[offset if block % 2 == 0 else count - 1 - offset].append(entry)
    return groups


def round_robin[T](entries: Sequence[T], cycles: int = 1) -> list[list[tuple[T, T]]]:
    ring: list[T | None] = list(entries)
    if len(ring) % 2:
        ring.append(None)
    matches = []
    for cycle in range(cycles):
        for _ in range(len(ring) - 1):
            pairings = zip(ring[: len(ring) // 2], reversed(ring[len(ring) // 2 :]), strict=True)
            matches.append(
                [
                    (a, b) if cycle % 2 == 0 else (b, a)
                    for a, b in pairings
                    if a is not None and b is not None
                ]
            )
            ring.insert(1, ring.pop())
    return matches


@dataclass(frozen=True, slots=True)
class Source:
    kind: Literal["seed", "fixture"]
    index: int


@dataclass(frozen=True, slots=True)
class KnockoutNode:
    round: int
    position: int
    a: Source
    b: Source


def knockout(count: int) -> list[KnockoutNode]:
    size = 1 << (count - 1).bit_length()
    order = [0, 1]
    while len(order) < size:
        complement = 2 * len(order) - 1
        order = [slot for seed in order for slot in (seed, complement - seed)]
    slots: list[Source | None] = [Source("seed", seed) if seed < count else None for seed in order]
    nodes: list[KnockoutNode] = []
    round_ = 1
    while len(slots) > 1:
        next_slots: list[Source | None] = []
        for position, (a, b) in enumerate(zip(slots[::2], slots[1::2], strict=True), 1):
            if a is not None and b is not None:
                next_slots.append(Source("fixture", len(nodes)))
                nodes.append(KnockoutNode(round_, position, a, b))
            else:
                next_slots.append(a or b)
        slots = next_slots
        round_ += 1
    return nodes


def _rotation_cost(base: list[int], count: int) -> tuple[int, int, int]:
    partners = [0] * (count // 2 + 1)
    opponents = partners.copy()

    def distance(a: int, b: int) -> int:
        difference = abs(a - b)
        return min(difference, count - difference)

    for i in range(0, len(base), 4):
        a, b, c, d = base[i : i + 4]
        for left, right in ((a, b), (c, d)):
            partners[distance(left, right)] += 1
        for left, right in ((a, c), (a, d), (b, c), (b, d)):
            opponents[distance(left, right)] += 1
    if count % 2 == 0:
        partners[-1] *= 2
        opponents[-1] *= 2
    return (
        sum(value * value for value in partners),
        sum(value * value for value in opponents),
        -sum(value > 0 for value in opponents),
    )


def rotating(players: Sequence[UUID], seed: int) -> list[list[tuple[Team, Team]]]:
    count = len(players)
    rng = Random(seed)  # noqa: S311 - reproducible schedule, no secret
    slots = list(players)
    rng.shuffle(slots)
    if count == 4:
        a, b, c, d = slots
        return [[((a, b), (c, d))], [((a, c), (b, d))], [((a, d), (b, c))]]
    base = list(range(count))
    used = count - count % 4
    candidates = []
    for _ in range(96):
        rng.shuffle(base)
        candidates.append(base[:used])
    best = min(candidates, key=lambda candidate: _rotation_cost(candidate, count))
    rounds: list[list[tuple[Team, Team]]] = []
    for rotation in range(count):
        ordered = [slots[(i + rotation) % count] for i in best]
        rounds.append(
            [
                ((ordered[i], ordered[i + 1]), (ordered[i + 2], ordered[i + 3]))
                for i in range(0, used, 4)
            ]
        )
    return rounds
