"""Tests del proxy de PokéAPI.

Estos tests NO golpean la red real (httpx se monkeypatch-ea) para que la
suite sea rápida, determinista y funcione en CI/sandboxes sin salida a
internet. La integración real contra pokeapi.co se puede validar
manualmente con `curl` o desde Swagger UI (/docs).
"""
import pytest

from app.schemas.pokemon import PokemonDetail, PokemonStat
from app.services import pokeapi_client as pokeapi_client_module


@pytest.fixture(autouse=True)
def _reset_client_singleton():
    pokeapi_client_module._client_singleton = None
    yield
    pokeapi_client_module._client_singleton = None


def _fake_pikachu() -> PokemonDetail:
    return PokemonDetail(
        id=25,
        name="pikachu",
        height=4,
        weight=60,
        sprite_url="https://example.com/25.png",
        artwork_url="https://example.com/artwork/25.png",
        types=["electric"],
        abilities=["static"],
        stats=[PokemonStat(name="hp", base_stat=35)],
    )


def test_get_pokemon_detail_uses_client(client, monkeypatch):
    async def fake_get_pokemon(self, id_or_name):
        assert str(id_or_name).lower() == "pikachu"
        return _fake_pikachu()

    monkeypatch.setattr(
        pokeapi_client_module.PokeAPIClient, "get_pokemon", fake_get_pokemon
    )

    response = client.get("/api/v1/pokemon/pikachu")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "pikachu"
    assert body["types"] == ["electric"]


def test_list_pokemon_uses_client(client, monkeypatch):
    from app.schemas.pokemon import PokemonListResponse, PokemonSummary

    async def fake_list_pokemon(self, *, limit, offset, search):
        return PokemonListResponse(
            count=1,
            limit=limit,
            offset=offset,
            results=[PokemonSummary(id=25, name="pikachu", sprite_url=None, types=[])],
        )

    monkeypatch.setattr(
        pokeapi_client_module.PokeAPIClient, "list_pokemon", fake_list_pokemon
    )

    response = client.get("/api/v1/pokemon?limit=10&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "pikachu"
