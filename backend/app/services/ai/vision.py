"""Bonus 1 — Identificar un Pokémon a partir de una foto (Gemini 2.5 Flash,
Vertex AI Model Garden).

Diseño (ver docs/BONUS_FEATURES.md para más detalle):
  1. La foto se sube a Cloud Storage (o disco en dev) con el StorageService
     ya existente — se reutiliza tal cual, mismo patrón que las imágenes
     personalizadas de la colección.
  2. Gemini identifica el Pokémon y redacta una descripción + un fun fact
     (esto SÍ se le pide al modelo, es lo que aporta valor de "IA").
  3. En vez de confiarle al modelo las ventajas/desventajas de tipo (puede
     alucinar la tabla de tipos), se resuelve el nombre contra PokéAPI (la
     misma fuente de verdad que usa el resto de la app) y de ahí se calculan
     fuerte/débil-contra con datos reales. Si el nombre no existe en PokéAPI
     (el modelo se equivocó o el Pokémon no es de la gen soportada), se
     devuelve igual la identificación del modelo, sin esos campos extra.
"""
from __future__ import annotations

from app.schemas.ai import PokemonVisionResult
from app.services.ai.gemini_client import generate_structured_json
from app.services.pokeapi_client import get_pokeapi_client

_SYSTEM_INSTRUCTION = (
    "Eres un experto en Pokémon ayudando a identificar Pokémon a partir de fotos "
    "(pueden ser cartas coleccionables, capturas de videojuegos, peluches, dibujos "
    "o fotos de la vida real de algo con forma de Pokémon). Responde siempre en "
    "español, de forma concisa y en el formato JSON solicitado. Si la imagen no "
    "muestra un Pokémon reconocible, responde con tu mejor intento y explica la "
    "incertidumbre en el campo 'confidence'."
)

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pokemon_name": {
            "type": "STRING",
            "description": "Nombre del Pokémon en inglés, en minúsculas, tal como aparece en la Pokédex oficial (ej. 'pikachu', 'charizard')",
        },
        "description": {"type": "STRING", "description": "Descripción breve (1-2 frases) en español"},
        "fun_fact": {"type": "STRING", "description": "Un dato curioso sobre el Pokémon, en español"},
        "confidence": {
            "type": "STRING",
            "description": "Qué tan seguro estás de la identificación: 'alta', 'media' o 'baja', con una breve razón",
        },
    },
    "required": ["pokemon_name", "description", "fun_fact", "confidence"],
}


async def identify_pokemon_from_image(
    *, image_bytes: bytes, mime_type: str, image_url: str
) -> PokemonVisionResult:
    from google.genai import types  # import perezoso, ver gemini_client.py

    parts = [
        types.Part.from_text(
            text=(
                "Identifica el Pokémon en esta imagen y describe sus características "
                "según el esquema JSON solicitado."
            )
        ),
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
    ]

    data = await generate_structured_json(
        parts=parts, response_schema=_RESPONSE_SCHEMA, system_instruction=_SYSTEM_INSTRUCTION
    )

    result = PokemonVisionResult(
        image_url=image_url,
        pokemon_name=data.get("pokemon_name", "desconocido"),
        description=data.get("description", ""),
        fun_fact=data.get("fun_fact", ""),
        confidence=data.get("confidence", ""),
    )

    # Resolver contra PokéAPI (fuente autoritativa) — best effort, no debe
    # tumbar la respuesta si el nombre no matchea nada real.
    try:
        client = get_pokeapi_client()
        detail = await client.get_pokemon(result.pokemon_name)
        strong_against, weak_against = await client.get_type_matchups(detail.types)
        result.matched_pokemon_id = detail.id
        result.sprite_url = detail.sprite_url
        result.types = detail.types
        result.strong_against = strong_against
        result.weak_against = weak_against
    except Exception:
        # El modelo identificó algo que no existe (tal cual) en PokéAPI —
        # se devuelve igual la identificación "cruda" del modelo.
        pass

    return result
