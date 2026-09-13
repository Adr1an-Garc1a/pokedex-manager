"""Cliente async para PokéAPI (https://pokeapi.co) con caché en memoria.

PokéAPI es de solo lectura y externa: este cliente es el ÚNICO punto del
sistema que le habla directamente. Ver docs/POKEAPI_DECISION.md para el
razonamiento completo.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from cachetools import TTLCache
from fastapi import HTTPException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.schemas.pokemon import PokemonDetail, PokemonListResponse, PokemonStat, PokemonSummary

settings = get_settings()


class PokeAPIClient:
    def __init__(self) -> None:
        self._base_url = settings.pokeapi_base_url
        self._cache: TTLCache = TTLCache(maxsize=2048, ttl=settings.pokeapi_cache_ttl_seconds)
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _cache_get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = value

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(httpx.TransportError),
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        response = await self._client.get(path, params=params)
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Pokémon no encontrado en PokéAPI")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_id_from_url(url: str) -> int:
        # Las URLs de PokéAPI terminan en /pokemon/{id}/
        parts = [p for p in url.split("/") if p]
        return int(parts[-1])

    async def list_pokemon(self, *, limit: int, offset: int, search: str | None) -> PokemonListResponse:
        if search:
            # PokéAPI no soporta búsqueda por texto nativa en /pokemon; se resuelve
            # buscando el recurso exacto por nombre (case-insensitive).
            try:
                detail = await self.get_pokemon(search.lower().strip())
                return PokemonListResponse(
                    count=1,
                    limit=limit,
                    offset=offset,
                    results=[
                        PokemonSummary(
                            id=detail.id,
                            name=detail.name,
                            sprite_url=detail.sprite_url,
                            types=detail.types,
                        )
                    ],
                )
            except HTTPException:
                return PokemonListResponse(count=0, limit=limit, offset=offset, results=[])

        cache_key = f"list:{limit}:{offset}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = await self._get("/pokemon", params={"limit": limit, "offset": offset})

        results: list[PokemonSummary] = []
        for item in data["results"]:
            pid = self._extract_id_from_url(item["url"])
            results.append(
                PokemonSummary(
                    id=pid,
                    name=item["name"],
                    sprite_url=self._sprite_url(pid),
                    types=[],
                )
            )

        response_obj = PokemonListResponse(
            count=data["count"], limit=limit, offset=offset, results=results
        )
        self._cache_set(cache_key, response_obj)
        return response_obj

    @staticmethod
    def _sprite_url(pokemon_id: int) -> str:
        return (
            "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/"
            f"pokemon/{pokemon_id}.png"
        )

    @staticmethod
    def _artwork_url(pokemon_id: int) -> str:
        return (
            "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/"
            f"pokemon/other/official-artwork/{pokemon_id}.png"
        )

    async def get_pokemon(self, id_or_name: str | int) -> PokemonDetail:
        cache_key = f"detail:{str(id_or_name).lower()}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        data = await self._get(f"/pokemon/{str(id_or_name).lower()}")

        detail = PokemonDetail(
            id=data["id"],
            name=data["name"],
            height=data["height"],
            weight=data["weight"],
            sprite_url=self._sprite_url(data["id"]),
            artwork_url=self._artwork_url(data["id"]),
            types=[t["type"]["name"] for t in data["types"]],
            abilities=[a["ability"]["name"] for a in data["abilities"]],
            stats=[
                PokemonStat(name=s["stat"]["name"], base_stat=s["base_stat"])
                for s in data["stats"]
            ],
        )
        self._cache_set(cache_key, detail)
        return detail

    async def get_type_matchups(self, types: list[str]) -> tuple[list[str], list[str]]:
        """Devuelve (fuerte_contra, débil_contra) para una lista de tipos.

        Se usa desde las funcionalidades de IA (Vision e Insights): en vez de
        confiar en que el modelo "recuerde" bien las tablas de tipos de
        Pokémon (puede alucinar), se le pide solo que identifique el/los
        tipo(s), y las ventajas/desventajas reales se calculan aquí con el
        dato autoritativo de PokéAPI (`/type/{nombre}` → damage_relations).

        Simplificación deliberada para un Pokémon de dos tipos: se combinan
        (unión, sin duplicados) los "fuerte contra" / "débil contra" de cada
        tipo por separado — no se calculan multiplicadores compuestos (x4,
        x0.25, inmunidades que se cancelan entre sí). Es una aproximación
        "suficientemente buena" para una feature de fun facts, no para
        simular daño de batalla exacto.
        """
        strong_against: set[str] = set()
        weak_against: set[str] = set()

        for type_name in types:
            cache_key = f"type:{type_name.lower()}"
            cached = self._cache_get(cache_key)
            if cached is None:
                try:
                    data = await self._get(f"/type/{type_name.lower()}")
                except HTTPException:
                    continue
                cached = data
                self._cache_set(cache_key, cached)

            relations = cached.get("damage_relations", {})
            strong_against.update(t["name"] for t in relations.get("double_damage_to", []))
            weak_against.update(t["name"] for t in relations.get("double_damage_from", []))

        # Un tipo no cuenta como "débil contra sí mismo" ni "fuerte contra sí
        # mismo" para un Pokémon de tipo dual raro (ej. mismo tipo repetido).
        strong_against -= set(t.lower() for t in types)
        weak_against -= set()  # (se deja explícito por si se agrega lógica futura)

        return sorted(strong_against), sorted(weak_against)


_client_singleton: PokeAPIClient | None = None


def get_pokeapi_client() -> PokeAPIClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = PokeAPIClient()
    return _client_singleton
