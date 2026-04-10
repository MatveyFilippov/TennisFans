from .models import *
import database.tools as db
import settings
from typing import List
from fastapi import APIRouter, HTTPException, status


log = settings.ProjectLoggerFactory.get_for("app.matches")
router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def register_match(register_body: RegisterMatchRequest):
    if register_body.side1.match_score < 0 or register_body.side2.match_score < 0:
        log.info(f"Match score={register_body.side1.match_score}|{register_body.side2.match_score} is negative")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Match score can't be negative")

    if len({register_body.side1.player1_id, register_body.side1.player2_id, register_body.side2.player1_id, register_body.side2.player2_id}) != 4:
        log.info(f"Player with id={register_body.side1.player1_id}|{register_body.side1.player2_id}|{register_body.side2.player1_id}|{register_body.side2.player2_id} doesn't unique")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not unique Player")

    if (
        not db.players.is_player_exists(register_body.side1.player1_id)
        or not db.players.is_player_exists(register_body.side1.player2_id)
        or not db.players.is_player_exists(register_body.side2.player1_id)
        or not db.players.is_player_exists(register_body.side2.player2_id)
    ):
        log.info(f"Player with id={register_body.side1.player1_id}|{register_body.side1.player2_id}|{register_body.side2.player1_id}|{register_body.side2.player2_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No such Player")

    match_entity = db.matches.register_match(
        players_pair_1_ids=(register_body.side1.player1_id, register_body.side1.player2_id,),
        players_pair_2_ids=(register_body.side2.player1_id, register_body.side2.player2_id,),
        players_pair_1_score=register_body.side1.match_score,
        players_pair_2_score=register_body.side2.match_score,
    )
    log.info(f"Create new Match with id={match_entity.id}")

    player1_pair1, player2_pair1 = db.matches.get_pair_players(players_pair_id=match_entity.players_pair_id_1)
    player1_pair2, player2_pair2 = db.matches.get_pair_players(players_pair_id=match_entity.players_pair_id_2)
    log.info(f"Get Players with ids={player1_pair1.id}&{player2_pair1.id} from PlayersPair with id={match_entity.players_pair_id_1} and Players with ids={player1_pair2.id}&{player2_pair2.id} from PlayersPair with id={match_entity.players_pair_id_2}")

    return MatchResponse.of(
        match_entity=match_entity,
        player1_pair1=player1_pair1, player2_pair1=player2_pair1,
        player1_pair2=player1_pair2, player2_pair2=player2_pair2,
    )


@router.get("", response_model=List[MatchResponse], status_code=status.HTTP_200_OK)
async def get_all_matches_for_player(player_id: int, start_date: datetime | None = datetime.min, end_date: datetime | None = datetime.max):
    if not db.players.is_player_exists(player_id):
        log.info(f"Player with id={player_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No such Player")

    match_entities = db.matches.get_all_matches_for_player_by_period(player_id=player_id, start_date=start_date, end_date=end_date)
    log.info(f"Get all Matches for Player with id={player_id} by period [{start_date.isoformat()};{end_date.isoformat()}]")

    pairs_cache = {}
    def get_pair_players_cached(players_pair_id: int):
        if players_pair_id in pairs_cache:
            log.debug(f"Reading PlayersPair[id={players_pair_id}] from cache")
            return pairs_cache[players_pair_id]
        result = db.matches.get_pair_players(players_pair_id=players_pair_id)
        pairs_cache[players_pair_id] = result
        return result

    matches = []
    for match_entity in match_entities:
        player1_pair1, player2_pair1 = get_pair_players_cached(players_pair_id=match_entity.players_pair_id_1)
        log.info(f"Get Players with ids={player1_pair1.id}&{player2_pair1.id} from PlayersPair with id={match_entity.players_pair_id_1}")
        player1_pair2, player2_pair2 = get_pair_players_cached(players_pair_id=match_entity.players_pair_id_2)
        log.info(f"Get Players with ids={player1_pair2.id}&{player2_pair2.id} from PlayersPair with id={match_entity.players_pair_id_2}")
        matches.append(MatchResponse.of(
            match_entity=match_entity,
            player1_pair1=player1_pair1, player2_pair1=player2_pair1,
            player1_pair2=player1_pair2, player2_pair2=player2_pair2,
        ))

    return matches


@router.get("/{match_id}", response_model=MatchResponse, status_code=status.HTTP_200_OK)
async def get_match(match_id: int):
    if not db.matches.is_match_exists(match_id):
        log.info(f"Match with id={match_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Match")

    match_entity = db.matches.get_match(match_id=match_id)
    log.info(f"Get Match with id={match_entity.id}")

    player1_pair1, player2_pair1 = db.matches.get_pair_players(players_pair_id=match_entity.players_pair_id_1)
    log.info(f"Get Players with ids={player1_pair1.id}&{player2_pair1.id} from PlayersPair with id={match_entity.players_pair_id_1}")
    player1_pair2, player2_pair2 = db.matches.get_pair_players(players_pair_id=match_entity.players_pair_id_2)
    log.info(f"Get Players with ids={player1_pair2.id}&{player2_pair2.id} from PlayersPair with id={match_entity.players_pair_id_2}")

    return MatchResponse.of(
        match_entity=match_entity,
        player1_pair1=player1_pair1, player2_pair1=player2_pair1,
        player1_pair2=player1_pair2, player2_pair2=player2_pair2,
    )
