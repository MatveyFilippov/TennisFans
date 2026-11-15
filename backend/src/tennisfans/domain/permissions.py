from enum import StrEnum
from uuid import UUID

from tennisfans.core.errors import forbidden


class Role(StrEnum):
    PLAYER = "PLAYER"
    ADMIN = "ADMIN"


def require_admin(role: Role) -> None:
    if role != Role.ADMIN:
        raise forbidden()


def require_manager(role: Role, assigned: bool) -> None:
    if role != Role.ADMIN and not assigned:
        raise forbidden()


def require_participant(player: UUID, participants: tuple[UUID, ...]) -> None:
    if player not in participants:
        raise forbidden()


def require_resolver(role: Role, assigned: bool, participating: bool) -> None:
    if role != Role.ADMIN and (not assigned or participating):
        raise forbidden()


def require_opponent(
    player: UUID, author: UUID | None, a: tuple[UUID, ...], b: tuple[UUID, ...]
) -> None:
    if not ((author in a and player in b) or (author in b and player in a)):
        raise forbidden()
