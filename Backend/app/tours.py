from .models import *
import database as db
from utils.players_pair_utils import find_optimal_players_pairs
import settings
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, status


log = settings.ProjectLoggerFactory.get_for("app.tours")
router = APIRouter(prefix="/tours", tags=["tours"])


async def raise_not_found_if_tour_not_exists(tour_id: int):
    log.debug(f"Checking Tour with id={tour_id} exists")
    if not db.tours.is_tour_exists(tour_id):
        log.debug(f"Tour with id={tour_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Tour")
    log.debug(f"Tour with id={tour_id} exists")


async def raise_bad_request_if_invalid_tour_values(name: str, started_at: datetime, ended_at: datetime | None):
    log.debug("Checking Tour values")
    if len(name) == 0 or name.isspace():
        log.debug(f"Tour name is blank")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tour name can't be blank")
    if ended_at is not None and started_at >= ended_at:
        log.debug(f"Tour started_at={started_at} after (or equals with) ended_at={ended_at}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tour must starts before ends")
    log.debug("Tour values is valid")


@router.post("", response_model=TourResponse, status_code=status.HTTP_201_CREATED)
async def create_tour(body: CreateTourRequest):
    body.name = body.name.strip()
    await raise_bad_request_if_invalid_tour_values(
        name=body.name,
        started_at=(body.started_at or datetime.now(tz=settings.PROJECT_TIMEZONE)),
        ended_at=body.ended_at
    )

    log.debug("Creating new Tour")
    tour_dto = db.tours.create_tour(name=body.name, started_at=body.started_at, ended_at=body.ended_at)
    log.info(f"Create new Tour with id={tour_dto.id}")
    log.debug(f"Create: {tour_dto}")
    return TourResponse.of(tour_dto=tour_dto)


@router.get("", response_model=List[TourResponse], status_code=status.HTTP_200_OK)
async def get_all_tours(started_after: datetime | None = None, ended_before: datetime | None = None):
    if (started_after is not None and ended_before is not None) and started_after > ended_before:
        log.debug(f"Request started_after={started_after} after ended_before={ended_before}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid datetime range")

    log.debug(f"Getting all Tours by period [{started_after.isoformat() if started_after else None};{ended_before.isoformat() if ended_before else None}]")
    tour_dtos = db.tours.get_all_tours_by_period(started_after=started_after, ended_before=ended_before)
    log.info(f"Get all Tours by period [{started_after.isoformat() if started_after else '-min'};{ended_before.isoformat() if ended_before else '+max'}]")
    log.debug(f"Get: {tour_dtos}")
    return [TourResponse.of(tour_dto=tour_dto) for tour_dto in tour_dtos]


@router.get("/not_ended", response_model=List[TourResponse], status_code=status.HTTP_200_OK)
async def get_all_not_ended_tours():
    log.debug("Getting all not ended Tours")
    tour_dtos = db.tours.get_all_not_ended_tours()
    log.info("Get all not ended Tours")
    log.debug(f"Get: {tour_dtos}")
    return [TourResponse.of(tour_dto=tour_dto) for tour_dto in tour_dtos]


@router.get("/{tour_id}", response_model=TourResponse, status_code=status.HTTP_200_OK)
async def get_tour(tour_id: int):
    await raise_not_found_if_tour_not_exists(tour_id=tour_id)

    log.debug(f"Getting Tour with id={tour_id}")
    tour_dto = db.tours.get_tour(tour_id=tour_id)
    log.info(f"Get Tour with id={tour_dto.id}")
    log.debug(f"Get: {tour_dto}")
    return TourResponse.of(tour_dto=tour_dto)


