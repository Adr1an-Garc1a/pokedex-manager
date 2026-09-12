from pydantic import BaseModel


class PokemonSummary(BaseModel):
    """Resumen ligero usado en listados/búsqueda de la Pokédex."""

    id: int
    name: str
    sprite_url: str | None = None
    types: list[str] = []


class PokemonListResponse(BaseModel):
    count: int
    limit: int
    offset: int
    results: list[PokemonSummary]


class PokemonStat(BaseModel):
    name: str
    base_stat: int


class PokemonDetail(BaseModel):
    id: int
    name: str
    height: int
    weight: int
    sprite_url: str | None = None
    artwork_url: str | None = None
    types: list[str] = []
    abilities: list[str] = []
    stats: list[PokemonStat] = []
