from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from tennisfans.domain.permissions import Role
from tennisfans.domain.schedule import Format, Status, TeamMode
from tennisfans.domain.scoring import Discipline, Input, Rules, Score
from tennisfans.modules.tournaments import Config

Username = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
DisplayName = Field(min_length=1, max_length=80)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Username
    password: str = Field(min_length=1, max_length=128)


class Registration(Credentials):
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(None, min_length=1, max_length=80)


class Passwords(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_password: str = Field("", max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class Profile(Input):
    display_name: str = DisplayName


class UserEdit(Profile):
    username: str = Username
    active: bool
    role: Role


class PublicUser(BaseModel):
    id: UUID
    username: str
    display_name: str
    rating: float
    active: bool
    avatar_id: UUID | None = None


class ManagedUser(PublicUser):
    role: Role


class Account(BaseModel):
    user: ManagedUser
    csrf: str
    password_change_required: bool


class Reset(BaseModel):
    temporary_password: str
    expires_at: datetime


class Ref(BaseModel):
    id: UUID


class Page[T](BaseModel):
    items: list[T]
    total: int


class Photo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    width: int
    height: int
    cover: bool


class Cover(Input):
    photo_id: UUID | None


class PhotoList(BaseModel):
    items: list[Photo]


class Point(BaseModel):
    match_id: UUID
    user_id: UUID
    played_at: datetime
    rating_after: float
    delta: float


class DisputeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author_id: UUID
    reason: str
    created_at: datetime
    resolved_at: datetime | None
    resolver_id: UUID | None
    decision: str | None
    resolution_reason: str | None


class MatchView(BaseModel):
    id: UUID
    category: Literal["FRIENDLY", "TOURNAMENT"]
    discipline: Discipline
    rules: Rules
    a: list[PublicUser]
    b: list[PublicUser]
    score: Score | None
    status: Literal["SCHEDULED", "COMPLETED", "DISPUTED", "BLOCKED"]
    played_at: datetime | None
    scheduled_at: datetime | None
    author_id: UUID | None
    tournament_id: UUID | None
    version: int
    gallery: list[Photo] = Field(default_factory=list)
    rating: list[Point] = Field(default_factory=list)
    disputes: list[DisputeView] = Field(default_factory=list)


class TournamentSummary(BaseModel):
    id: UUID
    title: str
    description: str
    starts_at: datetime
    timezone: str
    completed_at: datetime | None
    status: Status
    discipline: Discipline
    format: Format
    team_mode: TeamMode | None
    capacity: int
    accepted: int
    applications_open: bool
    cover_id: UUID | None


class StandingView(BaseModel):
    players: list[PublicUser]
    rank: int
    rank_end: int
    played: int
    wins: int
    losses: int
    sets_won: int
    sets_lost: int
    games_won: int
    games_lost: int


class Placement(BaseModel):
    players: list[PublicUser]
    rank: int
    rank_end: int


class GroupView(BaseModel):
    id: UUID
    position: int
    standings: list[StandingView]


class FixtureView(BaseModel):
    id: UUID
    stage: str
    group_id: UUID | None
    round: int
    position: int
    predecessor_a_id: UUID | None
    predecessor_b_id: UUID | None
    scheduled_at: datetime
    match: MatchView | None


class TournamentView(TournamentSummary):
    config: Config
    version: int
    organizers: list[PublicUser]
    roster: list[PublicUser]
    teams: list[list[PublicUser]]
    gallery: list[Photo]
    standings: list[StandingView]
    groups: list[GroupView]
    fixtures: list[FixtureView]
    placements: list[Placement]


class ApplicationView(BaseModel):
    player: PublicUser
    status: Literal["PENDING", "ACCEPTED", "REJECTED", "WITHDRAWN"]


class ApplicationState(BaseModel):
    status: Literal["PENDING", "ACCEPTED", "REJECTED", "WITHDRAWN"] | None


class Totals(BaseModel):
    matches: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0
    sets_won: int = 0
    sets_lost: int = 0
    games_won: int = 0
    games_lost: int = 0
    current_streak: int = 0
    longest_streak: int = 0


class Leader(PublicUser):
    rank: int
    matches: int
    wins: int
    losses: int
    win_rate: float
    trend: list[float]


class TournamentFinish(BaseModel):
    tournament: TournamentSummary
    rank: int | None
    rank_end: int | None


class PlayerStats(BaseModel):
    player: PublicUser
    overall: Totals
    singles: Totals
    doubles: Totals
    recent: list[MatchView]
    tournaments: list[TournamentFinish]
    history: list[Point]
    gallery: list[Photo]


class PairStats(BaseModel):
    a: PlayerStats
    b: PlayerStats
    opponent_matches: list[MatchView]
    partner_matches: list[MatchView]
    opponent_total: int
    partner_total: int
    a_wins: int
    b_wins: int
    partner_wins: int


class AuditView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_id: UUID | None
    target_id: UUID | None
    action: str
    details: dict[str, Any]
    created_at: datetime


class NotificationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    match_id: UUID | None
    decision: str
    created_at: datetime


class ErrorBody(BaseModel):
    code: str
    detail: str
    request_id: str
    context: dict[str, Any] = Field(default_factory=dict)
