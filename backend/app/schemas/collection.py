from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    caught_at: datetime
    created_at: datetime
    updated_at: datetime


class CollectionStats(BaseModel):
    total: int
    by_type: dict[str, int]
    favorites: int
