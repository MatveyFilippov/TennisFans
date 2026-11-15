import hashlib
import hmac
import json
from dataclasses import asdict
from datetime import UTC
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import delete
from sqlalchemy.orm import Session

from tennisfans.core.config import Settings
from tennisfans.core.errors import conflict, invalid, missing
from tennisfans.db.accounts import Idempotency, Notification, User
from tennisfans.db.base import now
from tennisfans.db.results import Dispute, Match, MatchSet, Revision
from tennisfans.domain.permissions import (
    Role,
    require_admin,
    require_opponent,
    require_participant,
    require_resolver,
)
from tennisfans.domain.scoring import Discipline, Input, Rules, Score, validate_score
from tennisfans.modules import brackets, tournaments
from tennisfans.modules.facts import (
    create_match,
    load_user,
    open_dispute,
    purge_match,
    record_audit,
    result,
    sets_many,
    sides,
    tournament_id_for,
)
from tennisfans.modules.ratings import rebuild


class ResultInput(Input):
    played_at: AwareDatetime
    score: Score


class Friendly(ResultInput):
    discipline: Discipline
    rules: Rules
    a: list[UUID] = Field(min_length=1, max_length=2)
    b: list[UUID] = Field(min_length=1, max_length=2)


class EntryResult(ResultInput):
    version: int = Field(ge=1)


class DecisionInput(Input):
    reason: str = Field(min_length=3, max_length=1200)
    version: int = Field(ge=1)
    confirmation: str | None = Field(None, max_length=64)


class Correction(EntryResult, DecisionInput):
    pass


class Resolution(DecisionInput):
    decision: Literal["UPHOLD", "REPLACE", "ANNUL"]
    replacement: ResultInput | None = None

    @model_validator(mode="after")
    def require_replacement(self) -> "Resolution":
        if (self.decision == "REPLACE") != (self.replacement is not None):
            raise ValueError("A replacement is required only for the REPLACE decision")
        return self


def get(db: Session, id_: UUID) -> Match:
    match = db.get(Match, id_)
    if match is None:
        raise missing()
    return match


def _version(match: Match, version: int) -> None:
    if match.version != version:
        raise conflict("stale_version", "The match changed. Reload and try again")


def _retry(
    db: Session, user: User, key: UUID, operation: str, payload: Input
) -> tuple[UUID | None, str]:
    text = payload.model_dump_json(exclude={"confirmation"})
    fingerprint = hashlib.sha256(f"{operation}:{text}".encode()).hexdigest()
    previous = db.get(Idempotency, (user.id, key))
    if previous:
        if previous.fingerprint != fingerprint:
            raise conflict(
                "idempotency_conflict", "This key was already used for a different request"
            )
        return previous.resource_id, fingerprint
    return None, fingerprint


def _remember(
    db: Session, actor: User, key: UUID, fingerprint: str, match: Match, *, deleted: bool = False
) -> None:
    db.add(
        Idempotency(
            user_id=actor.id,
            key=key,
            fingerprint=fingerprint,
            match_id=None if deleted else match.id,
            resource_id=match.id,
        )
    )


def _replace(db: Session, match: Match, actor: User, payload: ResultInput, reason: str) -> None:
    validate_score(
        Rules.model_validate(match.rules), payload.score, tournament=match.fixture_id is not None
    )
    played_at = payload.played_at.astimezone(UTC)
    if played_at > now():
        raise invalid("future_result", "A result cannot be played in the future")
    prior_score = result(match, sets_many(db, [match.id]).get(match.id, []))
    before = (
        {"score": prior_score.model_dump(mode="json"), "played_at": match.played_at.isoformat()}
        if prior_score is not None and match.played_at is not None
        else None
    )
    db.execute(delete(MatchSet).where(MatchSet.match_id == match.id))
    match.played_at = played_at
    match.author_id = match.author_id or actor.id
    match.outcome = payload.score.outcome
    match.winner = payload.score.winner
    match.version += 1
    db.add_all(
        MatchSet(match_id=match.id, position=i, **item.model_dump())
        for i, item in enumerate(payload.score.sets, 1)
    )
    db.add(
        Revision(
            match_id=match.id,
            actor_id=actor.id,
            reason=reason,
            before=before,
            after=payload.model_dump(mode="json", include={"played_at", "score"}),
        )
    )


