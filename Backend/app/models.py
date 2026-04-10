import database.base.entities as db_entities
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
            cls, player_entity: db_entities.Player
    ) -> 'PlayerResponse':
        return PlayerResponse(
            id=player_entity.id,
            name=player_entity.name,
            registered_at=localize_datetime(player_entity.registered_at),
        )


class PlayersPairResponse(BaseModel):
    player1: PlayerResponse
    player2: PlayerResponse

    @classmethod
    def of(
            cls, player1_entity: db_entities.Player, player2_entity: db_entities.Player
    ) -> 'PlayersPairResponse':
        return PlayersPairResponse(
            player1=PlayerResponse.of(player1_entity),
            player2=PlayerResponse.of(player2_entity),
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
            cls, match_entity: db_entities.Match,
            player1_pair1: db_entities.Player, player2_pair1: db_entities.Player,
            player1_pair2: db_entities.Player, player2_pair2: db_entities.Player,
    ) -> 'MatchResponse':
        return MatchResponse(
            id=match_entity.id,
            played_at=localize_datetime(match_entity.played_at),
            players_pair1=PlayersPairResponse.of(
                player1_entity=player1_pair1,
                player2_entity=player2_pair1,
            ),
            players_pair2=PlayersPairResponse.of(
                player1_entity=player1_pair2,
                player2_entity=player2_pair2,
            ),
            players_pair1_score=match_entity.score_players_pair_1,
            players_pair2_score=match_entity.score_players_pair_2,
        )


class CreatePlayerRequest(BaseModel):
    name: str
    registered_at: Optional[datetime] = None


class RegisterMatchRequest(BaseModel):
    class RegisterMatchNetSideRequest(BaseModel):
        player1_id: int
        player2_id: int
        match_score: int

    side1: RegisterMatchNetSideRequest
    side2: RegisterMatchNetSideRequest
    played_at: Optional[datetime] = None
