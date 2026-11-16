import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tennisfans.core.config import Settings
from tennisfans.core.errors import Problem, conflict, invalid
from tennisfans.db.accounts import User
from tennisfans.db.base import now
from tennisfans.db.media import Media, MediaDeletion
from tennisfans.db.runtime import lock
from tennisfans.modules.facts import delete_photos, record_audit

logger = logging.getLogger(__name__)
FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class Storage(Protocol):
    def check(self) -> None: ...
    def write(self, id_: UUID, full: bytes, thumb: bytes) -> None: ...
    def path(self, id_: UUID, thumb: bool) -> Path: ...
    def remove(self, id_: UUID) -> None: ...


@dataclass(frozen=True)
class LocalStorage:
    root: Path

    def check(self) -> None:
        self.root.mkdir(mode=0o750, parents=True, exist_ok=True)
        marker = self.root / f".probe-{uuid4().hex}"
        with marker.open("xb") as handle:
            handle.write(b"ok")
        marker.unlink()
        if not os.access(self.root, os.R_OK | os.W_OK | os.X_OK):
            raise RuntimeError("The persistent media directory must be readable and writable")

    def path(self, id_: UUID, thumb: bool) -> Path:
        suffix = "thumb" if thumb else "full"
        return self.root / f"{id_.hex}.{suffix}"

    def write(self, id_: UUID, full: bytes, thumb: bytes) -> None:
        try:
            for variant, content in ((False, full), (True, thumb)):
                with self.path(id_, variant).open("xb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
        except OSError:
            self.remove(id_)
            raise

    def remove(self, id_: UUID) -> None:
        for variant in (False, True):
            self.path(id_, variant).unlink(missing_ok=True)


@dataclass(frozen=True)
class Decoded:
    full: bytes
    thumb: bytes
    content_type: str
    width: int
    height: int


def decode(stream: BinaryIO, declared_type: str | None, settings: Settings) -> Decoded:
    raw = stream.read(settings.upload_bytes + 1)
    if len(raw) > settings.upload_bytes:
        raise Problem(413, "file_too_large", "The file exceeds the individual upload limit")
    try:
        with Image.open(BytesIO(raw), formats=list(FORMATS)) as image:
            fmt = image.format
            if fmt is None or FORMATS.get(fmt) != declared_type:
                raise invalid(
                    "invalid_image", "Image type does not match JPEG, PNG, or WebP content"
                )
            if (
                image.width * image.height > settings.image_pixels
                or getattr(image, "n_frames", 1) != 1
            ):
                raise invalid("invalid_image", "Use a still image within the pixel limit")
            image.verify()
        with Image.open(BytesIO(raw), formats=list(FORMATS)) as original:
            upright = ImageOps.exif_transpose(original)
            clean = Image.new(
                "RGBA" if "A" in upright.getbands() or "transparency" in upright.info else "RGB",
                upright.size,
            )
            if fmt == "JPEG":
                clean = Image.new("RGB", upright.size)
            clean.paste(upright.convert(clean.mode))
            full = BytesIO()
            clean.save(full, format=fmt, quality=95, lossless=fmt == "WEBP")
            width, height = clean.size
            clean.thumbnail((480, 480))
            thumb = BytesIO()
            clean.save(thumb, format=fmt, quality=83)
            return Decoded(full.getvalue(), thumb.getvalue(), FORMATS[fmt], width, height)
    except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise invalid("invalid_image", "Upload a valid JPEG, PNG, or WebP image") from error


def save(
    db: Session,
    storage: Storage,
    settings: Settings,
    actor: User,
    images: list[Decoded],
    *,
    user_id: UUID | None = None,
    match_id: UUID | None = None,
    tournament_id: UUID | None = None,
) -> list[Media]:
    if user_id:
        if len(images) != 1:
            raise invalid("avatar_count", "Choose exactly one avatar")
        old = list(db.scalars(select(Media).where(Media.user_id == user_id)))
        delete_photos(db, old)
        db.flush()
    total = sum(len(image.full) + len(image.thumb) for image in images)
    if settings.storage_quota_bytes:
        used = db.scalar(select(func.coalesce(func.sum(Media.byte_count), 0))) or 0
        if used + total > settings.storage_quota_bytes:
            raise conflict("media_quota", "The configured media storage quota has been reached")
    rows = []
    for image in images:
        id_ = uuid4()
        storage.write(id_, image.full, image.thumb)
        db.info.setdefault("media_created", []).append(id_)
        item = Media(
            id=id_,
            user_id=user_id,
            match_id=match_id,
            tournament_id=tournament_id,
            uploader_id=actor.id,
            content_type=image.content_type,
            width=image.width,
            height=image.height,
            byte_count=len(image.full) + len(image.thumb),
        )
        db.add(item)
        record_audit(
            db, "media.upload", item.id, actor.id, owner=str(user_id or match_id or tournament_id)
        )
        rows.append(item)
    db.flush()
    return rows


def cleanup_pending(factory: sessionmaker[Session], storage: Storage) -> None:
    with factory.begin() as db:
        lock(db)
        for item in db.scalars(select(MediaDeletion).order_by(MediaDeletion.created_at).limit(200)):
            try:
                storage.remove(item.id)
            except OSError:
                logger.warning("Could not remove media object %s; it will be retried", item.id)
            else:
                db.delete(item)


def sweep_orphans(factory: sessionmaker[Session], storage: LocalStorage) -> None:
    with factory.begin() as db:
        lock(db)
        cutoff = (now() - timedelta(hours=24)).timestamp()
        for path in storage.root.iterdir():
            stem, ext = path.stem, path.suffix
            if not path.is_file() or ext not in {".full", ".thumb"} or len(stem) != 32:
                continue
            try:
                id_ = UUID(hex=stem)
                if path.stat().st_mtime < cutoff and db.get(Media, id_) is None:
                    storage.remove(id_)
            except (ValueError, OSError):
                continue