def _reconcile(db: Session, tournament_id: UUID | None) -> list[brackets.Impact]:
    if tournament_id:
        return brackets.reconcile(db, tournaments.get(db, tournament_id))
    return []


def _confirm(
    settings: Settings,
    actor: User,
    match_id: UUID,
    fingerprint: str,
    impacts: list[brackets.Impact],
    confirmation: str | None,
    *,
    required: bool,
) -> None:
    if not required and not impacts:
        return
    if actor.role != Role.ADMIN and any(item.has_result for item in impacts):
        raise conflict(
            "admin_cascade_required",
            "An administrator must resolve this dispute because recorded downstream results would be removed",
        )
    ordered = [asdict(item) for item in sorted(impacts, key=lambda item: item.match_id)]
    summary = json.dumps(ordered, default=str, sort_keys=True)
    token = hmac.digest(
        settings.session_secret.get_secret_value().encode(),
        f"{actor.id}:{match_id}:{fingerprint}:{summary}".encode(),
        "sha256",
    ).hex()
    if confirmation is None or not hmac.compare_digest(confirmation, token):
        raise conflict(
            "cascade_confirmation",
            "Review the affected fixtures and confirm this change",
            confirmation=token,
            affected=ordered,
        )


def friendly(db: Session, settings: Settings, actor: User, key: UUID, payload: Friendly) -> UUID:
    retry, fp = _retry(db, actor, key, "friendly", payload)
    if retry:
        return get(db, retry).id
    count = 1 if payload.discipline == Discipline.SINGLES else 2
    all_players = tuple(payload.a + payload.b)
    if len(payload.a) != count or len(payload.b) != count or len(set(all_players)) != 2 * count:
        raise invalid(
            "invalid_participants", "Each side must have the correct number of distinct players"
        )
    require_participant(actor.id, all_players)
    for player in all_players:
        load_user(db, player)
    match = create_match(db, payload.discipline, payload.rules, tuple(payload.a), tuple(payload.b))
    _replace(db, match, actor, payload, "Initial friendly result")
    record_audit(db, "match.create", match.id, actor.id)
    _remember(db, actor, key, fp, match)
    rebuild(db, settings.elo_k)
    return match.id


def submit(
    db: Session, settings: Settings, actor: User, key: UUID, match_id: UUID, payload: EntryResult
) -> UUID:
    retry, fp = _retry(db, actor, key, f"submit:{match_id}", payload)
    if retry:
        return get(db, retry).id
    match = get(db, match_id)
    a, b = sides(db, match)
    require_participant(actor.id, a + b)
    _version(match, payload.version)
    tournament_id = tournament_id_for(db, match)
    if not tournament_id or match.outcome or match.blocked:
        raise conflict("fixture_unavailable", "The fixture is unavailable or has a recorded result")
    if payload.played_at < tournaments.get(db, tournament_id).starts_at:
        raise invalid(
            "premature_result", "The match cannot have been played before tournament start"
        )
    _replace(db, match, actor, payload, "Initial tournament result")
    record_audit(db, "match.submit", match.id, actor.id)
    _remember(db, actor, key, fp, match)
    _reconcile(db, tournament_id)
    rebuild(db, settings.elo_k)
    return match.id


def dispute(
    db: Session, settings: Settings, actor: User, match: Match, payload: DecisionInput
) -> None:
    a, b = sides(db, match)
    require_opponent(actor.id, match.author_id, a, b)
    _version(match, payload.version)
    if not match.outcome or match.blocked or open_dispute(db, match.id):
        raise conflict(
            "dispute_unavailable", "A dispute is already open or this result is unavailable"
        )
    db.add(Dispute(match_id=match.id, author_id=actor.id, reason=payload.reason))
    match.version += 1
    record_audit(db, "match.dispute", match.id, actor.id, reason=payload.reason)
    _reconcile(db, tournament_id_for(db, match))
    rebuild(db, settings.elo_k)


