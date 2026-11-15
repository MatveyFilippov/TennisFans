from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from tennisfans.api import contracts as dto
from tennisfans.api.accounts import Limit, Offset, Search
from tennisfans.api.context import Actor, Database, Environment, Key
from tennisfans.db.competition import Application, Fixture, Stage, Tournament
from tennisfans.db.results import Match, SidePlayer
from tennisfans.domain.permissions import require_admin
from tennisfans.domain.schedule import Status
from tennisfans.domain.scoring import Discipline
from tennisfans.modules import matches, ratings, tournaments, views
from tennisfans.modules.facts import record_audit

router = APIRouter()


@router.get("/public/matches", tags=["matches"])
def match_list(
    db: Database,
    category: Literal["FRIENDLY", "TOURNAMENT"] | None = None,
    discipline: Discipline | None = None,
    player_id: UUID | None = None,
    tournament_id: UUID | None = None,
    offset: Offset = 0,
    limit: Limit = 30,
) -> dto.Page[dto.MatchView]:
    query = select(Match)
    if category == "FRIENDLY":
        query = query.where(Match.fixture_id.is_(None))
    elif category == "TOURNAMENT":
        query = query.where(Match.fixture_id.is_not(None))
    if discipline:
        query = query.where(Match.discipline == discipline)
    if player_id:
        query = query.join(SidePlayer, SidePlayer.match_id == Match.id).where(
            SidePlayer.user_id == player_id
        )
    if tournament_id:
        query = query.join(Fixture).join(Stage).where(Stage.tournament_id == tournament_id)
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(
        db.scalars(
            query.order_by(Match.played_at.desc().nulls_last(), Match.created_at.desc(), Match.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return dto.Page(items=views.match_views(db, rows), total=total)


@router.get("/public/matches/{match_id}", tags=["matches"])
def match_detail(match_id: UUID, db: Database) -> dto.MatchView:
    return views.match_views(db, [matches.get(db, match_id)], details=True)[0]


@router.post("/matches/friendly", status_code=201, tags=["matches"])
def record_friendly(
    payload: matches.Friendly, db: Database, env: Environment, actor: Actor, key: Key
) -> dto.Ref:
    return dto.Ref(id=matches.friendly(db, env.settings, actor, key, payload))


@router.post("/matches/{match_id}/result", tags=["matches"])
def record_result(
    match_id: UUID,
    payload: matches.EntryResult,
    db: Database,
    env: Environment,
    actor: Actor,
    key: Key,
) -> dto.Ref:
    return dto.Ref(id=matches.submit(db, env.settings, actor, key, match_id, payload))


@router.post("/matches/{match_id}/disputes", status_code=204, tags=["disputes"])
def open_dispute(
    match_id: UUID, payload: matches.DecisionInput, db: Database, env: Environment, actor: Actor
) -> None:
    matches.dispute(db, env.settings, actor, matches.get(db, match_id), payload)


@router.post("/matches/{match_id}/resolution", tags=["disputes"])
def resolve_dispute(
    match_id: UUID,
    payload: matches.Resolution,
    db: Database,
    env: Environment,
    actor: Actor,
    key: Key,
) -> dto.Ref:
    return dto.Ref(id=matches.resolve(db, env.settings, actor, key, match_id, payload))


@router.patch("/admin/matches/{match_id}", tags=["matches"])
def correct_match(
    match_id: UUID,
    payload: matches.Correction,
    db: Database,
    env: Environment,
    actor: Actor,
    key: Key,
) -> dto.Ref:
    return dto.Ref(
        id=matches.correct_or_delete(db, env.settings, actor, key, match_id, payload, remove=False)
    )


@router.post("/admin/matches/{match_id}/delete", tags=["matches"])
def delete_match(
    match_id: UUID,
    payload: matches.DecisionInput,
    db: Database,
    env: Environment,
    actor: Actor,
    key: Key,
) -> dto.Ref:
    return dto.Ref(
        id=matches.correct_or_delete(db, env.settings, actor, key, match_id, payload, remove=True)
    )


@router.get("/public/tournaments", tags=["tournaments"])
def tournament_list(
    db: Database,
    status: Status | None = None,
    q: Search = "",
    offset: Offset = 0,
    limit: Limit = 30,
) -> dto.Page[dto.TournamentSummary]:
    query = select(Tournament)
    if status:
        query = query.where(Tournament.status == status)
    if q:
        query = query.where(Tournament.title.icontains(q, autoescape=True))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(
        db.scalars(
            query.order_by(Tournament.starts_at.desc(), Tournament.id).offset(offset).limit(limit)
        )
    )
    return dto.Page(items=views.tournament_summaries(db, rows), total=total)


@router.get("/public/tournaments/{tournament_id}", tags=["tournaments"])
def tournament_detail(tournament_id: UUID, db: Database) -> dto.TournamentView:
    return views.tournament_view(db, tournaments.get(db, tournament_id))


@router.post("/tournaments", status_code=201, tags=["tournaments"])
def create_tournament(payload: tournaments.Create, db: Database, actor: Actor) -> dto.Ref:
    return dto.Ref(id=tournaments.create(db, actor, payload).id)


@router.put("/tournaments/{tournament_id}", status_code=204, tags=["tournaments"])
def edit_tournament(
    tournament_id: UUID, payload: tournaments.Edit, db: Database, actor: Actor
) -> None:
    tournaments.edit(db, actor, tournaments.get(db, tournament_id), payload)


@router.delete("/tournaments/{tournament_id}", status_code=204, tags=["tournaments"])
def delete_tournament(tournament_id: UUID, db: Database, env: Environment, actor: Actor) -> None:
    tournaments.delete_tournament(db, actor, tournaments.get(db, tournament_id), env.settings.elo_k)


@router.put(
    "/tournaments/{tournament_id}/organizers/{user_id}", status_code=204, tags=["tournaments"]
)
def appoint(tournament_id: UUID, user_id: UUID, db: Database, actor: Actor) -> None:
    tournaments.set_organizer(db, actor, tournaments.get(db, tournament_id), user_id, True)


@router.delete(
    "/tournaments/{tournament_id}/organizers/{user_id}", status_code=204, tags=["tournaments"]
)
def revoke(tournament_id: UUID, user_id: UUID, db: Database, actor: Actor) -> None:
    tournaments.set_organizer(db, actor, tournaments.get(db, tournament_id), user_id, False)


@router.get("/tournaments/{tournament_id}/application", tags=["applications"])
def application(tournament_id: UUID, db: Database, actor: Actor) -> dto.ApplicationState:
    tournaments.get(db, tournament_id)
    row = db.get(Application, (tournament_id, actor.id))
    return dto.ApplicationState.model_validate({"status": row.status if row else None})


@router.post("/tournaments/{tournament_id}/application", status_code=204, tags=["applications"])
def apply(tournament_id: UUID, db: Database, actor: Actor) -> None:
    tournaments.apply(db, actor, tournaments.get(db, tournament_id), withdraw=False)


@router.delete("/tournaments/{tournament_id}/application", status_code=204, tags=["applications"])
def withdraw(tournament_id: UUID, db: Database, actor: Actor) -> None:
    tournaments.apply(db, actor, tournaments.get(db, tournament_id), withdraw=True)


@router.get("/tournaments/{tournament_id}/applications", tags=["applications"])
def applications(
    tournament_id: UUID, db: Database, actor: Actor, offset: Offset = 0, limit: Limit = 30
) -> dto.Page[dto.ApplicationView]:
    tournaments.manage(db, actor, tournaments.get(db, tournament_id))
    query = select(Application).where(Application.tournament_id == tournament_id)
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    items = list(
        db.scalars(
            query.order_by(Application.created_at, Application.user_id).offset(offset).limit(limit)
        )
    )
    users = views.users_for(db, {item.user_id for item in items})
    return dto.Page(
        items=[
            dto.ApplicationView.model_validate(
                {"player": users[item.user_id], "status": item.status}
            )
            for item in items
        ],
        total=total,
    )


@router.post(
    "/tournaments/{tournament_id}/roster/{user_id}", status_code=204, tags=["applications"]
)
def roster(
    tournament_id: UUID,
    user_id: UUID,
    payload: tournaments.RosterAction,
    db: Database,
    actor: Actor,
) -> None:
    tournaments.roster_action(db, actor, tournaments.get(db, tournament_id), user_id, payload)


@router.put("/tournaments/{tournament_id}/teams", status_code=204, tags=["tournaments"])
def teams(tournament_id: UUID, payload: tournaments.Teams, db: Database, actor: Actor) -> None:
    tournaments.set_teams(db, actor, tournaments.get(db, tournament_id), payload)


@router.post("/admin/ratings/rebuild", status_code=204, tags=["ratings"])
def rebuild_ratings(db: Database, env: Environment, actor: Actor) -> None:
    require_admin(actor.role)
    ratings.rebuild(db, env.settings.elo_k)
    record_audit(db, "rating.rebuild", actor.id, actor.id, k=env.settings.elo_k)
