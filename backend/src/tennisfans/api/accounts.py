from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import ColumnElement, delete, func, select

from tennisfans.api import contracts as dto
from tennisfans.api.context import Actor, Database, Environment, SignedIn, session_token
from tennisfans.core.errors import conflict, invalid
from tennisfans.db.accounts import Audit, LoginSession, Notification, User
from tennisfans.domain.permissions import Role, require_admin
from tennisfans.modules import auth, statistics, views
from tennisfans.modules.facts import load_user

router = APIRouter()
Search = Annotated[str, Query(max_length=120)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


def _managed(user: User, public: dto.PublicUser) -> dto.ManagedUser:
    return dto.ManagedUser(**public.model_dump(), role=user.role)


def _account(
    db: Database, env: Environment, user: User, token: str, restricted: bool
) -> dto.Account:
    return dto.Account(
        user=_managed(user, views.public_users(db, [user])[user.id]),
        csrf=auth.csrf(env.settings, token),
        password_change_required=restricted,
    )


def _cookie(response: Response, env: Environment, token: str) -> None:
    response.set_cookie(
        auth.COOKIE,
        token,
        httponly=True,
        secure=env.settings.secure_cookies,
        samesite=env.settings.same_site,
        max_age=env.settings.session_hours * 3600,
    )


@router.post("/auth/register", status_code=201, tags=["auth"])
def register(
    payload: dto.Registration, response: Response, db: Database, env: Environment
) -> dto.Account:
    display = payload.display_name.strip() if payload.display_name else None
    if payload.display_name and not display:
        raise invalid("invalid_display_name", "Display name must include a visible character")
    user = auth.create_user(db, payload.username, payload.password, display)
    token = auth.open_session(db, env.settings, user)
    _cookie(response, env, token)
    return _account(db, env, user, token, False)


@router.post("/auth/login", tags=["auth"])
def login(
    payload: dto.Credentials, request: Request, response: Response, db: Database, env: Environment
) -> dto.Account:
    user, token = auth.sign_in(
        db, env.settings, payload.username, payload.password, session_token(request)
    )
    _cookie(response, env, token)
    return _account(db, env, user, token, user.reset_expires_at is not None)


@router.get("/auth/session", tags=["auth"])
def session(request: Request, db: Database, env: Environment, authn: SignedIn) -> dto.Account:
    return _account(db, env, authn[0], session_token(request), authn[1].restricted)


@router.post("/auth/logout", status_code=204, tags=["auth"])
def logout(response: Response, db: Database, env: Environment, authn: SignedIn) -> None:
    db.delete(authn[1])
    auth.audit(db, "auth.logout", authn[0], authn[0])
    response.delete_cookie(
        auth.COOKIE,
        httponly=True,
        secure=env.settings.secure_cookies,
        samesite=env.settings.same_site,
    )


@router.post("/auth/password", tags=["auth"])
def change_password(
    payload: dto.Passwords, response: Response, db: Database, env: Environment, authn: SignedIn
) -> dto.Account:
    user, current = authn
    token = auth.rotate_password(
        db, env.settings, user, current, payload.old_password, payload.new_password
    )
    _cookie(response, env, token)
    return _account(db, env, user, token, False)


@router.patch("/account", tags=["users"])
def profile(payload: dto.Profile, db: Database, user: Actor) -> dto.ManagedUser:
    user.display_name = payload.display_name
    auth.audit(db, "user.profile", user, user)
    return _managed(user, views.public_users(db, [user])[user.id])


@router.get("/account/notifications", tags=["users"])
def notifications(
    db: Database, user: Actor, offset: Offset = 0, limit: Limit = 30
) -> dto.Page[dto.NotificationView]:
    query = select(Notification).where(Notification.user_id == user.id)
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    items = db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id).offset(offset).limit(limit)
    )
    return dto.Page(
        items=[dto.NotificationView.model_validate(item) for item in items], total=total
    )


def _user_query(q: str) -> ColumnElement[bool]:
    return User.username.icontains(q, autoescape=True) | User.display_name.icontains(
        q, autoescape=True
    )


