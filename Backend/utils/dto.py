from datetime import datetime
from typing import NamedTuple


class PlayerDTO(NamedTuple):
    id: int
    name: str
    registered_at: datetime

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, PlayerDTO):
            return NotImplemented
        return self.id == other.id


class TourDTO(NamedTuple):
    id: int
    name: str
    started_at: datetime
    ended_at: datetime | None

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, TourDTO):
            return NotImplemented
        return self.id == other.id


class PlayersPairDTO(NamedTuple):
    player1_dto: PlayerDTO
    player2_dto: PlayerDTO

    def sort_player_ids(self) -> tuple[int, int]:
        return tuple(sorted([self.player1_dto.id, self.player2_dto.id]))

    def __hash__(self) -> int:
        return hash(self.sort_player_ids())

    def __eq__(self, other) -> bool:
        if not isinstance(other, PlayersPairDTO):
            return NotImplemented
        return self.sort_player_ids() == other.sort_player_ids()


class MatchDTO(NamedTuple):
    id: int
    played_at: datetime
    players_pair1_dto: PlayersPairDTO
    players_pair2_dto: PlayersPairDTO
    players_pair1_score: int
    players_pair2_score: int

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        if not isinstance(other, MatchDTO):
            return NotImplemented
        return self.id == other.id
