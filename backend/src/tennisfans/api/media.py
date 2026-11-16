from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from tennisfans.api import contracts as dto
from tennisfans.api.context import Actor, Database, Environment
from tennisfans.core.errors import forbidden, missing
from tennisfans.db.media import Media
from tennisfans.domain.permissions import Role, require_admin
from tennisfans.modules import matches, storage, tournaments
from tennisfans.modules.facts import (
    delete_photos,
    load_user,
    record_audit,
    sides,
    tournament_id_for,
)

router = APIRouter(tags=["media"])
Uploads = Annotated[list[UploadFile], File()]


@router.post("/media/{kind}/{owner_id}", status_code=201)
def upload(
    kind: Literal["user", "match", "tournament"],
    owner_id: UUID,
    files: Uploads,
    db: Database,
    env: Environment,
    actor: Actor,
) -> dto.PhotoList:
    user_id = match_id = tournament_id = None
    if kind == "user":
        if owner_id != actor.id:
            require_admin(actor.role)
        load_user(db, owner_id)
        user_id = owner_id
    elif kind == "match":
        match = matches.get(db, owner_id)
        a, b = sides(db, match)
        tournament_id_ = tournament_id_for(db, match)
        if (
            actor.role != Role.ADMIN
            and actor.id not in a + b
            and not tournaments.is_organizer(db, actor.id, tournament_id_)
        ):
            raise forbidden()
        match_id = owner_id
    else:
        tournaments.manage(db, actor, tournaments.get(db, owner_id))
        tournament_id = owner_id
    images = [storage.decode(file.file, file.content_type, env.settings) for file in files]
    photos = storage.save(
        db,
        env.storage,
        env.settings,
        actor,
        images,
        user_id=user_id,
        match_id=match_id,
        tournament_id=tournament_id,
    )
    return dto.PhotoList(items=[dto.Photo.model_validate(photo) for photo in photos])


@router.get("/public/media/{photo_id}/{variant}", response_class=FileResponse)
def photo(
    photo_id: UUID, variant: Literal["full", "thumb"], db: Database, env: Environment
) -> FileResponse:
    item = db.get(Media, photo_id)
    if item is None:
        raise missing()
    path = env.storage.path(item.id, variant == "thumb")
    if not path.is_file():
        raise missing()
    return FileResponse(
        path,
        media_type=item.content_type,
        headers={"Cache-Control": "public, max-age=0, must-revalidate"},
    )


@router.delete("/admin/media/{photo_id}", status_code=204)
def remove(photo_id: UUID, db: Database, actor: Actor) -> None:
    require_admin(actor.role)
    item = db.get(Media, photo_id)
    if item is None:
        raise missing()
    delete_photos(db, [item])
    record_audit(db, "media.delete", photo_id, actor.id)


@router.put("/tournaments/{tournament_id}/cover", status_code=204)
def cover(tournament_id: UUID, payload: dto.Cover, db: Database, actor: Actor) -> None:
    require_admin(actor.role)
    tournaments.get(db, tournament_id)
    target = db.get(Media, payload.photo_id) if payload.photo_id else None
    if payload.photo_id and (target is None or target.tournament_id != tournament_id):
        raise missing()
    current = db.scalar(select(Media).where(Media.tournament_id == tournament_id, Media.cover))
    if current:
        current.cover = False
        db.flush()
    if target:
        target.cover = True
    record_audit(db, "tournament.cover", tournament_id, actor.id)
