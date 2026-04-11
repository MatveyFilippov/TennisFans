from ..base import Player, Session
from utils.datetime_utils import utc_datetime
import settings
from datetime import datetime
from sqlalchemy import asc, exists


log = settings.ProjectLoggerFactory.get_for("database.players")


def _get_player(session: Session, player_id: int) -> Player:
    log.debug(f"Reading Player[id={player_id}]")
    player = session.get(Player, player_id)
    if not player:
        raise KeyError(f"No such Player in database with ID {player_id}")
    return player


def is_player_exists(player_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Player[id={player_id}] exists")
        return bool(session.query(
            exists().where(Player.id == player_id)
        ).scalar())


def create_player(name: str, registered_at: datetime | None = None) -> Player:
    registered_at = utc_datetime(registered_at) if registered_at else None
    with Session() as session:
        log.debug("Creating new Player")
        new_player = (
            Player(name=name, registered_at=registered_at)
            if registered_at else
            Player(name=name)
        )
        session.add(new_player)
        session.commit()
        session.refresh(new_player)
        log.debug(f"Create new Player[id={new_player.id}]")
        return new_player


def get_player(player_id: int) -> Player:
    with Session() as session:
        return _get_player(session=session, player_id=player_id)


def get_all_players() -> list[Player]:
    with Session() as session:
        log.debug("Reading all Players")
        return session.query(Player).order_by(asc(Player.registered_at)).all()
