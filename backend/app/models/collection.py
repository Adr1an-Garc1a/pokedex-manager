from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CollectionEntry(Base):
    """Una entrada en la colección personal de un usuario.

    Los campos pokemon_name / sprite_url / types se guardan desnormalizados
    (copiados de PokéAPI en el momento de crear la entrada) a propósito: la
    colección del usuario debe seguir siendo legible aunque PokéAPI cambie o
    no esté disponible. Ver docs/POKEAPI_DECISION.md.
    """

    __tablename__ = "collection_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    pokemon_id: Mapped[int] = mapped_column(Integer, index=True)
    pokemon_name: Mapped[str] = mapped_column(String(255))
    sprite_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    types: Mapped[list] = mapped_column(JSON, default=list)

    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    caught_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="collection")

    def __repr__(self) -> str:
        return f"<CollectionEntry id={self.id} pokemon={self.pokemon_name!r} user_id={self.user_id}>"
