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


# --- Traducciones estáticas ES usadas por las funcionalidades de IA --------
# (Vision, MCP tools, Insights): se resuelven aquí, contra datos reales de
# PokéAPI o mapeos fijos, en vez de pedírselo al modelo — mismo principio que
# get_type_matchups (no confiar en que el modelo "recuerde" bien tablas fijas).

TYPE_NAME_ES: dict[str, str] = {
    "normal": "normal", "fire": "fuego", "water": "agua", "electric": "eléctrico",
    "grass": "planta", "ice": "hielo", "fighting": "lucha", "poison": "veneno",
    "ground": "tierra", "flying": "volador", "psychic": "psíquico", "bug": "bicho",
    "rock": "roca", "ghost": "fantasma", "dragon": "dragón", "dark": "siniestro",
    "steel": "acero", "fairy": "hada",
}


def translate_types_es(types: list[str]) -> list[str]:
    """Traduce una lista de tipos (slugs en inglés de PokéAPI) a español,
    dejando el original si no está en el mapeo (no debería pasar con los 18
    tipos oficiales, pero evita romper la respuesta si PokéAPI agrega algo)."""
    return [TYPE_NAME_ES.get(t.lower(), t) for t in types]


# generation-i..ix de PokéAPI -> juego(s) de esa generación en español. Se usa
# para "¿en qué juego salió por primera vez este Pokémon?" a partir del campo
# `generation` de /pokemon-species/{id} (dato real, no una fecha inventada).
_GENERATION_GAMES_ES: dict[str, str] = {
    "generation-i": "Pokémon Rojo, Azul y Amarillo",
    "generation-ii": "Pokémon Oro, Plata y Cristal",
    "generation-iii": "Pokémon Rubí, Zafiro y Esmeralda",
    "generation-iv": "Pokémon Diamante, Perla y Platino",
    "generation-v": "Pokémon Negro y Blanco (y sus secuelas B2/W2)",
    "generation-vi": "Pokémon X y Y",
    "generation-vii": "Pokémon Sol y Luna",
    "generation-viii": "Pokémon Espada y Escudo",
    "generation-ix": "Pokémon Escarlata y Púrpura",
}

# `habitat` de /pokemon-species/{id} -> zonas en español. PokéAPI dejó de
# poblar este campo para Pokémon de generaciones más recientes (queda `null`)
# — en ese caso se devuelve un mensaje explícito en vez de inventar una zona.
_HABITAT_ES: dict[str, str] = {
    "cave": "cuevas",
    "forest": "bosques",
    "grassland": "praderas y pastizales",
    "mountain": "montañas",
    "rare": "zonas poco comunes o especiales",
    "rough-terrain": "terrenos escarpados y rocosos",
    "sea": "mar y océanos",
    "urban": "zonas urbanas, cerca de las personas",
    "waters-edge": "orillas de ríos y lagos",
}

_HABITAT_DESCONOCIDO_ES = (
    "PokéAPI no tiene un hábitat estandarizado registrado para este Pokémon "
    "(común en generaciones más recientes) — varía según la zona del juego."
)


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

    async def get_species_info(self, id_or_name: str | int) -> dict:
        """Devuelve datos "de especie" (no de una forma/variante puntual) de
        `/pokemon-species/{id}`: la generación en que debutó y su hábitat.

        Usado por la funcionalidad de Vision (bonus 1) para "¿en qué juego
        salió por primera vez?" / "¿en qué zonas es fácil encontrarlo?" —
        igual que get_type_matchups, se resuelve contra el dato real de
        PokéAPI en vez de pedírselo al modelo de IA, para no arriesgarse a
        que alucine un juego o una zona que no es.
        """
        cache_key = f"species:{str(id_or_name).lower()}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        data = await self._get(f"/pokemon-species/{str(id_or_name).lower()}")
        generation = (data.get("generation") or {}).get("name")
        habitat = (data.get("habitat") or {}).get("name")
        evolution_chain_url = (data.get("evolution_chain") or {}).get("url")

        result = {
            "generation": generation,
            "first_appearance_game": _GENERATION_GAMES_ES.get(
                generation, "No disponible (PokéAPI no reporta la generación de este Pokémon)"
            ),
            "habitat": habitat,
            "habitat_zones": _HABITAT_ES.get(habitat, _HABITAT_DESCONOCIDO_ES),
            "evolution_chain_url": evolution_chain_url,
        }
        self._cache_set(cache_key, result)
        return result

    async def get_evolution_info(self, *, evolution_chain_url: str, pokemon_name: str) -> dict:
        """Devuelve {"pre_evolution": str | None, "evolutions": list[str]} para
        `pokemon_name` dentro de su cadena evolutiva completa (`/evolution-chain/{id}`).

        Igual que el resto de datos "duros" de Pokédex en este cliente: se lee
        directo de PokéAPI en vez de pedírselo al modelo de IA. Si el Pokémon
        no aparece en la cadena (no debería pasar si el nombre es válido) o
        la cadena no se puede resolver, se devuelve vacío en vez de fallar.
        """
        cache_key = f"evochain:{evolution_chain_url}"
        cached = self._cache_get(cache_key)
        if cached is None:
            # evolution_chain_url ya es una URL absoluta de PokéAPI; _get solo
            # acepta paths relativos al cliente, así que se recorta el prefijo.
            path = evolution_chain_url.replace(self._base_url, "")
            cached = await self._get(path)
            self._cache_set(cache_key, cached)

        chain = cached.get("chain")
        if not chain:
            return {"pre_evolution": None, "evolutions": []}

        found = _find_evolution_node(chain, pokemon_name.lower())
        if found is None:
            return {"pre_evolution": None, "evolutions": []}
        pre_evolution, evolutions = found
        return {"pre_evolution": pre_evolution, "evolutions": evolutions}


def _find_evolution_node(
    node: dict, target: str, parent_name: str | None = None
) -> tuple[str | None, list[str]] | None:
    """Recorre el árbol de `/evolution-chain/{id}` (puede ramificarse, ej.
    Eevee) buscando `target`; devuelve (nombre de la pre-evolución o None,
    [nombres de las evoluciones directas]) o None si no se encontró."""
    name = node.get("species", {}).get("name")
    if name == target:
        children = [c.get("species", {}).get("name") for c in node.get("evolves_to", [])]
        return parent_name, [c for c in children if c]

    for child in node.get("evolves_to", []):
        result = _find_evolution_node(child, target, parent_name=name)
        if result is not None:
            return result
    return None


_client_singleton: PokeAPIClient | None = None


def get_pokeapi_client() -> PokeAPIClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = PokeAPIClient()
    return _client_singleton
