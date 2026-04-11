from .models import *
import database.tools as db
import settings
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, status


log = settings.ProjectLoggerFactory.get_for("app.tours")
router = APIRouter(prefix="/tours", tags=["tours"])


@router.post("", response_model=TourResponse, status_code=status.HTTP_201_CREATED)
async def start_tour(body: StartTourRequest):
    if (body.started_at is not None and body.ended_at is not None) and body.started_at >= body.ended_at:
        log.info(f"Tour started_at={body.started_at} after (or equals with) ended_at={body.ended_at}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tour must starts before ends")
    tour_entity = db.tours.start_tour(name=body.name, started_at=body.started_at, ended_at=body.ended_at)
    log.info(f"Start new Tour with id={tour_entity.id}")
    return TourResponse.of(tour_entity=tour_entity)


@router.get("", response_model=List[TourResponse], status_code=status.HTTP_200_OK)
async def get_all_tours():
    tour_entities = db.tours.get_all_tours()
    log.info(f"Get all Tours")
    return [TourResponse.of(tour_entity=tour_entity) for tour_entity in tour_entities]


@router.get("/not_ended", response_model=List[TourResponse], status_code=status.HTTP_200_OK)
async def get_all_not_ended_tours():
    tour_entities = db.tours.get_all_not_ended_tours()
    log.info(f"Get all not ended Tours")
    return [TourResponse.of(tour_entity=tour_entity) for tour_entity in tour_entities]


@router.get("/ended", response_model=List[TourResponse], status_code=status.HTTP_200_OK)
async def get_all_ended_tours(start_date: datetime | None = datetime.min, end_date: datetime | None = datetime.max):
    if start_date > end_date:
        log.info(f"Request start_date={start_date} after end_date={end_date}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date must be before (or equals with) End date")

    tour_entities = db.tours.get_all_ended_tours_by_period(start_date=start_date, end_date=end_date)
    log.info(f"Get all ended Tours by period [{start_date.isoformat()};{end_date.isoformat()}]")
    return [TourResponse.of(tour_entity=tour_entity) for tour_entity in tour_entities]


@router.get("/{tour_id}", response_model=TourResponse, status_code=status.HTTP_200_OK)
async def get_tour(tour_id: int):
    if not db.tours.is_tour_exists(tour_id):
        log.info(f"Tour with id={tour_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Tour")
    tour_entity = db.tours.get_tour(tour_id=tour_id)
    log.info(f"Get Tour with id={tour_entity.id}")
    return TourResponse.of(tour_entity=tour_entity)


@router.get("/{tour_id}/players_points", response_model=List[TourPlayerPointsResponse], status_code=status.HTTP_200_OK)
async def get_tour_players_points(tour_id: int):
    if not db.tours.is_tour_exists(tour_id):
        log.info(f"Tour with id={tour_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Tour")
    tour_player_entities_points = db.tours.get_tour_players_points(tour_id=tour_id)
    log.info(f"Get Players and points for Tour with id={tour_id}")
    return [
        TourPlayerPointsResponse.of(player_entity=player_entity, player_tour_points=player_tour_points)
        for player_entity, player_tour_points in tour_player_entities_points.items()
    ]


@router.put("/{tour_id}/end", response_model=TourResponse, status_code=status.HTTP_200_OK)
async def end_tour(tour_id: int, body: Optional[EndTourRequest] = None):
    if not db.tours.is_tour_exists(tour_id):
        log.info(f"Tour with id={tour_id} doesn't exists")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such Tour")

    tour_entity = db.tours.get_tour(tour_id=tour_id)
    log.info(f"Get Tour with id={tour_entity.id}")
    if tour_entity.ended_at is not None:
        log.info(f"Tour with id={tour_id} already ended")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tour already ended")
    if body is None:
        body = EndTourRequest(ended_at=datetime.now(settings.BACKEND_TIMEZONE))
    elif tour_entity.started_at >= body.ended_at:
        log.info(f"Tour started_at={body.started_at} after (or equals with) ended_at={body.ended_at}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tour must ends after starts")

    tour_entity = db.tours.end_tour(tour_id=tour_id, ended_at=body.ended_at)
    log.info(f"End Tour with id={tour_entity.id}")
    return TourResponse.of(tour_entity=tour_entity)

