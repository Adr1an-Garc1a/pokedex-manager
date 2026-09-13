from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectionEntryCreate(BaseModel):
    pokemon_id: int = Field(..., description="ID del Pokémon en PokéAPI")
    nickname: str | None = None
    level: int | None = Field(default=None, ge=1, le=100)
    notes: str | None = None
    is_favorite: bool = False


class CollectionEntryUpdate(BaseModel):
    nickname: str | None = None
    level: int | None = Field(default=None, ge=1, le=100)
    notes: str | None = None
    is_favorite: bool | None = None


class CollectionEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pokemon_id: int
    pokemon_name: str
    sprite_url: str | None
    types: list[str]
    nickname: str | None
    level: int | None
    is_favorite: bool
    notes: str | None
    custom_image_url: str | None
    is_team_member: bool
    caught_at: datetime
    created_at: datetime
    updated_at: datetime


class CollectionStats(BaseModel):
    total: int
    by_type: dict[str, int]
    favorites: int


class TeamUpdate(BaseModel):
    """Body de PUT /collection/team: los ids (de la colección del usuario que
    llama) que a partir de ahora forman su equipo — hasta 6, pueden ser menos.
    Un arreglo vacío quita a todos del equipo (vuelve al comportamiento por
    defecto de "primeros 6 agregados" en Insights)."""

    entry_ids: list[int] = Field(default_factory=list)

    @field_validator("entry_ids")
    @classmethod
    def _max_six(cls, value: list[int]) -> list[int]:
        if len(value) > 6:
            raise ValueError("Un equipo no puede tener más de 6 Pokémon.")
        if len(set(value)) != len(value):
            raise ValueError("No repitas el mismo Pokémon dos veces en el equipo.")
        return value
