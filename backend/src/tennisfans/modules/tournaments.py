import logging
import secrets
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from tennisfans.core.errors import conflict, invalid, missing
from tennisfans.db.accounts import User
from tennisfans.db.base import now
from tennisfans.db.competition import (
    Application,
    Entry,
    EntryMember,
    Fixture,
    Membership,
    Organizer,
    Stage,
    Tournament,
)
from tennisfans.db.media import Media
from tennisfans.db.results import Match
from tennisfans.db.runtime import lock
from tennisfans.domain.permissions import require_admin, require_manager
from tennisfans.domain.schedule import Format, Seeding, Status, TeamMode, validate_capacity
from tennisfans.domain.scoring import Discipline, Input, Rules
from tennisfans.modules.brackets import start
from tennisfans.modules.facts import delete_photos, load_user, record_audit
from tennisfans.modules.ratings import rebuild

logger = logging.getLogger(__name__)
PRESTART = {Status.SCHEDULED, Status.ACTION_REQUIRED}
UserList = Annotated[list[UUID], Field(max_length=128)]


class Config(Input):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=5000)
    starts_at: AwareDatetime = Field(default_factory=now)
    timezone: str = Field("UTC", max_length=80)
    discipline: Discipline
    format: Format
    team_mode: TeamMode | None = None
    capacity: int = Field(ge=2, le=128)
    applications_open: bool = True
    rules: Rules = Field(default_factory=Rules)
    group_count: int | None = Field(None, ge=2, le=32)
    qualifiers: int | None = Field(None, ge=1, le=32)
    cycles: int = Field(1, ge=1, le=3)
    seeding: Seeding = Seeding.SEED_ORDER
    seed: int = Field(default_factory=lambda: secrets.randbelow(2**31), ge=0, lt=2**31)
    slot_minutes: int = Field(0, ge=0, le=1440)

    @model_validator(mode="after")
    def valid(self) -> "Config":
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use a valid IANA time zone") from exc
        if self.format == Format.GROUPS_THEN_PLAYOFFS:
            if self.group_count is None:
                self.group_count = 2
            if self.qualifiers is None:
                self.qualifiers = 1
        validate_capacity(
            self.discipline,
            self.format,
            self.team_mode,
            self.capacity,
            self.group_count,
            self.qualifiers,
        )
        if self.cycles > 1 and self.team_mode == TeamMode.ROTATING_PARTNERS:
            raise ValueError("Rotation generates its own balanced cycle")
        if self.cycles > 1 and self.format == Format.SINGLE_ELIMINATION:
            raise ValueError("Knockout matches do not have round robin cycles")
        return self


class Create(Config):
    participants: UserList = Field(default_factory=list)
    organizers: list[UUID] = Field(default_factory=list)


class Edit(Config):
    version: int = Field(ge=1)


class Teams(Input):
    teams: list[tuple[UUID, UUID]] = Field(max_length=64)


class RosterAction(Input):
    action: Literal["ACCEPT", "REJECT", "ADD", "REMOVE"]


def get(db: Session, id_: UUID) -> Tournament:
    tournament = db.get(Tournament, id_)
    if not tournament:
        raise missing()
    return tournament


def is_organizer(db: Session, actor_id: UUID, tournament_id: UUID | None) -> bool:
    return tournament_id is not None and db.get(Organizer, (tournament_id, actor_id)) is not None


def manage(db: Session, actor: User, tournament: Tournament) -> None:
    require_manager(actor.role, is_organizer(db, actor.id, tournament.id))


def prestart(tournament: Tournament) -> None:
    if tournament.status not in PRESTART:
        raise conflict(
            "roster_locked", "The tournament started and its roster and rules are locked"
        )


