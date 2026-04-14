from .models import *
import database as db
import settings
from typing import List
from fastapi import APIRouter, HTTPException, status


log = settings.ProjectLoggerFactory.get_for("app.matches")
router = APIRouter(prefix="/matches", tags=["matches"])


async def raise_not_found_if_match_not_exists(match_id: int):
    log.debug("Checking Match exists")
    if not db.matches.is_match_exists(match_id):
        log.debug(f"Match with id={match_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Match")
    log.debug(f"Match with id={match_id} exists")


async def raise_bad_request_if_invalid_player_values(side1_player1_id: int, side1_player2_id: int, side2_player1_id: int, side2_player2_id: int, side1_match_score: int, side2_match_score: int):
    log.debug("Checking Match values")
    if len({side1_player1_id, side1_player2_id, side2_player1_id, side2_player2_id}) != 4:
        log.debug(f"Player with id={side1_player1_id}|{side1_player2_id}|{side2_player1_id}|{side2_player2_id} doesn't unique")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not unique Player")
    if side1_match_score < 0 or side2_match_score < 0:
        log.debug(f"Match score={side1_match_score}|{side2_match_score} is negative")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Match score can't be negative")
    for player_id in [side1_player1_id, side1_player2_id, side2_player1_id, side2_player2_id]:
        if not db.players.is_player_exists(player_id):
            log.debug(f"Player with id={player_id} doesn't exists")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No such Player")
    log.debug("Match values is valid")


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def register_match(body: RegisterMatchRequest):
    await raise_bad_request_if_invalid_player_values(
        side1_player1_id=body.side1.player1_id,
        side1_player2_id=body.side1.player2_id,
        side2_player1_id=body.side2.player1_id,
        side2_player2_id=body.side2.player2_id,
        side1_match_score=body.side1.match_score,
        side2_match_score=body.side2.match_score,
    )

    log.debug("Creating new Match")
    match_dto = db.matches.register_match(
        players_pair_1_ids=(body.side1.player1_id, body.side1.player2_id),
        players_pair_2_ids=(body.side2.player1_id, body.side2.player2_id),
        players_pair_1_score=body.side1.match_score,
        players_pair_2_score=body.side2.match_score,
        played_at=body.played_at,
    )
    log.info(f"Create new Match with id={match_dto.id}")
    log.debug(f"Create: {match_dto}")
    return MatchResponse.of(match_dto=match_dto)


@router.get("", response_model=List[MatchResponse], status_code=status.HTTP_200_OK)
async def get_all_matches(player_id: int | None = None, played_after: datetime | None = None, played_before: datetime | None = None):
    if (played_after is not None and played_before is not None) and played_after > played_before:
        log.debug(f"Request played_after={played_after} after played_before={played_before}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid datetime range")

    if player_id is not None:
        log.debug(f"Checking Player with id={player_id} exists")
        if not db.players.is_player_exists(player_id):
            log.debug(f"Player with id={player_id} doesn't exists")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No such Player")
        log.debug(f"Player with id={player_id} exists")
        log.debug(f"Getting all Matches for Player with id={player_id} by period [{played_after.isoformat() if played_after else '-min'};{played_before.isoformat() if played_before else '+max'}]")
        match_dtos = db.matches.get_all_matches_for_player_by_period(player_id=player_id, played_after=played_after, played_before=played_before)
        log.info(f"Get all Matches for Player with id={player_id} by period [{played_after.isoformat() if played_after else '-min'};{played_before.isoformat() if played_before else '+max'}]")
    else:
        log.debug(f"Getting all Matches by period [{played_after.isoformat() if played_after else '-min'};{played_before.isoformat() if played_before else '+max'}]")
        match_dtos = db.matches.get_all_matches_by_period(played_after=played_after, played_before=played_before)
        log.info(f"Get all Matches by period [{played_after.isoformat() if played_after else '-min'};{played_before.isoformat() if played_before else '+max'}]")
    log.debug(f"Get: {match_dtos}")

    return [MatchResponse.of(match_dto=match_dto) for match_dto in match_dtos]


@router.get("/{match_id}", response_model=MatchResponse, status_code=status.HTTP_200_OK)
async def get_match(match_id: int):
    await raise_not_found_if_match_not_exists(match_id)

    log.debug(f"Getting Match with id={match_id}")
    match_dto = db.matches.get_match(match_id=match_id)
    log.info(f"Get Match with id={match_dto.id}")
    log.debug(f"Get: {match_dto}")
    return MatchResponse.of(match_dto=match_dto)


@router.delete("/{match_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def delete_match(match_id: int):
    await raise_not_found_if_match_not_exists(match_id)

    log.debug(f"Deleting Match with id={match_id}")
    db.matches.delete_match(match_id=match_id)
    log.info(f"Delete Match with id={match_id}")
    return None