@router.patch("/{tour_id}", response_model=TourResponse, status_code=status.HTTP_200_OK)
async def edit_tour(tour_id: int, body: EditTourRequest):
    await raise_not_found_if_tour_not_exists(tour_id=tour_id)
    if body.name:
        body.name = body.name.strip()
    log.debug(f"Getting Tour with id={tour_id}")
    tour_before_dto = db.tours.get_tour(tour_id=tour_id)
    log.debug(f"Get: {tour_before_dto}")
    await raise_bad_request_if_invalid_tour_values(
        name=(body.name or tour_before_dto.name),
        started_at=(body.started_at or tour_before_dto.started_at),
        ended_at=(body.ended_at or tour_before_dto.ended_at),
    )

    log.debug(f"Editing Tour with id={tour_id}")
    tour_after_dto = db.tours.edit_tour(tour_id=tour_id, name=body.name, started_at=body.started_at, ended_at=body.ended_at)
    log.info(f"Edit Tour with id={tour_after_dto.id}")
    log.debug(f"Edit: {tour_before_dto} -> {tour_after_dto}")
    return TourResponse.of(tour_dto=tour_after_dto)


@router.delete("/{tour_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def delete_tour(tour_id: int):
    await raise_not_found_if_tour_not_exists(tour_id=tour_id)

    log.debug(f"Deleting Tour with id={tour_id}")
    db.tours.delete_tour(tour_id=tour_id)
    log.info(f"Delete Tour with id={tour_id}")
    return None


@router.get("/{tour_id}/players_points", response_model=List[TourPlayerPointsResponse], status_code=status.HTTP_200_OK)
async def get_tour_players_points(tour_id: int):
    await raise_not_found_if_tour_not_exists(tour_id=tour_id)

    log.debug(f"Getting Players and points for Tour with id={tour_id}")
    tour_player_dtos_points = db.tours.get_tour_players_points(tour_id=tour_id)
    log.info(f"Get Players and points for Tour with id={tour_id}")
    log.debug(f"Get: {tour_player_dtos_points}")
    return [
        TourPlayerPointsResponse.of(player_dto=player_dto, player_tour_points=player_tour_points)
        for player_dto, player_tour_points in tour_player_dtos_points
    ]


@router.get("/{tour_id}/propose_players_pairs", response_model=List[TourPlayersPairProposeResponse], status_code=status.HTTP_200_OK)
async def propose_players_pairs(tour_id: int):
    await raise_not_found_if_tour_not_exists(tour_id=tour_id)

    log.debug(f"Getting Tour with id={tour_id}")
    tour_dto = db.tours.get_tour(tour_id=tour_id)
    log.debug(f"Get Tour with id={tour_dto.id}")
    log.debug(f"Get: {tour_dto}")

    if tour_dto.ended_at is not None and tour_dto.ended_at <= datetime.now(tz=settings.PROJECT_TIMEZONE):
        log.debug(f"Tour with id={tour_dto.id} already ended")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can't propose pairs for ended Tour")

    log.debug("Getting all Players")
    all_players_id_dto = {
        player_dto.id: player_dto
        for player_dto in db.players.get_all_players()
    }
    log.debug("Get all Players")
    log.debug(f"Get: {all_players_id_dto}")

    log.debug(f"Getting all PlayersPairs last play for Tour with id={tour_dto.id}")
    players_pair_dto_last_play = db.matches.get_players_pair_last_play(tour_id=tour_dto.id)
    log.info(f"Get all PlayersPairs last play for Tour with id={tour_dto.id}")
    log.debug(f"Get: {players_pair_dto_last_play}")

    log.debug(f"Computing optimal PlayersPairs for Tour with id={tour_dto.id}")
    optimal_players_pairs = find_optimal_players_pairs(
        all_players_id_dto=all_players_id_dto,
        players_pair_dto_last_play=players_pair_dto_last_play,
    )
    log.info(f"Compute optimal PlayersPairs for Tour with id={tour_dto.id}")
    log.debug(f"Compute: {optimal_players_pairs}")

    return [
        TourPlayersPairProposeResponse.of(
            players_pair_dto=players_pair_dto,
            last_played_at=players_pair_dto_last_play.get(players_pair_dto),
        ) for players_pair_dto in optimal_players_pairs
    ]
