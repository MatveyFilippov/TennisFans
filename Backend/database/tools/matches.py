from .players import _get_player
from .tours import _get_tour
from ..base import Player, PlayersPair, Match, Session
from utils.datetime_utils import utc_datetime
import settings
from datetime import datetime
from sqlalchemy import and_, desc, exists, or_, select


log = settings.ProjectLoggerFactory.get_for("database.matches")


def _get_or_create_players_pair(session: Session, player1_id: int, player2_id: int) -> PlayersPair:
    p1_id, p2_id = sorted([player1_id, player2_id])
    log.debug(f"Reading PlayersPair[player1_id={player1_id};player2_id={player2_id}]")
    pair = session.query(PlayersPair).filter(
        PlayersPair.player1_id == p1_id,
        PlayersPair.player2_id == p2_id
    ).first()
    if not pair:
        log.debug(f"Creating PlayersPair[player1_id={player1_id};player2_id={player2_id}]")
        pair = PlayersPair(player1_id=p1_id, player2_id=p2_id)
        session.add(pair)
    return pair


def get_pair_players(players_pair_id: int) -> tuple[Player, Player]:
    with Session() as session:
        log.debug(f"Reading PlayersPair[id={players_pair_id}]")
        players_pair = session.get(PlayersPair, players_pair_id)
        if not players_pair:
            raise KeyError(f"No such PlayersPair in database with ID {players_pair_id}")
        player1 = _get_player(session=session, player_id=players_pair.player1_id)
        player2 = _get_player(session=session, player_id=players_pair.player2_id)
        return player1, player2


def get_players_pair_last_play(tour_id: int) -> dict[tuple[Player, Player], datetime]:
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

        pair_history = {}
        for match in matches:
            log.debug(f"Reading Players from Match[id={match.id}]")
            pair1 = get_pair_players(match.players_pair_id_1)
            pair2 = get_pair_players(match.players_pair_id_2)
            for players_pair in [pair1, pair2]:
                if players_pair not in pair_history or match.played_at > pair_history[players_pair]:
                    pair_history[players_pair] = match.played_at

        return pair_history


def is_match_exists(match_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Match[id={match_id}] exists")
        return bool(session.query(
            exists().where(Match.id == match_id)
        ).scalar())


def register_match(players_pair_1_ids: tuple[int, int], players_pair_2_ids: tuple[int, int], players_pair_1_score: int, players_pair_2_score: int, played_at: datetime | None = None) -> Match:
    played_at = utc_datetime(played_at) if played_at else None
    with Session() as session:
        players_pair_1 = _get_or_create_players_pair(session=session, player1_id=players_pair_1_ids[0], player2_id=players_pair_1_ids[1])
        players_pair_2 = _get_or_create_players_pair(session=session, player1_id=players_pair_2_ids[0], player2_id=players_pair_2_ids[1])
        session.flush()
        log.debug(f"Read or Create PlayersPair[ids={players_pair_1.id},{players_pair_2.id}]")
        log.debug("Registering new Match")
        new_match = (
            Match(
                players_pair_id_1=players_pair_1.id,
                players_pair_id_2=players_pair_2.id,
                score_players_pair_1=players_pair_1_score,
                score_players_pair_2=players_pair_2_score,
                played_at=played_at,
            )
            if played_at else
            Match(
                players_pair_id_1=players_pair_1.id,
                players_pair_id_2=players_pair_2.id,
                score_players_pair_1=players_pair_1_score,
                score_players_pair_2=players_pair_2_score,
            )
        )
        session.add(new_match)
        session.commit()
        session.refresh(new_match)
        log.debug(f"Register new Match[id={new_match.id}]")
        return new_match


def get_match(match_id: int) -> Match:
    with Session() as session:
        log.debug(f"Reading Match[id={match_id}]")
        match = session.get(Match, match_id)
        if not match:
            raise KeyError(f"No such Match in database with ID {match_id}")
        return match


def get_all_matches_for_player_by_period(player_id: int, start_date: datetime, end_date: datetime) -> list[Match]:
    start_date = utc_datetime(start_date)
    end_date = utc_datetime(end_date)
    with Session() as session:
        log.debug(f"Reading all Matches for Player[id={player_id}] by period [{start_date.isoformat()};{end_date.isoformat()}]")
        player_pairs_ids = select(PlayersPair.id).where(
            or_(
                PlayersPair.player1_id == player_id,
                PlayersPair.player2_id == player_id,
            )
        )
        stmt = select(Match).where(
            and_(
                Match.played_at >= start_date,
                Match.played_at <= end_date,
                or_(
                    Match.players_pair_id_1.in_(player_pairs_ids),
                    Match.players_pair_id_2.in_(player_pairs_ids),
                ),
            )
        ).order_by(desc(Match.played_at))
        return session.execute(stmt).scalars().all()
