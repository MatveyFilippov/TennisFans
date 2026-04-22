from utils import dto
from utils.datetime_utils import localize_datetime
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class PlayerResponse(BaseModel):
    id: int
    name: str
    registered_at: datetime

    @classmethod
    def of(
            cls, player_dto: dto.PlayerDTO
    ) -> 'PlayerResponse':
        return PlayerResponse(
            id=player_dto.id,
            name=player_dto.name,
            registered_at=localize_datetime(player_dto.registered_at),
        )


class TourResponse(BaseModel):
    id: int
    name: str
    started_at: datetime
    ended_at: Optional[datetime]

    @classmethod
    def of(
            cls, tour_dto: dto.TourDTO
    ) -> 'TourResponse':
        return TourResponse(
            id=tour_dto.id,
            name=tour_dto.name,
            started_at=localize_datetime(tour_dto.started_at),
            ended_at=localize_datetime(tour_dto.ended_at) if tour_dto.ended_at is not None else None,
        )


class TourPlayerPointsResponse(BaseModel):
    player: PlayerResponse
    player_tour_points: float

    @classmethod
    def of(
            cls, player_dto: dto.PlayerDTO, player_tour_points: float
    ) -> 'TourPlayerPointsResponse':
        return TourPlayerPointsResponse(
            player=PlayerResponse.of(
                player_dto=player_dto,
            ),
            player_tour_points=player_tour_points,
        )


class PlayersPairResponse(BaseModel):
    player1: PlayerResponse
    player2: PlayerResponse

    @classmethod
    def of(
            cls, players_pair_dto: dto.PlayersPairDTO
    ) -> 'PlayersPairResponse':
        return PlayersPairResponse(
            player1=PlayerResponse.of(
                player_dto=players_pair_dto.player1_dto,
            ),
            player2=PlayerResponse.of(
                player_dto=players_pair_dto.player2_dto,
            ),
        )


class MatchResponse(BaseModel):
    id: int
    played_at: datetime
    players_pair1: PlayersPairResponse
    players_pair2: PlayersPairResponse
    players_pair1_score: int
    players_pair2_score: int

    @classmethod
    def of(
            cls, match_dto: dto.MatchDTO,
    ) -> 'MatchResponse':
        return MatchResponse(
            id=match_dto.id,
            played_at=localize_datetime(match_dto.played_at),
            players_pair1=PlayersPairResponse.of(
                players_pair_dto=match_dto.players_pair1_dto,
            ),
            players_pair2=PlayersPairResponse.of(
                players_pair_dto=match_dto.players_pair2_dto,
            ),
            players_pair1_score=match_dto.players_pair1_score,
            players_pair2_score=match_dto.players_pair2_score,
        )


class TourPlayersPairProposeResponse(BaseModel):
    players_pair: PlayersPairResponse
    last_played_at: Optional[datetime]

    @classmethod
    def of(
            cls, players_pair_dto: dto.PlayersPairDTO, last_played_at: datetime | None
    ) -> 'TourPlayersPairProposeResponse':
        return TourPlayersPairProposeResponse(
            players_pair=PlayersPairResponse.of(
                players_pair_dto=players_pair_dto,
            ),
            last_played_at=localize_datetime(last_played_at) if last_played_at is not None else None,
        )


class CreatePlayerRequest(BaseModel):
    name: str


class EditPlayerRequest(BaseModel):
    name: Optional[str] = None


class CreateTourRequest(BaseModel):
    name: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class EditTourRequest(BaseModel):
    name: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class RegisterMatchRequest(BaseModel):
    class RegisterMatchNetSideRequest(BaseModel):
        player1_id: int
        player2_id: int
        match_score: int

    side1: RegisterMatchNetSideRequest
    side2: RegisterMatchNetSideRequest
    played_at: Optional[datetime] = None
