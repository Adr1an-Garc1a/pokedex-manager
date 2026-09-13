"""Bonus 2 — Servidor MCP (Model Context Protocol) con las herramientas que
Claude puede usar para responder preguntas sobre la colección del usuario.

Se construye un servidor nuevo, ligero, por cada conversación (build_mcp_server),
con las tools "cerradas" sobre el usuario y la sesión de DB de ESE request —
así el propio servidor MCP ya sabe de quién es la colección que puede leer,
sin que el modelo tenga que (ni pueda) pasar un user_id como parámetro. Es la
misma idea de aislamiento que ya usa el resto de la API (JWT → current_user),
aplicada al servidor de herramientas en vez de a un endpoint REST.

El servidor se conecta al cliente MCP (chat.py) con streams en memoria — sin
proceso aparte, sin red — usando `mcp.shared.memory`, el mismo mecanismo que
usa el propio SDK de `mcp` para sus tests: es una sesión cliente-servidor MCP
real (mismos mensajes JSON-RPC, mismo protocolo), simplemente sin la capa de
transporte de red que tendría un MCP server standalone (stdio o HTTP).
"""
from __future__ import annotations

import asyncio
from collections import Counter

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from app.models.collection import CollectionEntry
from app.models.user import User
from app.services.pokeapi_client import get_pokeapi_client
from app.services.team import get_effective_team


def build_mcp_server(*, db: Session, user: User) -> FastMCP:
    server = FastMCP("pokedex-manager-collection")

    def _load_entries() -> list[CollectionEntry]:
        return (
            db.query(CollectionEntry)
            .filter(CollectionEntry.user_id == user.id)
            .order_by(CollectionEntry.created_at.desc())
            .all()
        )

    @server.tool(
        description=(
            "Lista TODOS los Pokémon en la colección personal del usuario actual, "
            "con su apodo, nivel, tipos, si es favorito, si es parte de su equipo "
            "actual (is_team_member) y sus notas. Para preguntas específicamente "
            "sobre 'mi equipo' usa mejor la tool get_my_team, que ya filtra "
            "exactamente cuáles son."
        )
    )
    async def list_my_collection() -> list[dict]:
        # db (SQLAlchemy síncrono) se ejecuta en un thread aparte para no
        # bloquear el event loop del backend mientras responde este tool.
        entries = await asyncio.to_thread(_load_entries)
        return [
            {
                "id": e.id,
                "pokemon_name": e.pokemon_name,
                "nickname": e.nickname,
                "types": e.types,
                "level": e.level,
                "is_favorite": e.is_favorite,
                "is_team_member": e.is_team_member,
                "notes": e.notes,
            }
            for e in entries
        ]

    @server.tool(
        description=(
            "Devuelve el EQUIPO actual del usuario (hasta 6 Pokémon) — la misma "
            "información que ya usa la sección de Insights de la app. Si el usuario "
            "eligió un equipo a mano en 'Mi Colección' (botón 'Hacer de mi equipo'), "
            "son esos; si no ha elegido ninguno todavía, son los primeros 6 Pokémon "
            "que agregó a su colección. Usa SIEMPRE esta tool (no list_my_collection) "
            "cuando el usuario pregunte por 'mi equipo', 'mi equipo actual', si puede "
            "'pasar el juego con este equipo', o cualquier variante — nunca asumas ni "
            "adivines cuál es el equipo a partir de los favoritos u otra señal."
        )
    )
    async def get_my_team() -> dict:
        def _load_team() -> list[CollectionEntry]:
            return get_effective_team(db, user.id)

        team = await asyncio.to_thread(_load_team)
        chosen_by_hand = any(e.is_team_member for e in team)
        return {
            "team_was_chosen_by_user": chosen_by_hand,
            "note": (
                "Este equipo lo eligió el usuario a mano."
                if chosen_by_hand
                else "El usuario no ha elegido un equipo a mano todavía — estos son "
                "los primeros Pokémon que agregó a su colección, usados por defecto."
            ),
            "team": [
                {
                    "id": e.id,
                    "pokemon_name": e.pokemon_name,
                    "nickname": e.nickname,
                    "types": e.types,
                    "level": e.level,
                    "is_favorite": e.is_favorite,
                }
                for e in team
            ],
        }

    @server.tool(
        description=(
            "Devuelve estadísticas agregadas de la colección del usuario actual: "
            "total de Pokémon, cuántos son favoritos, y distribución por tipo."
        )
    )
    async def get_collection_stats() -> dict:
        entries = await asyncio.to_thread(_load_entries)
        type_counter: Counter = Counter()
        for e in entries:
            type_counter.update(e.types or [])
        return {
            "total": len(entries),
            "favorites": sum(1 for e in entries if e.is_favorite),
            "by_type": dict(type_counter),
        }

    @server.tool(
        description=(
            "Busca información oficial de un Pokémon por nombre o ID en la Pokédex "
            "(tipos, habilidades, estadísticas base) — para CUALQUIER Pokémon, no solo "
            "los de la colección del usuario. Útil para responder '¿qué tipo es X?' o "
            "comparar un Pokémon de la colección contra otro que el usuario no tiene."
        )
    )
    async def get_pokemon_info(name_or_id: str) -> dict:
        client = get_pokeapi_client()
        try:
            detail = await client.get_pokemon(name_or_id)
        except Exception:
            return {"error": f"No se encontró ningún Pokémon con el nombre/ID '{name_or_id}'."}

        strong_against, weak_against = await client.get_type_matchups(detail.types)
        return {
            "id": detail.id,
            "name": detail.name,
            "types": detail.types,
            "abilities": detail.abilities,
            "stats": {s.name: s.base_stat for s in detail.stats},
            "strong_against": strong_against,
            "weak_against": weak_against,
        }

    return server