def create(db: Session, actor: User, payload: Create) -> Tournament:
    require_admin(actor.role)
    validate_capacity(
        payload.discipline,
        payload.format,
        payload.team_mode,
        payload.capacity,
        payload.group_count,
        payload.qualifiers,
    )
    if len(payload.participants) > payload.capacity or len(set(payload.participants)) != len(
        payload.participants
    ):
        raise invalid(
            "invalid_roster", "Initial players must be distinct and fit the available slots"
        )
    if len(set(payload.organizers)) != len(payload.organizers):
        raise invalid("duplicate_organizer", "Organizer assignments must be unique")
    config = payload.model_dump(exclude={"participants", "organizers"})
    config["rules"] = payload.rules.model_dump(mode="json")
    tournament = Tournament(**config)
    db.add(tournament)
    db.flush()
    for index, user_id in enumerate(payload.participants, 1):
        load_user(db, user_id)
        db.add(Membership(tournament_id=tournament.id, user_id=user_id, position=index))
        record_audit(db, "tournament.roster.add", tournament.id, actor.id, user=str(user_id))
    for user_id in payload.organizers:
        set_organizer(db, actor, tournament, user_id, True)
    record_audit(db, "tournament.create", tournament.id, actor.id, capacity=tournament.capacity)
    return tournament


def edit(db: Session, actor: User, tournament: Tournament, payload: Edit) -> None:
    require_admin(actor.role)
    prestart(tournament)
    if payload.version != tournament.version:
        raise conflict("stale_version", "The tournament changed. Reload and try again")
    accepted = int(
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.tournament_id == tournament.id)
        )
        or 0
    )
    if payload.capacity < accepted:
        raise conflict("capacity_below_roster", "Capacity cannot be less than the accepted roster")
    meets_fixed = payload.team_mode == TeamMode.FIXED_TEAMS
    if tournament.team_mode == TeamMode.FIXED_TEAMS and not meets_fixed:
        db.execute(delete(Entry).where(Entry.tournament_id == tournament.id))
    if tournament.starts_at != payload.starts_at:
        tournament.status = Status.SCHEDULED
    config = payload.model_dump(exclude={"version"})
    config["rules"] = payload.rules.model_dump(mode="json")
    for key, value in config.items():
        setattr(tournament, key, value)
    tournament.version += 1
    record_audit(db, "tournament.edit", tournament.id, actor.id, version=tournament.version)


def set_organizer(
    db: Session, actor: User, tournament: Tournament, user_id: UUID, enabled: bool
) -> None:
    require_admin(actor.role)
    load_user(db, user_id)
    assignment = db.get(Organizer, (tournament.id, user_id))
    if enabled and not assignment:
        db.add(Organizer(tournament_id=tournament.id, user_id=user_id))
    elif not enabled and assignment:
        db.delete(assignment)
    else:
        return
    record_audit(
        db, "tournament.organizer", tournament.id, actor.id, user=str(user_id), assigned=enabled
    )


def apply(db: Session, actor: User, tournament: Tournament, *, withdraw: bool) -> None:
    prestart(tournament)
    key = (tournament.id, actor.id)
    application = db.get(Application, key)
    if withdraw:
        if application is None or application.status != "PENDING":
            raise conflict("no_pending_application", "Only a pending application can be withdrawn")
        application.status = "WITHDRAWN"
    else:
        if not tournament.applications_open:
            raise conflict("applications_closed", "Applications are closed")
        if db.get(Membership, key) or (application and application.status != "WITHDRAWN"):
            raise conflict(
                "duplicate_application", "The player already joined or submitted an application"
            )
        if application is None:
            db.add(Application(tournament_id=tournament.id, user_id=actor.id, status="PENDING"))
        else:
            application.status = "PENDING"
    record_audit(
        db, "tournament.withdraw" if withdraw else "tournament.apply", tournament.id, actor.id
    )