@router.get("/public/users", tags=["users"])
def directory(
    db: Database, q: Search = "", offset: Offset = 0, limit: Limit = 30
) -> dto.Page[dto.PublicUser]:
    query = select(User).where(_user_query(q))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    users = list(
        db.scalars(
            query.order_by(func.lower(User.display_name), User.id).offset(offset).limit(limit)
        )
    )
    return dto.Page(items=list(views.public_users(db, users).values()), total=total)


@router.get("/public/users/{user_id}", tags=["users", "statistics"])
def player(user_id: UUID, db: Database) -> dto.PlayerStats:
    return statistics.player_stats(db, user_id)


@router.get("/public/ratings", tags=["ratings"])
def ratings(
    db: Database, q: Search = "", offset: Offset = 0, limit: Limit = 30
) -> dto.Page[dto.Leader]:
    return statistics.leaderboard(db, q, offset, limit)


@router.get("/public/ratings/{user_id}/history", tags=["ratings"])
def history(user_id: UUID, db: Database) -> list[dto.Point]:
    load_user(db, user_id)
    return views.points(db, [user_id]).get(user_id, [])


@router.get("/public/stats/compare/{a}/{b}", tags=["statistics"])
def compare(a: UUID, b: UUID, db: Database) -> dto.PairStats:
    if a == b:
        raise invalid("comparison_players", "Choose two different players")
    load_user(db, b)
    return statistics.pair(db, a, b)


@router.get("/admin/users", tags=["admin"])
def admin_users(
    db: Database, actor: Actor, q: Search = "", offset: Offset = 0, limit: Limit = 30
) -> dto.Page[dto.ManagedUser]:
    require_admin(actor.role)
    query = select(User).where(_user_query(q))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(
        db.scalars(query.order_by(func.lower(User.username), User.id).offset(offset).limit(limit))
    )
    public = views.public_users(db, rows)
    return dto.Page(items=[_managed(row, public[row.id]) for row in rows], total=total)


@router.patch("/admin/users/{user_id}", tags=["admin"])
def update_user(
    user_id: UUID, payload: dto.UserEdit, db: Database, actor: Actor
) -> dto.ManagedUser:
    require_admin(actor.role)
    user = load_user(db, user_id)
    found = auth.username_lookup(db, payload.username)
    if found and found.id != user.id:
        raise conflict("username_taken", "This username is already in use")
    if (
        user.role == Role.ADMIN
        and user.active
        and (not payload.active or payload.role != Role.ADMIN)
    ):
        admins = db.scalar(
            select(func.count()).select_from(User).where(User.role == Role.ADMIN, User.active)
        )
        if admins == 1:
            raise conflict("last_admin", "Keep at least one active administrator")
    if user.active != payload.active or user.role != payload.role:
        db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    user.active = payload.active
    user.role = payload.role
    user.display_name = payload.display_name
    user.username = payload.username
    auth.audit(db, "user.admin_edit", actor, user)
    return _managed(user, views.public_users(db, [user])[user.id])


@router.post("/admin/users/{user_id}/reset", tags=["admin"])
def admin_reset(user_id: UUID, db: Database, env: Environment, actor: Actor) -> dto.Reset:
    require_admin(actor.role)
    user = load_user(db, user_id)
    temporary = auth.reset_password(db, env.settings, actor, user)
    expiry = user.reset_expires_at
    if expiry is None:
        raise RuntimeError("Credential reset did not set an expiry")
    return dto.Reset(temporary_password=temporary, expires_at=expiry)


@router.get("/admin/audit", tags=["admin"])
def admin_audit(
    db: Database, actor: Actor, action: Search = "", offset: Offset = 0, limit: Limit = 30
) -> dto.Page[dto.AuditView]:
    require_admin(actor.role)
    query = select(Audit)
    if action:
        query = query.where(Audit.action.startswith(action, autoescape=True))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = db.scalars(
        query.order_by(Audit.created_at.desc(), Audit.id.desc()).offset(offset).limit(limit)
    )
    return dto.Page(items=[dto.AuditView.model_validate(item) for item in rows], total=total)
