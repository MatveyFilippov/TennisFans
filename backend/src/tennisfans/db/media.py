from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from tennisfans.db.base import Base, Created, Identity


class Media(Identity, Created, Base):
    __tablename__ = "media_files"
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    tournament_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"), index=True
    )
    uploader_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    content_type: Mapped[str] = mapped_column(String(16))
    byte_count: Mapped[int]
    width: Mapped[int]
    height: Mapped[int]
    cover: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (
        CheckConstraint("num_nonnulls(user_id, match_id, tournament_id) = 1", name="owner"),
        CheckConstraint("NOT cover OR tournament_id IS NOT NULL", name="cover"),
        Index(
            "uq_media_avatar", "user_id", unique=True, postgresql_where=text("user_id IS NOT NULL")
        ),
        Index("uq_media_cover", "tournament_id", unique=True, postgresql_where=text("cover")),
    )


class MediaDeletion(Created, Base):
    __tablename__ = "media_deletions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
