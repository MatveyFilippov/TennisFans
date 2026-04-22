from datetime import datetime, timezone
from sqlalchemy import and_, desc, exists, or_, select
import settings
from utils import dto
from utils.datetime_utils import utc_datetime
from .general import _get_all_matches_by_period, _get_tour, _to_player_dto, _to_tour_dto
from ..base import PlayerEntity, PlayersPairEntity, Session, TourEntity


log = settings.ProjectLoggerFactory.get_for("database.tours")


def is_tour_exists(tour_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Tour[id={tour_id}] exists")
        return bool(
            session.query(
                exists().where(TourEntity.id == tour_id),
            ).scalar(),
        )


def create_tour(name: str, started_at: datetime = None, ended_at: datetime = None) -> dto.TourDTO:
    started_at = utc_datetime(started_at) if started_at else None
    ended_at = utc_datetime(ended_at) if ended_at else None
    with Session() as session:
        log.debug("Creating new Tour")
        new_tour = TourEntity(
            name=name,
        )
        if started_at is not None:
            new_tour.started_at = started_at
        if ended_at is not None:
            new_tour.ended_at = ended_at
        session.add(new_tour)
        session.commit()
        session.refresh(new_tour)
        log.debug(f"Create new Tour[id={new_tour.id}]")
        return _to_tour_dto(tour=new_tour)


def edit_tour(tour_id: int, name: str = None, started_at: datetime = None, ended_at: datetime = None) -> dto.TourDTO:
    started_at = utc_datetime(started_at) if started_at else None
    ended_at = utc_datetime(ended_at) if ended_at else None
    with Session() as session:
        tour = _get_tour(session=session, tour_id=tour_id)

        log.debug(f"Looking for changes in Tour[id={tour.id}]")
        is_edit = False
        if name is not None and tour.name != name:
            tour.name = name
            is_edit = True
        if started_at is not None and tour.started_at != started_at:
            tour.started_at = started_at
            is_edit = True
        if ended_at is not None and tour.ended_at != ended_at:
            tour.ended_at = ended_at
            is_edit = True

        if is_edit:
            session.commit()
            session.refresh(tour)
            log.debug(f"Edit Tour[id={tour.id}]")
        else:
            log.debug(f"Don't edit Tour[id={tour.id}], already in target state")

        return _to_tour_dto(tour=tour)


def delete_tour(tour_id: int):
    with Session() as session:
        tour = _get_tour(session=session, tour_id=tour_id)
        session.delete(tour)
        session.commit()
        log.debug(f"Delete Tour[id={tour_id}]")


def get_tour(tour_id: int) -> dto.TourDTO:
    with Session() as session:
        tour = _get_tour(session=session, tour_id=tour_id)
        return _to_tour_dto(tour=tour)


def get_all_not_ended_tours() -> list[dto.TourDTO]:
    dt_now = datetime.now(tz=timezone.min)
    with Session() as session:
        log.debug("Reading all not ended Tours")
        stmt = select(TourEntity).where(
            or_(
                TourEntity.ended_at == None,
                TourEntity.ended_at < dt_now,
            ),
        ).order_by(desc(TourEntity.started_at))
        tours = session.execute(stmt).scalars().all()
        return [_to_tour_dto(tour=tour) for tour in tours]


def get_all_tours_by_period(started_after: datetime | None = None, ended_before: datetime | None = None) -> list[dto.TourDTO]:
    started_after = utc_datetime(started_after or datetime.min)
    ended_before = utc_datetime(ended_before or datetime.max)
    with Session() as session:
        log.debug(f"Reading all Tours by period [{started_after.isoformat()};{ended_before.isoformat()}]")
        stmt = select(TourEntity).where(
            and_(
                TourEntity.started_at >= started_after,
                or_(
                    TourEntity.ended_at == None,
                    TourEntity.ended_at <= ended_before,
                ),
            ),
        ).order_by(desc(TourEntity.started_at))
        tours = session.execute(stmt).scalars().all()
        return [_to_tour_dto(tour=tour) for tour in tours]


def get_tour_players_points(tour_id: int) -> list[tuple[dto.PlayerDTO, float]]:
    with Session() as session:
        log.debug(f"Reading all Players points in Tour[id={tour_id}]")
        tour = _get_tour(session=session, tour_id=tour_id)
        matches = _get_all_matches_by_period(session=session, played_after=tour.started_at, played_before=(tour.ended_at or utc_datetime(datetime.max)))

        pair_ids = set()
        for match in matches:
            pair_ids.add(match.players_pair_id_1)
            pair_ids.add(match.players_pair_id_2)
        if not pair_ids:
            return []

        log.debug(f"Reading all PlayersPairs in Tour[id={tour.id}]")
        pairs_query = select(PlayersPairEntity).where(PlayersPairEntity.id.in_(pair_ids))
        pairs = {p.id: p for p in session.execute(pairs_query).scalars().all()}

        all_player_ids = set()
        for pair in pairs.values():
            all_player_ids.add(pair.player1_id)
            all_player_ids.add(pair.player2_id)

        log.debug(f"Computing Players points in Tour[id={tour.id}]")
        points = {}
        for match in matches:
            pair1 = pairs.get(match.players_pair_id_1)
            pair2 = pairs.get(match.players_pair_id_2)

            if pair1:
                points[pair1.player1_id] = points.get(pair1.player1_id, 0) + match.score_players_pair_1
                points[pair1.player2_id] = points.get(pair1.player2_id, 0) + match.score_players_pair_1

            if pair2:
                points[pair2.player1_id] = points.get(pair2.player1_id, 0) + match.score_players_pair_2
                points[pair2.player2_id] = points.get(pair2.player2_id, 0) + match.score_players_pair_2

        log.debug(f"Reading all Players in Tour[id={tour.id}]")
        tour_players = session.query(PlayerEntity).where(PlayerEntity.id.in_(all_player_ids)).all()
        result = {
            _to_player_dto(player=player): ((points[player.id] / 2) if player.id in points else 0)
            for player in tour_players
        }

        return list(sorted(result.items(), key=lambda i: i[1], reverse=True))
