from fastapi import APIRouter, Query

from app.schemas.pokemon import PokemonDetail, PokemonListResponse
from app.services.pokeapi_client import get_pokeapi_client

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


@router.get("", response_model=PokemonListResponse)
async def list_pokemon(
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Nombre exacto a buscar"),
):
    """Proxy cacheado hacia PokéAPI (solo lectura). Ver docs/POKEAPI_DECISION.md."""
    client = get_pokeapi_client()
    return await client.list_pokemon(limit=limit, offset=offset, search=search)


@router.get("/{id_or_name}", response_model=PokemonDetail)
async def get_pokemon_detail(id_or_name: str):
    client = get_pokeapi_client()
    return await client.get_pokemon(id_or_name)
