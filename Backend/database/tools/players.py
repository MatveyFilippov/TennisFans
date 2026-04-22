from datetime import datetime
from sqlalchemy import asc, exists
import settings
from utils import dto
from utils.datetime_utils import utc_datetime
from .general import _get_player, _to_player_dto
from ..base import PlayerEntity, Session


log = settings.ProjectLoggerFactory.get_for("database.players")


def is_player_exists(player_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Player[id={player_id}] exists")
        return bool(
            session.query(
                exists().where(PlayerEntity.id == player_id),
            ).scalar(),
        )


def create_player(name: str, registered_at: datetime = None) -> dto.PlayerDTO:
    registered_at = utc_datetime(registered_at) if registered_at else None
    with Session() as session:
        log.debug("Creating new Player")
        new_player = PlayerEntity(
            name=name,
        )
        if registered_at is not None:
            new_player.registered_at = registered_at
        session.add(new_player)
        session.commit()
        session.refresh(new_player)
        log.debug(f"Create new Player[id={new_player.id}]")
        return _to_player_dto(player=new_player)


def edit_player(player_id: int, name: str = None) -> dto.PlayerDTO:
    with Session() as session:
        player = _get_player(session=session, player_id=player_id)

        log.debug(f"Looking for changes in Player[id={player.id}]")
        is_edit = False
        if name is not None and player.name != name:
            player.name = name
            is_edit = True

        if is_edit:
            session.commit()
            session.refresh(player)
            log.debug(f"Edit Player[id={player.id}]")
        else:
            log.debug(f"Don't edit Player[id={player.id}], already in target state")

        return _to_player_dto(player=player)


def delete_player(player_id: int):
    with Session() as session:
        player = _get_player(session=session, player_id=player_id)
        session.delete(player)
        session.commit()
        log.debug(f"Delete Player[id={player_id}]")


def get_player(player_id: int) -> dto.PlayerDTO:
    with Session() as session:
        player = _get_player(session=session, player_id=player_id)
        return _to_player_dto(player=player)


def get_all_players() -> list[dto.PlayerDTO]:
    with Session() as session:
        log.debug("Reading all Players")
        players = session.query(PlayerEntity).order_by(asc(PlayerEntity.registered_at)).all()
        return [_to_player_dto(player=player) for player in players]
