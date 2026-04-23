from datetime import datetime
from sqlalchemy import and_, desc, select
from database.base import MatchEntity, PlayerEntity, PlayersPairEntity, Session, TourEntity
import settings
from utils import dto


log = settings.ProjectLoggerFactory.get_for("database.general")


def _to_player_dto(player: PlayerEntity) -> dto.PlayerDTO:
    log.debug(f"Exporting Player[id={player.id}] to PlayerDTO")
    return dto.PlayerDTO(
        id=player.id,
        name=player.name,
        registered_at=player.registered_at,
    )


def _to_tour_dto(tour: TourEntity) -> dto.TourDTO:
    log.debug(f"Exporting Tour[id={tour.id}] to TourDTO")
    return dto.TourDTO(
        id=tour.id,
        name=tour.name,
        started_at=tour.started_at,
        ended_at=tour.ended_at,
    )


def _to_players_pair_dto(player1: PlayerEntity, player2: PlayerEntity) -> dto.PlayersPairDTO:
    log.debug(f"Exporting Players[id={player1.id},{player2.id}] to PlayersPairDTO")
    players_id_dto = {
        player1.id: _to_player_dto(player=player1),
        player2.id: _to_player_dto(player=player2),
    }
    player1_id, player2_id = sorted(players_id_dto.keys())
    return dto.PlayersPairDTO(
        player1_dto=players_id_dto[player1_id],
        player2_dto=players_id_dto[player2_id],
    )


def _to_match_dto(match: MatchEntity, pair1: tuple[PlayerEntity, PlayerEntity], pair2: tuple[PlayerEntity, PlayerEntity]) -> dto.MatchDTO:
    log.debug(f"Exporting Match[id={match.id}]&Players[id={pair1[0].id},{pair1[1].id},{pair2[0].id},{pair2[1].id}] to MatchDTO")
    return dto.MatchDTO(
        id=match.id,
        played_at=match.played_at,
        players_pair1_dto=_to_players_pair_dto(player1=pair1[0], player2=pair1[1]),
        players_pair2_dto=_to_players_pair_dto(player1=pair2[0], player2=pair2[1]),
        players_pair1_score=match.score_players_pair_1,
        players_pair2_score=match.score_players_pair_2,
    )


def _get_player(session: Session, player_id: int) -> PlayerEntity:
    log.debug(f"Reading Player[id={player_id}]")
    player = session.get(PlayerEntity, player_id)
    if not player:
        raise KeyError(f"No such Player with ID {player_id}")
    return player


def _get_tour(session: Session, tour_id: int) -> TourEntity:
    log.debug(f"Reading Tour[id={tour_id}]")
    tour = session.get(TourEntity, tour_id)
    if not tour:
        raise KeyError(f"No such Tour with ID {tour_id}")
    return tour


def _get_or_create_players_pair(session: Session, player1_id: int, player2_id: int) -> PlayersPairEntity:
    player1_id, player2_id = sorted([player1_id, player2_id])
    log.debug(f"Reading PlayersPair[player1_id={player1_id};player2_id={player2_id}]")
    pair = session.query(PlayersPairEntity).filter(
        PlayersPairEntity.player1_id == player1_id,
        PlayersPairEntity.player2_id == player2_id,
    ).first()
    if not pair:
        log.debug(f"Creating PlayersPair[player1_id={player1_id};player2_id={player2_id}]")
        pair = PlayersPairEntity(player1_id=player1_id, player2_id=player2_id)
        session.add(pair)
        session.flush()
        session.refresh(pair)
        log.debug(f"Create PlayersPair[id={pair.id}]")
    return pair


def _get_pair_players(session: Session, players_pair: PlayersPairEntity = None, players_pair_id: int = None) -> tuple[PlayerEntity, PlayerEntity]:
    if players_pair is None:
        if players_pair_id is None:
            raise ValueError("Can't get Players without PlayersPair")
        log.debug(f"Reading PlayersPair[id={players_pair_id}]")
        players_pair = session.get(PlayersPairEntity, players_pair_id)
        if not players_pair:
            raise KeyError(f"No such PlayersPair with ID {players_pair_id}")
    player1_id, player2_id = sorted([players_pair.player1_id, players_pair.player2_id])
    player1 = _get_player(session=session, player_id=player1_id)
    player2 = _get_player(session=session, player_id=player2_id)
    return player1, player2


def _get_match(session: Session, match_id: int) -> MatchEntity:
    log.debug(f"Reading Match[id={match_id}]")
    match = session.get(MatchEntity, match_id)
    if not match:
        raise KeyError(f"No such Match with ID {match_id}")
    return match


def _get_all_matches_by_period(session: Session, played_after: datetime, played_before: datetime) -> list[MatchEntity]:
    log.debug(f"Reading all Matches by period [{played_after.isoformat()};{played_before.isoformat()}]")
    stmt = select(MatchEntity).where(
        and_(
            MatchEntity.played_at >= played_after,
            MatchEntity.played_at <= played_before,
        ),
    ).order_by(desc(MatchEntity.played_at))
    return session.execute(stmt).scalars().all()
