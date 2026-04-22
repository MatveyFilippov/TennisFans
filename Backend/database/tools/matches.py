from .players import _get_player_dto, _get_player
from .tours import _get_tour
from ..base import Session, PlayerEntity, PlayersPairEntity, MatchEntity
from utils import dto
from utils.datetime_utils import utc_datetime
import settings
from datetime import datetime
from sqlalchemy import and_, desc, exists, or_, select


log = settings.ProjectLoggerFactory.get_for("database.matches")


def _get_players_pair_dto(player1: PlayerEntity, player2: PlayerEntity) -> dto.PlayersPairDTO:
    log.debug(f"Exporting Players[id={player1.id},{player2.id}] to PlayersPairDTO")
    players_id_dto = {
        player1.id: _get_player_dto(player=player1),
        player2.id: _get_player_dto(player=player2),
    }
    player1_id, player2_id = sorted(players_id_dto.keys())
    return dto.PlayersPairDTO(
        player1_dto=players_id_dto[player1_id],
        player2_dto=players_id_dto[player2_id],
    )


def _get_match_dto(match: MatchEntity, pair1: tuple[PlayerEntity, PlayerEntity], pair2: tuple[PlayerEntity, PlayerEntity]) -> dto.MatchDTO:
    log.debug(f"Exporting Match[id={match.id}]&Players[id={pair1[0].id},{pair1[1].id},{pair2[0].id},{pair2[1].id}] to MatchDTO")
    return dto.MatchDTO(
        id=match.id,
        played_at=match.played_at,
        players_pair1_dto=_get_players_pair_dto(player1=pair1[0], player2=pair1[1]),
        players_pair2_dto=_get_players_pair_dto(player1=pair2[0], player2=pair2[1]),
        players_pair1_score=match.score_players_pair_1,
        players_pair2_score=match.score_players_pair_2,
    )


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


class PairPlayersCache:
    def __init__(self, session: Session, cache_as_dto: bool = False):
        self.__session = session
        self.__cache = dict()
        self.__is_cache_as_dto = cache_as_dto

    def put(self, players_pair_id: int, pair_players: tuple[PlayerEntity, PlayerEntity]):
        if self.__is_cache_as_dto:
            pair_players = _get_players_pair_dto(player1=pair_players[0], player2=pair_players[1])
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
        tour = _get_tour(session=session, tour_id=tour_id)

        log.debug(f"Reading all Matches in Tour[id={tour.id}]")
        matches_query = select(MatchEntity).where(
            and_(
                MatchEntity.played_at >= tour.started_at,
                MatchEntity.played_at <= tour.ended_at if tour.ended_at else True
            )
        )
        matches = session.execute(matches_query).scalars().all()

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


def _get_match(session: Session, match_id: int) -> PlayerEntity:
    log.debug(f"Reading Match[id={match_id}]")
    match = session.get(MatchEntity, match_id)
    if not match:
        raise KeyError(f"No such Match with ID {match_id}")
    return match


def is_match_exists(match_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Match[id={match_id}] exists")
        return bool(session.query(
            exists().where(MatchEntity.id == match_id)
        ).scalar())


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
        return _get_match_dto(match=new_match, pair1=pair1_players, pair2=pair2_players)


def delete_match(match_id: int):
    with Session() as session:
        match = _get_match(session=session, match_id=match_id)
        session.delete(match)
        session.commit()
        log.debug(f"Delete Match[id={match_id}]")


def get_match(match_id: int) -> dto.MatchDTO:
    with Session() as session:
        log.debug(f"Reading Match[id={match_id}]")
        match = session.get(MatchEntity, match_id)
        if not match:
            raise KeyError(f"No such Match with ID {match_id}")
        pair1_players = _get_pair_players(session=session, players_pair_id=match.players_pair_id_1)
        pair2_players = _get_pair_players(session=session, players_pair_id=match.players_pair_id_2)
        return _get_match_dto(match=match, pair1=pair1_players, pair2=pair2_players)


def get_all_matches_by_period(played_after: datetime | None = None, played_before: datetime | None = None) -> list[dto.MatchDTO]:
    played_after = utc_datetime(played_after or datetime.min)
    played_before = utc_datetime(played_before or datetime.max)
    with Session() as session:
        log.debug(f"Reading all Matches by period [{played_after.isoformat()};{played_before.isoformat()}]")
        stmt = select(MatchEntity).where(
            and_(
                MatchEntity.played_at >= played_after,
                MatchEntity.played_at <= played_before,
            )
        ).order_by(desc(MatchEntity.played_at))
        matches = session.execute(stmt).scalars().all()

        players_pairs_cache = PairPlayersCache(session=session)
        return [
            _get_match_dto(
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
            )
        )
        stmt = select(MatchEntity).where(
            and_(
                MatchEntity.played_at >= played_after,
                MatchEntity.played_at <= played_before,
                or_(
                    MatchEntity.players_pair_id_1.in_(player_pairs_ids),
                    MatchEntity.players_pair_id_2.in_(player_pairs_ids),
                ),
            )
        ).order_by(desc(MatchEntity.played_at))
        matches = session.execute(stmt).scalars().all()

        players_pairs_cache = PairPlayersCache(session=session)
        return [
            _get_match_dto(
                match=match,
                pair1=players_pairs_cache.get(players_pair_id=match.players_pair_id_1),
                pair2=players_pairs_cache.get(players_pair_id=match.players_pair_id_2),
            ) for match in matches
        ]
