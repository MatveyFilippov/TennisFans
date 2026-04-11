from .models import *
import database.tools as db
import settings
from typing import List
from fastapi import APIRouter, HTTPException, status


log = settings.ProjectLoggerFactory.get_for("app.players")
router = APIRouter(prefix="/players", tags=["players"])


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(body: CreatePlayerRequest):
    player_entity = db.players.create_player(name=body.name, registered_at=body.registered_at)
    log.info(f"Create new Player with id={player_entity.id}")
    return PlayerResponse.of(player_entity=player_entity)


@router.get("", response_model=List[PlayerResponse], status_code=status.HTTP_200_OK)
async def get_all_players():
    player_entities = db.players.get_all_players()
    log.info(f"Get all Players")
    return [PlayerResponse.of(player_entity=player_entity) for player_entity in player_entities]


@router.get("/{player_id}", response_model=PlayerResponse, status_code=status.HTTP_200_OK)
async def get_player(player_id: int):
    if not db.players.is_player_exists(player_id):
        log.info(f"Player with id={player_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Player")
    player_entity = db.players.get_player(player_id=player_id)
    log.info(f"Get Player with id={player_entity.id}")
    return PlayerResponse.of(player_entity=player_entity)

