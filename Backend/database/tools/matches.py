from datetime import datetime
from sqlalchemy import and_, desc, exists, or_, select
import settings
from utils import dto
from utils.datetime_utils import utc_datetime
from .general import (
    _get_all_matches_by_period, _get_match, _get_or_create_players_pair, _get_pair_players, _get_tour,
    _to_match_dto, _to_players_pair_dto,
)
from ..base import MatchEntity, PlayerEntity, PlayersPairEntity, Session


log = settings.ProjectLoggerFactory.get_for("database.matches")


class PairPlayersCache:
    def __init__(self, session: Session, cache_as_dto: bool = False):
        self.__session = session
        self.__cache = dict()
        self.__is_cache_as_dto = cache_as_dto

    def put(self, players_pair_id: int, pair_players: tuple[PlayerEntity, PlayerEntity]):
        if self.__is_cache_as_dto:
            pair_players = _to_players_pair_dto(player1=pair_players[0], player2=pair_players[1])
        self.__cache[players_pair_id] = pair_players
        log.debug(f"Put Players[id={pair_players[0].id},{pair_players[1].id}] of PlayersPair[id={players_pair_id}] to cache")

    def take(self, players_pair_id: int) -> tuple[PlayerEntity, PlayerEntity] | dto.PlayersPairDTO:
        pair_players = self.__cache[players_pair_id]
        log.debug(f"Take Players[id={pair_players[0].id},{pair_players[1].id}] of PlayersPair[id={players_pair_id}] from cache")
        return pair_players

    def get(self, players_pair_id: int) -> tuple[PlayerEntity, PlayerEntity] | dto.PlayersPairDTO:
        if players_pair_id not in self.__cache:
            self.put(
                players_pair_id=players_pair_id,
                pair_players=_get_pair_players(session=self.__session, players_pair_id=players_pair_id),
            )
        return self.take(players_pair_id=players_pair_id)


def get_players_pair_last_play(tour_id: int) -> dict[dto.PlayersPairDTO, datetime]:
    with Session() as session:
        log.debug(f"Reading all PlayersPairs last play in Tour[id={tour_id}]")
        tour = _get_tour(session=session, tour_id=tour_id)
        matches = _get_all_matches_by_period(session=session, played_after=tour.started_at, played_before=(tour.ended_at or utc_datetime(datetime.max)))

        result = {}
        players_pair_dtos_cache = PairPlayersCache(session=session, cache_as_dto=True)
        for match in matches:
            log.debug(f"Reading Players from Match[id={match.id}]")
            pair1_players_dto = players_pair_dtos_cache.get(players_pair_id=match.players_pair_id_1)
            pair2_players_dto = players_pair_dtos_cache.get(players_pair_id=match.players_pair_id_2)
            for players_pair_dto in [pair1_players_dto, pair2_players_dto]:
                if players_pair_dto not in result or match.played_at > result[players_pair_dto]:
                    result[players_pair_dto] = match.played_at
        return result


def is_match_exists(match_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Match[id={match_id}] exists")
        return bool(
            session.query(
                exists().where(MatchEntity.id == match_id),
            ).scalar(),
        )


def register_match(players_pair_1_ids: tuple[int, int], players_pair_2_ids: tuple[int, int], players_pair_1_score: int, players_pair_2_score: int, played_at: datetime = None) -> dto.MatchDTO:
    played_at = utc_datetime(played_at) if played_at else None
    with Session() as session:
        players_pair_1 = _get_or_create_players_pair(session=session, player1_id=players_pair_1_ids[0], player2_id=players_pair_1_ids[1])
        players_pair_2 = _get_or_create_players_pair(session=session, player1_id=players_pair_2_ids[0], player2_id=players_pair_2_ids[1])
        log.debug("Registering new Match")
        new_match = MatchEntity(
            players_pair_id_1=players_pair_1.id,
            players_pair_id_2=players_pair_2.id,
            score_players_pair_1=players_pair_1_score,
            score_players_pair_2=players_pair_2_score,
        )
        if played_at is not None:
            new_match.played_at = played_at
        session.add(new_match)
        session.commit()
        session.refresh(new_match)
        log.debug(f"Register new Match[id={new_match.id}]")
        pair1_players = _get_pair_players(session=session, players_pair=players_pair_1)
        pair2_players = _get_pair_players(session=session, players_pair=players_pair_2)
        return _to_match_dto(match=new_match, pair1=pair1_players, pair2=pair2_players)


def delete_match(match_id: int):
    with Session() as session:
        match = _get_match(session=session, match_id=match_id)
        session.delete(match)
        session.commit()
        log.debug(f"Delete Match[id={match_id}]")


def get_match(match_id: int) -> dto.MatchDTO:
    with Session() as session:
        match = _get_match(session=session, match_id=match_id)
        pair1_players = _get_pair_players(session=session, players_pair_id=match.players_pair_id_1)
        pair2_players = _get_pair_players(session=session, players_pair_id=match.players_pair_id_2)
        return _to_match_dto(match=match, pair1=pair1_players, pair2=pair2_players)


def get_all_matches_by_period(played_after: datetime | None = None, played_before: datetime | None = None) -> list[dto.MatchDTO]:
    played_after = utc_datetime(played_after or datetime.min)
    played_before = utc_datetime(played_before or datetime.max)
    with Session() as session:
        matches = _get_all_matches_by_period(session=session, played_after=played_after, played_before=played_before)
        players_pairs_cache = PairPlayersCache(session=session)
        return [
            _to_match_dto(
                match=match,
                pair1=players_pairs_cache.get(players_pair_id=match.players_pair_id_1),
                pair2=players_pairs_cache.get(players_pair_id=match.players_pair_id_2),
            ) for match in matches
        ]


def get_all_matches_for_player_by_period(player_id: int, played_after: datetime | None = None, played_before: datetime | None = None) -> list[dto.MatchDTO]:
    played_after = utc_datetime(played_after or datetime.min)
    played_before = utc_datetime(played_before or datetime.max)
    with Session() as session:
        log.debug(f"Reading all Matches for Player[id={player_id}] by period [{played_after.isoformat()};{played_before.isoformat()}]")
        player_pairs_ids = select(PlayersPairEntity.id).where(
            or_(
                PlayersPairEntity.player1_id == player_id,
                PlayersPairEntity.player2_id == player_id,
            ),
        )
        stmt = select(MatchEntity).where(
            and_(
                MatchEntity.played_at >= played_after,
                MatchEntity.played_at <= played_before,
                or_(
                    MatchEntity.players_pair_id_1.in_(player_pairs_ids),
                    MatchEntity.players_pair_id_2.in_(player_pairs_ids),
                ),
            ),
        ).order_by(desc(MatchEntity.played_at))
        matches = session.execute(stmt).scalars().all()

        players_pairs_cache = PairPlayersCache(session=session)
        return [
            _to_match_dto(
                match=match,
                pair1=players_pairs_cache.get(players_pair_id=match.players_pair_id_1),
                pair2=players_pairs_cache.get(players_pair_id=match.players_pair_id_2),
            ) for match in matches
        ]
