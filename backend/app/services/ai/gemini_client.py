"""Cliente compartido para Gemini 2.5 Flash vía Vertex AI (Model Garden).

Usado por vision.py (identificar Pokémon por foto) e insights.py (análisis de
la colección). Import perezoso de `google.genai` a propósito — igual que
services/storage.py con `google.cloud.storage` — para que el backend arranque
sin problema en entornos donde estas funcionalidades bonus todavía no están
configuradas (dev local sin credenciales de GCP, por ejemplo).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("pokedex_manager.ai.gemini")

_client_singleton = None


def _get_client():
    global _client_singleton
    if _client_singleton is None:
        from google import genai  # import perezoso: solo si se usa una función de IA

        _client_singleton = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project or None,
            location=settings.vertex_location,
        )
    return _client_singleton


async def generate_structured_json(
    *,
    parts: list[Any],
    response_schema: dict,
    system_instruction: str,
) -> dict:
    """Llama a Gemini 2.5 Flash pidiendo una respuesta JSON que cumpla
    `response_schema`, y devuelve el dict ya parseado.

    Lanza HTTPException(503) si Vertex AI no está configurado/disponible en
    este entorno, o HTTPException(502) si el modelo no devolvió JSON válido.
    """
    from google.genai import types  # import perezoso, mismo motivo que _get_client

    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.4,
            ),
        )
    except Exception as exc:  # credenciales/ADC ausentes, API deshabilitada, cuota, etc.
        logger.exception("Fallo llamando a Vertex AI (Gemini)")
        raise HTTPException(
            status_code=503,
            detail=(
                "El servicio de IA (Vertex AI / Gemini) no está disponible. Verifica que "
                "aiplatform.googleapis.com esté habilitado, que la service account tenga "
                "roles/aiplatform.user, y que GOOGLE_CLOUD_PROJECT esté configurado. "
                f"Detalle técnico: {exc}"
            ),
        ) from exc

    text = response.text
    if not text:
        raise HTTPException(status_code=502, detail="Gemini no devolvió contenido.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini devolvió un JSON inválido: %s", text[:500])
        raise HTTPException(
            status_code=502, detail="Gemini devolvió una respuesta que no se pudo interpretar."
        ) from exc