def resolve(
    db: Session, settings: Settings, actor: User, key: UUID, match_id: UUID, payload: Resolution
) -> UUID:
    retry, fp = _retry(db, actor, key, f"resolve:{match_id}", payload)
    if retry:
        return retry
    match = get(db, match_id)
    a, b = sides(db, match)
    tournament_id = tournament_id_for(db, match)
    require_resolver(
        actor.role, tournaments.is_organizer(db, actor.id, tournament_id), actor.id in a + b
    )
    _version(match, payload.version)
    active = open_dispute(db, match.id)
    if active is None or match.blocked:
        raise conflict("dispute_unavailable", "This result has no actionable dispute")
    if payload.decision == "ANNUL":
        require_admin(actor.role)
        purge_match(db, match)
    else:
        if payload.replacement is not None:
            if (
                tournament_id
                and payload.replacement.played_at < tournaments.get(db, tournament_id).starts_at
            ):
                raise invalid(
                    "premature_result", "The match cannot have been played before tournament start"
                )
            _replace(db, match, actor, payload.replacement, payload.reason)
        else:
            match.version += 1
        active.resolved_at = now()
        active.resolver_id = actor.id
        active.decision = payload.decision
        active.resolution_reason = payload.reason

    impacts = _reconcile(db, tournament_id)
    _confirm(
        settings,
        actor,
        match_id,
        fp,
        impacts,
        payload.confirmation,
        required=payload.decision == "ANNUL",
    )
    record_audit(
        db, "match.resolve", match_id, actor.id, decision=payload.decision, reason=payload.reason
    )
    for item in impacts:
        record_audit(db, "match.invalidate", item.match_id, actor.id, cause=str(match_id))
    db.add_all(
        Notification(
            user_id=player,
            match_id=None if payload.decision == "ANNUL" else match_id,
            decision=payload.decision,
        )
        for player in a + b
    )
    _remember(db, actor, key, fp, match, deleted=payload.decision == "ANNUL")
    rebuild(db, settings.elo_k)
    return match_id


def correct_or_delete(
    db: Session,
    settings: Settings,
    actor: User,
    key: UUID,
    match_id: UUID,
    payload: Correction | DecisionInput,
    *,
    remove: bool,
) -> UUID:
    require_admin(actor.role)
    retry, fp = _retry(db, actor, key, f"{'delete' if remove else 'correct'}:{match_id}", payload)
    if retry:
        return retry
    match = get(db, match_id)
    _version(match, payload.version)
    tournament_id = tournament_id_for(db, match)
    if remove:
        if open_dispute(db, match.id):
            raise conflict("active_dispute", "Use the annul decision to delete a disputed match")
        purge_match(db, match)
    elif isinstance(payload, Correction):
        if not match.outcome or match.blocked or open_dispute(db, match.id):
            raise conflict(
                "correction_unavailable",
                "Use result submission or resolve the active dispute first",
            )
        if tournament_id and payload.played_at < tournaments.get(db, tournament_id).starts_at:
            raise invalid(
                "premature_result", "The match cannot have been played before tournament start"
            )
        _replace(db, match, actor, payload, payload.reason)

    impacts = _reconcile(db, tournament_id)
    _confirm(settings, actor, match_id, fp, impacts, payload.confirmation, required=remove)
    record_audit(
        db,
        "match.delete" if remove else "match.correct",
        match_id,
        actor.id,
        **({} if remove else {"reason": payload.reason}),
    )
    for item in impacts:
        record_audit(db, "match.invalidate", item.match_id, actor.id, cause=str(match_id))
    _remember(db, actor, key, fp, match, deleted=remove)
    rebuild(db, settings.elo_k)
    return match_id