def roster_action(
    db: Session, actor: User, tournament: Tournament, user_id: UUID, payload: RosterAction
) -> None:
    manage(db, actor, tournament)
    prestart(tournament)
    load_user(db, user_id)
    key = (tournament.id, user_id)
    member = db.get(Membership, key)
    application = db.get(Application, key)
    if payload.action in {"ACCEPT", "REJECT"} and (
        application is None or application.status != "PENDING"
    ):
        raise conflict(
            "no_pending_application", "The selected player does not have a pending application"
        )

    if payload.action == "REMOVE":
        if member is None:
            raise missing()
        entry_member = db.get(EntryMember, key)
        if entry_member is not None:
            db.execute(delete(Entry).where(Entry.id == entry_member.entry_id))
        db.delete(member)
        if application and application.status == "ACCEPTED":
            application.status = "WITHDRAWN"
    elif payload.action == "REJECT":
        if application is not None:
            application.status = "REJECTED"
    else:
        if member:
            raise conflict("duplicate_member", "Player is already in the roster")
        occupied = list(
            db.scalars(select(Membership.position).where(Membership.tournament_id == tournament.id))
        )
        if len(occupied) >= tournament.capacity:
            raise conflict("capacity_full", "No accepted-player slots are available")
        db.add(
            Membership(
                tournament_id=tournament.id, user_id=user_id, position=max(occupied, default=0) + 1
            )
        )
        if application:
            application.status = "ACCEPTED"
    tournament.version += 1
    record_audit(
        db,
        f"tournament.roster.{payload.action.lower()}",
        tournament.id,
        actor.id,
        user=str(user_id),
    )


def set_teams(db: Session, actor: User, tournament: Tournament, payload: Teams) -> None:
    manage(db, actor, tournament)
    prestart(tournament)
    if tournament.team_mode != TeamMode.FIXED_TEAMS:
        raise invalid("invalid_teams", "Only fixed doubles has persistent teams")
    players = [player for team in payload.teams for player in team]
    roster = set(
        db.scalars(select(Membership.user_id).where(Membership.tournament_id == tournament.id))
    )
    if len(players) != len(set(players)) or not set(players) <= roster:
        raise invalid("invalid_teams", "Teams require disjoint pairs of accepted players")
    db.execute(delete(Entry).where(Entry.tournament_id == tournament.id))
    for team in payload.teams:
        entry = Entry(tournament_id=tournament.id)
        db.add(entry)
        db.flush()
        db.add_all(
            EntryMember(tournament_id=tournament.id, entry_id=entry.id, user_id=player)
            for player in team
        )
    tournament.version += 1
    record_audit(db, "tournament.teams", tournament.id, actor.id, teams=len(payload.teams))


def delete_tournament(db: Session, actor: User, tournament: Tournament, k: int) -> None:
    require_admin(actor.role)
    matches = select(Match.id).join(Fixture).join(Stage).where(Stage.tournament_id == tournament.id)
    delete_photos(
        db,
        list(
            db.scalars(
                select(Media).where(
                    (Media.tournament_id == tournament.id) | Media.match_id.in_(matches)
                )
            )
        ),
    )
    db.flush()
    db.execute(delete(Stage).where(Stage.tournament_id == tournament.id))
    db.execute(delete(Tournament).where(Tournament.id == tournament.id))
    record_audit(db, "tournament.delete", tournament.id, actor.id)
    rebuild(db, k)


def reconcile_due(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        ids = list(
            db.scalars(
                select(Tournament.id)
                .where(Tournament.status == Status.SCHEDULED, Tournament.starts_at <= now())
                .order_by(Tournament.starts_at, Tournament.id)
            )
        )
    for id_ in ids:
        try:
            with factory.begin() as db:
                lock(db)
                tournament = db.get(Tournament, id_, with_for_update=True)
                if (
                    tournament
                    and tournament.status == Status.SCHEDULED
                    and tournament.starts_at <= now()
                ):
                    validate_capacity(
                        tournament.discipline,
                        tournament.format,
                        tournament.team_mode,
                        tournament.capacity,
                        tournament.group_count,
                        tournament.qualifiers,
                    )
                    start(db, tournament)
        except Exception:
            logger.exception("Tournament reconciliation failed for %s", id_)
