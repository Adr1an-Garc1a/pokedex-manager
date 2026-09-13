"""Bonus 3 — Análisis inteligente de la colección (Gemini 2.5 Flash, Vertex AI).

Toma el historial real de la colección del usuario (tipos, favoritos,
niveles) y le pide al modelo: un equipo ideal de 6 Pokémon (puede mezclar
Pokémon que el usuario ya tiene con sugerencias nuevas), fortalezas y
debilidades de tipo de la colección actual, datos curiosos, y alternativas
sugeridas. Reutiliza el mismo cliente de Gemini que vision.py.
"""
from __future__ import annotations

from app.models.collection import CollectionEntry
from app.schemas.ai import CollectionInsights
from app.services.ai.gemini_client import generate_structured_json

_SYSTEM_INSTRUCTION = (
    "Eres un entrenador experto de Pokémon analizando la colección personal de un "
    "usuario para darle consejos prácticos y entretenidos. Responde siempre en "
    "español y en el formato JSON solicitado. El 'equipo ideal' debe tener como "
    "máximo 6 Pokémon: prioriza los que ya tiene el usuario en su colección "
    "(marca already_in_collection=true) y completa los espacios restantes con "
    "sugerencias nuevas que complementen bien al equipo (cobertura de tipos, "
    "balance ofensivo/defensivo). Sé específico y evita respuestas genéricas."
)

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ideal_team": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "pokemon_name": {"type": "STRING"},
                    "reason": {"type": "STRING", "description": "Por qué este Pokémon está en el equipo ideal"},
                    "already_in_collection": {"type": "BOOLEAN"},
                },
                "required": ["pokemon_name", "reason", "already_in_collection"],
            },
        },
        "strengths": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Fortalezas de tipo/composición de la colección actual",
        },
        "weaknesses": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Debilidades o huecos de cobertura de tipo de la colección actual",
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
        "suggested_additions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "pokemon_name": {"type": "STRING"},
                    "reason": {"type": "STRING"},
                },
                "required": ["pokemon_name", "reason"],
            },
            "description": "Pokémon que el usuario no tiene y le convendría agregar",
        },
    },
    "required": ["ideal_team", "strengths", "weaknesses", "fun_facts", "suggested_additions"],
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


async def generate_collection_insights(entries: list[CollectionEntry]) -> CollectionInsights:
    from google.genai import types  # import perezoso, ver gemini_client.py

    summary = _summarize_collection(entries)
    prompt = (
        f"Esta es la colección actual del usuario ({len(entries)} Pokémon):\n\n"
        f"{summary}\n\n"
        "Genera el análisis según el esquema JSON solicitado."
    )

    parts = [types.Part.from_text(text=prompt)]
    data = await generate_structured_json(
        parts=parts, response_schema=_RESPONSE_SCHEMA, system_instruction=_SYSTEM_INSTRUCTION
    )
    return CollectionInsights.model_validate(data)
