from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tennisfans.core.errors import invalid

NonNegative = Annotated[int, Field(ge=0, le=999, strict=True)]
Side = Literal[0, 1]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Discipline(StrEnum):
    SINGLES = "SINGLES"
    DOUBLES = "DOUBLES"


class ScoreFormat(StrEnum):
    STANDARD_MATCH = "STANDARD_MATCH"
    SINGLE_SET = "SINGLE_SET"
    SHORT_MATCH = "SHORT_MATCH"


class ShortFinish(StrEnum):
    DECIDING_GAME = "DECIDING_GAME"
    TIEBREAK = "TIEBREAK"
    WIN_BY_TWO = "WIN_BY_TWO"


class Outcome(StrEnum):
    COMPETITIVE = "COMPETITIVE"
    WALKOVER = "WALKOVER"
    RETIREMENT = "RETIREMENT"
    FORFEIT = "FORFEIT"


class Rules(Input):
    format: ScoreFormat = ScoreFormat.STANDARD_MATCH
    deciding_match_tiebreak: bool = False
    short_games: int = Field(3, ge=2, le=20)
    short_finish: ShortFinish = ShortFinish.DECIDING_GAME
    short_tiebreak_points: int = Field(7, ge=3, le=21)

    @model_validator(mode="after")
    def check_format(self) -> "Rules":
        if self.deciding_match_tiebreak and self.format != ScoreFormat.STANDARD_MATCH:
            raise ValueError("Deciding match tie-break requires a standard match")
        return self


class SetScore(Input):
    a: NonNegative
    b: NonNegative
    tiebreak_a: NonNegative | None = None
    tiebreak_b: NonNegative | None = None


class Score(Input):
    outcome: Outcome = Outcome.COMPETITIVE
    winner: Side
    sets: list[SetScore] = Field(default_factory=list, max_length=3)


def _invalid_score(detail: str) -> None:
    raise invalid("invalid_score", detail)


def _points(a: int, b: int, target: int) -> bool:
    high, low = sorted((a, b), reverse=True)
    return high == max(target, low + 2)


def _games(a: int, b: int, rules: Rules, standard: bool) -> tuple[bool, int | None]:
    high, low = sorted((a, b), reverse=True)
    if standard:
        valid = (high, low) in {(7, 5), (7, 6)} or (high == 6 and low <= 4)
        return valid, 7 if (high, low) == (7, 6) else None
    target = rules.short_games
    if rules.short_finish == ShortFinish.WIN_BY_TWO:
        return _points(a, b, target), None
    valid = high == target and low < target
    points = (
        rules.short_tiebreak_points
        if valid and low == target - 1 and rules.short_finish == ShortFinish.TIEBREAK
        else None
    )
    return valid, points


def validate_score(rules: Rules, score: Score, *, tournament: bool) -> None:
    if score.outcome != Outcome.COMPETITIVE and not tournament:
        _invalid_score("Friendly matches require completed competitive scores")
    if score.outcome in {Outcome.WALKOVER, Outcome.FORFEIT}:
        if score.sets:
            _invalid_score("Walkovers and forfeits cannot include a games score")
        return

    needed = 2 if rules.format == ScoreFormat.STANDARD_MATCH else 1
    wins = [0, 0]
    for index, item in enumerate(score.sets):
        if max(wins) >= needed:
            _invalid_score("There cannot be a set after the winning set")
        tiebreak = (item.tiebreak_a, item.tiebreak_b)
        if (tiebreak[0] is None) != (tiebreak[1] is None):
            _invalid_score("Supply tie-break points for both sides")
        deciding = rules.deciding_match_tiebreak and wins == [1, 1]
        if deciding:
            completed, target = _points(item.a, item.b, 10), None
        else:
            completed, target = _games(
                item.a, item.b, rules, rules.format != ScoreFormat.SHORT_MATCH
            )
        if tiebreak[0] is not None and tiebreak[1] is not None:
            if (
                target is None
                or not _points(tiebreak[0], tiebreak[1], target)
                or (item.a > item.b) != (tiebreak[0] > tiebreak[1])
            ):
                _invalid_score("Tie-break points must be valid and agree with the set winner")
        if not completed:
            if (
                score.outcome != Outcome.RETIREMENT
                or index != len(score.sets) - 1
                or tiebreak[0] is not None
                or not _partial(item, rules, deciding)
            ):
                _invalid_score("Invalid set or deciding match tie-break")
            continue
        wins[int(item.b > item.a)] += 1

    if score.outcome == Outcome.COMPETITIVE and wins[score.winner] != needed:
        _invalid_score("The score must complete the match and agree with the declared winner")
    if score.outcome == Outcome.RETIREMENT and max(wins) >= needed:
        _invalid_score("A completed match cannot be recorded as a retirement")


def _partial(item: SetScore, rules: Rules, deciding: bool) -> bool:
    high, low = sorted((item.a, item.b), reverse=True)
    if deciding:
        return high < 10 or high - low < 2
    if rules.format != ScoreFormat.SHORT_MATCH:
        return high <= 5 or (high == 6 and low in {5, 6})
    if rules.short_finish == ShortFinish.WIN_BY_TWO:
        return high < rules.short_games or high - low < 2
    return high < rules.short_games


def score_totals(rules: Rules, score: Score) -> tuple[int, int, int, int]:
    sets_a = sets_b = games_a = games_b = 0
    for item in score.sets:
        if rules.deciding_match_tiebreak and sets_a == sets_b == 1:
            sets_a += int(_points(item.a, item.b, 10) and item.a > item.b)
            sets_b += int(_points(item.a, item.b, 10) and item.b > item.a)
            continue
        games_a += item.a
        games_b += item.b
        completed, _ = _games(item.a, item.b, rules, rules.format != ScoreFormat.SHORT_MATCH)
        if completed:
            sets_a += int(item.a > item.b)
            sets_b += int(item.b > item.a)
    return sets_a, sets_b, games_a, games_b
