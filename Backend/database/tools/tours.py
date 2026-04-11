from ..base import Player, Tour, PlayersPair, Match, Session
from utils.datetime_utils import utc_datetime
import settings
from datetime import datetime
from sqlalchemy import and_, desc, exists, select


log = settings.ProjectLoggerFactory.get_for("database.tours")


def _get_tour(session: Session, tour_id: int) -> Tour:
    log.debug(f"Reading Tour[id={tour_id}]")
    tour = session.get(Tour, tour_id)
    if not tour:
        raise KeyError(f"No such Tour in database with ID {tour_id}")
    return tour


def is_tour_exists(tour_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Tour[id={tour_id}] exists")
        return bool(session.query(
            exists().where(Tour.id == tour_id)
        ).scalar())


def start_tour(name: str, started_at: datetime | None = None, ended_at: datetime | None = None) -> Tour:
    started_at = utc_datetime(started_at) if started_at else None
    ended_at = utc_datetime(ended_at) if ended_at else None
    with Session() as session:
        log.debug("Starting new Tour")
        new_tour = (
            Tour(
                name=name,
                started_at=started_at,
                ended_at=ended_at,
            )
            if started_at else
            Tour(
                name=name,
                ended_at=ended_at,
            )
        )
        session.add(new_tour)
        session.commit()
        session.refresh(new_tour)
        log.debug(f"Start new Tour[id={new_tour.id}]")
        return new_tour


def end_tour(tour_id: int, ended_at: datetime) -> Tour:
    ended_at = utc_datetime(ended_at)
    with Session() as session:
        log.debug(f"Ending Tour[id={tour_id}]")
        tour = _get_tour(session=session, tour_id=tour_id)
        if tour.ended_at is not None:
            raise ValueError(f"Tour with ID {tour.ended_at} already ended")
        tour.ended_at = ended_at
        session.commit()
        session.refresh(tour)
        return tour


def get_tour(tour_id: int) -> Tour:
    with Session() as session:
        return _get_tour(session=session, tour_id=tour_id)


def get_all_tours() -> list[Tour]:
    with Session() as session:
        log.debug("Reading all Tours")
        return session.query(Tour).order_by(desc(Tour.started_at)).all()


def get_all_not_ended_tours() -> list[Tour]:
    with Session() as session:
        log.debug("Reading all not ended Tours")
        stmt = select(Tour).where(
            Tour.ended_at == None
        ).order_by(desc(Tour.started_at))
        return session.execute(stmt).scalars().all()


def get_all_ended_tours_by_period(start_date: datetime, end_date: datetime) -> list[Tour]:
    start_date = utc_datetime(start_date)
    end_date = utc_datetime(end_date)
    with Session() as session:
        log.debug(f"Reading all ended Tours by period [{start_date.isoformat()};{end_date.isoformat()}]")
        stmt = select(Tour).where(
            and_(
                Tour.ended_at != None,
                Tour.started_at >= start_date,
                Tour.ended_at <= end_date,
            )
        ).order_by(desc(Tour.started_at))
        return session.execute(stmt).scalars().all()


def get_tour_players_points(tour_id: int) -> dict[Player, float]:
    with Session() as session:
        tour = _get_tour(session=session, tour_id=tour_id)

        log.debug(f"Reading all Matches in Tour[id={tour.id}]")
        matches_query = select(Match).where(
            and_(
                Match.played_at >= tour.started_at,
                Match.played_at <= tour.ended_at if tour.ended_at else True
            )
        )
        matches = session.execute(matches_query).scalars().all()

        pair_ids = set()
        for match in matches:
            pair_ids.add(match.players_pair_id_1)
            pair_ids.add(match.players_pair_id_2)
        if not pair_ids:
            return {}

        log.debug(f"Reading all PlayersPairs in Tour[id={tour.id}]")
        pairs_query = select(PlayersPair).where(PlayersPair.id.in_(pair_ids))
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
        players_query = select(Player).where(Player.id.in_(all_player_ids))
        result = {
            player: (points[player.id] / 2)
            for player in session.execute(players_query).scalars().all()
        }

        return dict(sorted(result.items(), key=lambda i: i[1], reverse=True))
