import logging
from collections.abc import Iterator
from dataclasses import dataclass
from hmac import compare_digest
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session, sessionmaker

from tennisfans.core.config import Settings
from tennisfans.core.errors import Problem, forbidden
from tennisfans.db.accounts import LoginSession, User
from tennisfans.db.runtime import lock
from tennisfans.modules import auth
from tennisfans.modules.storage import LocalStorage

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Runtime:
    settings: Settings
    db: sessionmaker[Session]
    storage: LocalStorage


def runtime(request: Request) -> Runtime:
    return cast(Runtime, request.app.state.runtime)


Environment = Annotated[Runtime, Depends(runtime)]


def transaction(request: Request, env: Environment) -> Iterator[Session]:
    write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    with env.db() as db:
        if write:
            lock(db)
        else:
            db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        try:
            yield db
        except BaseException:
            db.rollback()
            for item in db.info.get("media_created", []):
                try:
                    env.storage.remove(item)
                except OSError:
                    log.warning("Temporary image %s will be swept later", item)
            raise
        if write:
            # If the driver loses its connection during commit, the outcome can
            # be unknown. A grace-period sweep safely finds any unreferenced file.
            db.commit()


Database = Annotated[Session, Depends(transaction, scope="function")]
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def session_token(request: Request) -> str:
    return request.cookies.get(auth.COOKIE, "")


def current(request: Request, db: Database, env: Environment) -> tuple[User, LoginSession]:
    token = session_token(request)
    match = auth.get_session(db, token)
    if match is None:
        raise Problem(401, "authentication_required", "Sign in to continue")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.headers.get("X-CSRF-Token", "")
        if not supplied.isascii() or not compare_digest(supplied, auth.csrf(env.settings, token)):
            raise Problem(403, "invalid_csrf", "The request has no valid CSRF token")
    return match


SignedIn = Annotated[tuple[User, LoginSession], Depends(current)]


def actor(session: SignedIn) -> User:
    if session[1].restricted:
        raise forbidden()
    return session[0]


Actor = Annotated[User, Depends(actor)]
