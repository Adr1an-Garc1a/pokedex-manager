"""Bonus 3 — Análisis inteligente de la colección (Gemini 2.5 Flash, Vertex AI).

El análisis se basa SIEMPRE en los primeros 6 Pokémon que el usuario agregó a
su colección (el llamador — app/api/v1/ai.py — ya se encarga de ordenar por
fecha de creación y recortar a 6 antes de llegar aquí, aunque el usuario
tenga más). Se le pide al modelo: un puntaje de 1 a 10 de qué tan bueno es
ese equipo (con motivo), fortalezas y debilidades específicas de esos 6
Pokémon (no genéricas), un equipo ideal de hasta 6 (mezclando los que ya
tiene con sugerencias nuevas, marcadas con already_in_collection=False para
que el frontend las resalte), alternativas por cada puesto del equipo ideal,
y datos curiosos.

Los nombres de Pokémon que menciona el modelo (equipo ideal, alternativas,
datos curiosos) se resuelven contra PokéAPI para conseguir su sprite real —
mismo principio que vision.py: nunca se le pide una URL de imagen al modelo,
solo un nombre, y la imagen se resuelve contra la fuente de verdad.
"""
from __future__ import annotations

import asyncio

from app.models.collection import CollectionEntry
from app.schemas.ai import CollectionInsights
from app.services.ai.gemini_client import generate_structured_json
from app.services.pokeapi_client import get_pokeapi_client

_SYSTEM_INSTRUCTION = (
    "Eres un entrenador experto de Pokémon analizando el equipo de un usuario para "
    "darle consejos prácticos, específicos y entretenidos. Te doy exactamente los "
    "PRIMEROS 6 Pokémon (o menos) que el usuario agregó a su colección, en el orden "
    "en que los agregó — TODO tu análisis (puntaje, fortalezas, debilidades) debe "
    "hablar específicamente de ESTOS Pokémon, mencionándolos por nombre, nunca en "
    "términos genéricos. El 'equipo ideal' debe tener como máximo 6 Pokémon: prioriza "
    "los que ya tiene el usuario en su equipo actual (marca already_in_collection=true) "
    "y completa los espacios restantes con sugerencias nuevas que complementen bien al "
    "equipo (cobertura de tipos, balance ofensivo/defensivo) — para cada miembro del "
    "equipo ideal, incluida su razón, y siempre da también 2 alternativas (otro Pokémon "
    "que podría cumplir un rol similar en ese mismo puesto, con su propia razón). "
    "Responde siempre en español y en el formato JSON solicitado."
)

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "team_score": {
            "type": "INTEGER",
            "description": "Qué tan bueno es este equipo de hasta 6 Pokémon, de 1 (muy débil) a 10 (excelente)",
        },
        "team_score_reason": {
            "type": "STRING",
            "description": "Por qué obtuvo ese puntaje, mencionando específicamente a los Pokémon del equipo",
        },
        "ideal_team": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "pokemon_name": {"type": "STRING"},
                    "reason": {
                        "type": "STRING",
                        "description": "Por qué este Pokémon está en el equipo ideal; si el usuario no lo tiene, explica claramente qué le aportaría al equipo",
                    },
                    "already_in_collection": {"type": "BOOLEAN"},
                    "alternatives": {
                        "type": "ARRAY",
                        "description": "2 alternativas para este mismo puesto del equipo, por si el usuario prefiere cambiarlo",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "pokemon_name": {"type": "STRING"},
                                "reason": {"type": "STRING"},
                            },
                            "required": ["pokemon_name", "reason"],
                        },
                    },
                },
                "required": ["pokemon_name", "reason", "already_in_collection", "alternatives"],
            },
        },
        "strengths": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Fortalezas específicas de ESTE equipo de 6, mencionando qué Pokémon las aportan",
        },
        "weaknesses": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Debilidades o huecos de cobertura específicos de ESTE equipo de 6, mencionando cuáles Pokémon las causan",
        },
        "fun_facts": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "pokemon_name": {"type": "STRING"},
                    "fact": {"type": "STRING"},
                },
                "required": ["pokemon_name", "fact"],
            },
        },
    },
    "required": [
        "team_score",
        "team_score_reason",
        "ideal_team",
        "strengths",
        "weaknesses",
        "fun_facts",
    ],
}


def _summarize_collection(entries: list[CollectionEntry]) -> str:
    lines = []
    for e in entries:
        types = ", ".join(e.types or [])
        favorite = " (favorito)" if e.is_favorite else ""
        nickname = f" — apodo: {e.nickname}" if e.nickname else ""
        level = f", nivel {e.level}" if e.level else ""
        lines.append(f"- {e.pokemon_name} [{types}]{level}{favorite}{nickname}")
    return "\n".join(lines)


async def _resolve_sprite(name: str) -> str | None:
    """Best effort — si el nombre que dio el modelo no existe tal cual en
    PokéAPI, simplemente no hay imagen (el frontend ya maneja sprite_url=None
    con un placeholder), no debe tumbar el análisis completo."""
    try:
        client = get_pokeapi_client()
        detail = await client.get_pokemon(name)
        return detail.sprite_url
    except Exception:
        return None


async def generate_collection_insights(entries: list[CollectionEntry]) -> CollectionInsights:
    from google.genai import types  # import perezoso, ver gemini_client.py

    summary = _summarize_collection(entries)
    prompt = (
        f"Este es el equipo actual de {len(entries)} Pokémon del usuario "
        f"(elegido por él, o por defecto los primeros que agregó a su "
        f"colección):\n\n{summary}\n\n"
        "Genera el análisis según el esquema JSON solicitado, basado específicamente "
        "en este equipo."
    )

    parts = [types.Part.from_text(text=prompt)]
    data = await generate_structured_json(
        parts=parts, response_schema=_RESPONSE_SCHEMA, system_instruction=_SYSTEM_INSTRUCTION
    )

    # Resolver sprites en paralelo para todos los nombres que menciona el
    # modelo (equipo ideal + sus alternativas + datos curiosos) contra
    # PokéAPI — nunca se le pide al modelo una URL de imagen directamente.
    names_to_resolve: set[str] = set()
    for member in data.get("ideal_team", []):
        if member.get("pokemon_name"):
            names_to_resolve.add(member["pokemon_name"])
        for alt in member.get("alternatives", []) or []:
            if alt.get("pokemon_name"):
                names_to_resolve.add(alt["pokemon_name"])
    for fact in data.get("fun_facts", []):
        if fact.get("pokemon_name"):
            names_to_resolve.add(fact["pokemon_name"])

    sprite_by_name: dict[str, str | None] = {}
    if names_to_resolve:
        names_list = list(names_to_resolve)
        sprites = await asyncio.gather(*(_resolve_sprite(n) for n in names_list))
        sprite_by_name = dict(zip(names_list, sprites))

    for member in data.get("ideal_team", []):
        member["sprite_url"] = sprite_by_name.get(member.get("pokemon_name"))
        for alt in member.get("alternatives", []) or []:
            alt["sprite_url"] = sprite_by_name.get(alt.get("pokemon_name"))
    for fact in data.get("fun_facts", []):
        fact["sprite_url"] = sprite_by_name.get(fact.get("pokemon_name"))

    # El equipo analizado sale directo de la base de datos (dato real del
    # usuario, no del modelo) — ya tenemos sprite_url y types guardados.
    data["analyzed_team"] = [
        {"pokemon_name": e.pokemon_name, "sprite_url": e.sprite_url, "types": e.types or []}
        for e in entries
    ]

    return CollectionInsights.model_validate(data)
