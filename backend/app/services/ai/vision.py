"""Bonus 1 — Identificar un Pokémon a partir de una foto (Gemini 2.5 Flash,
Vertex AI Model Garden).

Diseño (ver docs/BONUS_FEATURES.md para más detalle):
  1. La foto se sube a Cloud Storage (o disco en dev) con el StorageService
     ya existente — se reutiliza tal cual, mismo patrón que las imágenes
     personalizadas de la colección.
  2. Gemini identifica el Pokémon y redacta una descripción + un estimado de
     en qué juego apareció por primera vez / en qué zonas se encuentra (esto
     SÍ se le pide al modelo, como respaldo).
  3. En vez de confiarle al modelo las ventajas/desventajas de tipo, la
     generación de debut, o el hábitat (puede alucinar), se resuelve el
     nombre contra PokéAPI (la misma fuente de verdad que usa el resto de la
     app) y esos tres datos se sobreescriben con el dato real cuando el
     nombre identificado existe en el catálogo. Si no existe (el modelo se
     equivocó o el Pokémon no es de la gen soportada), se devuelve igual la
     identificación "cruda" del modelo, sin esos campos extra.
  4. La consulta completa (incluida la foto) se guarda en el historial de
     Vision del usuario en Firestore (best effort, ver firestore_client.py).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.schemas.ai import PokemonVisionResult
from app.services.ai.gemini_client import generate_structured_json
from app.services.firestore_client import append_vision_entry
from app.services.pokeapi_client import get_pokeapi_client, translate_types_es

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
        "first_appearance_game": {
            "type": "STRING",
            "description": "Tu mejor estimado de en qué videojuego de Pokémon apareció por primera vez, en español",
        },
        "habitat_zones": {
            "type": "STRING",
            "description": "Tu mejor estimado de en qué zonas/hábitats es fácil encontrar a este Pokémon, en español",
        },
        "confidence": {
            "type": "STRING",
            "description": "Qué tan seguro estás de la identificación: 'alta', 'media' o 'baja', con una breve razón",
        },
    },
    "required": [
        "pokemon_name",
        "description",
        "first_appearance_game",
        "habitat_zones",
        "confidence",
    ],
}


async def identify_pokemon_from_image(
    *, image_bytes: bytes, mime_type: str, image_url: str, user_id: int
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
        first_appearance_game=data.get("first_appearance_game", "No disponible"),
        habitat_zones=data.get("habitat_zones", "No disponible"),
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
        result.strong_against_es = translate_types_es(strong_against)
        result.weak_against_es = translate_types_es(weak_against)

        # Juego de primera aparición / hábitat: se sobreescribe el estimado
        # del modelo con el dato real de PokéAPI (/pokemon-species/{id}).
        species = await client.get_species_info(detail.id)
        result.first_appearance_game = species["first_appearance_game"]
        result.habitat_zones = species["habitat_zones"]
    except Exception:
        # El modelo identificó algo que no existe (tal cual) en PokéAPI —
        # se devuelve igual la identificación "cruda" del modelo.
        pass

    result.entry_id = uuid.uuid4().hex
    result.created_at = datetime.now(timezone.utc).isoformat()

    await append_vision_entry(user_id, result.model_dump())

    return result
