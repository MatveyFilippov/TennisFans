from .models import *
import database as db
import settings
from typing import List
from fastapi import APIRouter, HTTPException, status


log = settings.ProjectLoggerFactory.get_for("app.players")
router = APIRouter(prefix="/players", tags=["players"])


async def raise_not_found_if_player_not_exists(player_id: int):
    log.info(f"Checking Player with id={player_id} exists")
    if not db.players.is_player_exists(player_id):
        log.debug(f"Player with id={player_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Player")
    log.debug(f"Player with id={player_id} exists")


async def raise_bad_request_if_invalid_player_values(name: str):
    log.debug("Checking Player values")
    if len(name) == 0 or name.isspace():
        log.debug(f"Player name is blank")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Player name can't be blank")
    log.debug("Player values is valid")


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(body: CreatePlayerRequest):
    body.name = body.name.strip()
    await raise_bad_request_if_invalid_player_values(name=body.name)

    log.debug("Creating new Player")
    player_dto = db.players.create_player(name=body.name)
    log.info(f"Create new Player with id={player_dto.id}")
    log.debug(f"Create: {player_dto}")
    return PlayerResponse.of(player_dto=player_dto)


@router.get("", response_model=List[PlayerResponse], status_code=status.HTTP_200_OK)
async def get_all_players():
    log.debug("Getting all Players")
    player_dtos = db.players.get_all_players()
    log.info(f"Get all Players")
    log.debug(f"Get: {player_dtos}")
    return [PlayerResponse.of(player_dto=player_dto) for player_dto in player_dtos]


@router.get("/{player_id}", response_model=PlayerResponse, status_code=status.HTTP_200_OK)
async def get_player(player_id: int):
    await raise_not_found_if_player_not_exists(player_id)

    log.debug(f"Getting Player with id={player_id}")
    player_dto = db.players.get_player(player_id=player_id)
    log.info(f"Get Player with id={player_dto.id}")
    log.debug(f"Get: {player_dto}")
    return PlayerResponse.of(player_dto=player_dto)


@router.patch("/{player_id}", response_model=PlayerResponse, status_code=status.HTTP_200_OK)
async def edit_player(player_id: int, body: EditPlayerRequest):
    await raise_not_found_if_player_not_exists(player_id)
    if body.name:
        body.name = body.name.strip()
    log.debug(f"Getting Player with id={player_id}")
    player_before_dto = db.players.get_player(player_id=player_id)
    log.info(f"Get Player with id={player_before_dto.id}")
    log.debug(f"Get: {player_before_dto}")
    await raise_bad_request_if_invalid_player_values(name=(body.name or player_before_dto.name))

    log.debug(f"Editing Player with id={player_id}")
    player_after_dto = db.players.edit_player(player_id=player_id, name=body.name)
    log.info(f"Edit Player with id={player_after_dto.id}")
    log.debug(f"Edit: {player_before_dto} -> {player_after_dto}")
    return PlayerResponse.of(player_dto=player_after_dto)


@router.delete("/{player_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(player_id: int):
    await raise_not_found_if_player_not_exists(player_id)

    log.debug(f"Deleting Player with id={player_id}")
    db.players.delete_player(player_id=player_id)
    log.info(f"Delete Player with id={player_id}")
    return None

