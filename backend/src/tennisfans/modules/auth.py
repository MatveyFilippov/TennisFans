import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from tennisfans.core.config import Settings
from tennisfans.core.errors import Problem, conflict, invalid
from tennisfans.db.accounts import Audit, LoginSession, RateBucket, User
from tennisfans.db.base import now
from tennisfans.domain.permissions import Role

COOKIE = "tennisfans_session"
hasher = PasswordHasher()
SPENT_RESET = "!"
DUMMY = hasher.hash(secrets.token_urlsafe(32))


def audit(db: Session, action: str, user: User | None, target: User | None = None) -> None:
    db.add(
        Audit(
            action=action,
            actor_id=user.id if user else None,
            target_id=target.id if target else None,
            details={},
        )
    )


def rate_limit(
    db_factory: sessionmaker[Session], category: str, identity: str, maximum: int, seconds: int
) -> None:
    slot = int(now().timestamp()) // seconds
    key = hashlib.sha256(f"{category}:{identity}:{slot}".encode()).hexdigest()
    with db_factory.begin() as db:
        statement = insert(RateBucket).values(
            key=key, expires_at=now() + timedelta(seconds=seconds), count=1
        )
        count = db.scalar(
            statement.on_conflict_do_update(
                index_elements=[RateBucket.key], set_={"count": RateBucket.count + 1}
            ).returning(RateBucket.count)
        )
    if count is not None and count > maximum:
        raise Problem(
            429, "rate_limited", "Too many requests. Try again later", retry_after=seconds
        )


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf(settings: Settings, token: str) -> str:
    return hmac.digest(
        settings.session_secret.get_secret_value().encode(), token.encode(), "sha256"
    ).hex()


def username_lookup(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.username) == username.lower()))


def check_password(password: str) -> None:
    if not 12 <= len(password) <= 128:
        raise invalid("invalid_password", "Password length must be between 12 and 128 characters")


def create_user(
    db: Session, username: str, password: str, display_name: str | None, role: Role = Role.PLAYER
) -> User:
    check_password(password)
    if username_lookup(db, username):
        raise conflict("username_taken", "This username is already in use")
    user = User(
        username=username,
        display_name=display_name or username,
        password_hash=hasher.hash(password),
        role=role,
    )
    db.add(user)
    db.flush()
    audit(db, "auth.register" if role == Role.PLAYER else "auth.bootstrap", user, user)
    return user


def verify(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (InvalidHashError, VerificationError):
        return False


def open_session(db: Session, settings: Settings, user: User, *, restricted: bool = False) -> str:
    token = secrets.token_urlsafe(32)
    expiry = (
        user.reset_expires_at if restricted else now() + timedelta(hours=settings.session_hours)
    )
    db.add(
        LoginSession(
            digest=token_digest(token), user_id=user.id, expires_at=expiry, restricted=restricted
        )
    )
    return token


def sign_in(
    db: Session, settings: Settings, username: str, password: str, old_token: str
) -> tuple[User, str]:
    user = username_lookup(db, username)
    encoded = user.password_hash if user and user.password_hash != SPENT_RESET else DUMMY
    matches = verify(encoded, password)
    if (
        user is None
        or not user.active
        or encoded == DUMMY
        or not matches
        or (user.reset_expires_at is not None and user.reset_expires_at <= now())
    ):
        raise Problem(401, "invalid_credentials", "Invalid username or password")
    restricted = user.reset_expires_at is not None
    if restricted:
        user.password_hash = SPENT_RESET
    elif hasher.check_needs_rehash(encoded):
        user.password_hash = hasher.hash(password)
    if old_token:
        db.execute(delete(LoginSession).where(LoginSession.digest == token_digest(old_token)))
    audit(db, "auth.login", user, user)
    return user, open_session(db, settings, user, restricted=restricted)


def get_session(db: Session, token: str) -> tuple[User, LoginSession] | None:
    if not token or len(token) > 64:
        return None
    session = db.get(LoginSession, token_digest(token))
    if session and session.expires_at > now():
        user = db.get(User, session.user_id)
        if user and user.active:
            return user, session
    return None


def invalidate_sessions(db: Session, user: User) -> None:
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))


def rotate_password(
    db: Session, settings: Settings, user: User, session: LoginSession, old: str, new: str
) -> str:
    check_password(new)
    if not session.restricted and (not verify(user.password_hash, old) or new == old):
        raise invalid(
            "invalid_password", "Provide the current password and a different new password"
        )
    user.password_hash = hasher.hash(new)
    user.reset_expires_at = None
    invalidate_sessions(db, user)
    audit(db, "auth.password", user, user)
    return open_session(db, settings, user)


def reset_password(db: Session, settings: Settings, actor: User, target: User) -> str:
    temporary = secrets.token_urlsafe(24)
    target.password_hash = hasher.hash(temporary)
    target.reset_expires_at = now() + timedelta(minutes=settings.reset_minutes)
    invalidate_sessions(db, target)
    audit(db, "auth.reset", actor, target)
    return temporary
