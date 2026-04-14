from ..base import Session, PlayerEntity
from utils import dto
from utils.datetime_utils import utc_datetime
import settings
from datetime import datetime
from sqlalchemy import asc, exists


log = settings.ProjectLoggerFactory.get_for("database.players")


def _get_player_dto(player: PlayerEntity) -> dto.PlayerDTO:
    log.debug(f"Exporting Player[id={player.id}] to PlayerDTO")
    return dto.PlayerDTO(
        id=player.id,
        name=player.name,
        registered_at=player.registered_at,
    )


def _get_player(session: Session, player_id: int) -> PlayerEntity:
    log.debug(f"Reading Player[id={player_id}]")
    player = session.get(PlayerEntity, player_id)
    if not player:
        raise KeyError(f"No such Player with ID {player_id}")
    return player


def is_player_exists(player_id: int) -> bool:
    with Session() as session:
        log.debug(f"Checking if Player[id={player_id}] exists")
        return bool(session.query(
            exists().where(PlayerEntity.id == player_id)
        ).scalar())


def create_player(name: str, registered_at: datetime | None = None) -> dto.PlayerDTO:
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
        return _get_player_dto(player=new_player)


def edit_player(player_id: int, name: str | None = None) -> dto.PlayerDTO:
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

        return _get_player_dto(player=player)


def delete_player(player_id: int):
    with Session() as session:
        player = _get_player(session=session, player_id=player_id)
        session.delete(player)
        session.commit()
        log.debug(f"Delete Player[id={player_id}]")


def get_player(player_id: int) -> dto.PlayerDTO:
    with Session() as session:
        return _get_player_dto(player=_get_player(session=session, player_id=player_id))


def get_all_players() -> list[dto.PlayerDTO]:
    with Session() as session:
        log.debug("Reading all Players")
        players = session.query(PlayerEntity).order_by(asc(PlayerEntity.registered_at)).all()
        return [_get_player_dto(player=player) for player in players]
