"""Persistencia de las conversaciones del chat MCP en Firestore.

Por qué Firestore (y no Postgres/Cloud SQL, que ya tenemos): es la opción
natural de GCP para este tipo de dato — documentos semi-estructurados, de
tamaño variable (una conversación crece con cada mensaje), sin necesidad de
joins ni transacciones complejas, con un free tier generoso y cero
administración (a diferencia de Cloud SQL, no hay una instancia que
mantener). Encaja además con el resto de la arquitectura: un servicio
serverless más, mismo patrón de "un recurso de GCP por responsabilidad" que
Cloud SQL (datos relacionales), GCS (imágenes) y Secret Manager (secretos).

Modelo de datos: una colección `mcp_conversations`, un documento por usuario
(id = str(user.id)), con un solo campo `messages`: la lista completa de
turnos {role, content, ts}. Para el volumen de un chat personal (decenas o
cientos de mensajes) esto es más simple que una subcolección por mensaje, y
evita tener que paginar al cargar el historial completo del chat.

Import perezoso de `google.cloud.firestore` — mismo motivo que gemini_client.py
y storage.py: el backend debe poder arrancar (y correr sus tests) sin
credenciales de GCP configuradas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException

logger = logging.getLogger("pokedex_manager.ai.firestore")

_COLLECTION = "mcp_conversations"
_client_singleton = None


def _get_client():
    global _client_singleton
    if _client_singleton is None:
        from google.cloud import firestore  # import perezoso

        _client_singleton = firestore.AsyncClient()
    return _client_singleton


async def get_conversation(user_id: int) -> list[dict]:
    """Devuelve el historial de mensajes del usuario (vacío si nunca ha chateado
    o si Firestore no está configurado en este entorno — se degrada con
    gracia en vez de tumbar la carga del widget de chat)."""
    try:
        client = _get_client()
        doc = await client.collection(_COLLECTION).document(str(user_id)).get()
    except Exception:
        logger.warning("No se pudo leer el historial de chat desde Firestore", exc_info=True)
        return []

    if not doc.exists:
        return []
    return doc.to_dict().get("messages", [])


async def append_turn(user_id: int, *, user_message: str, assistant_reply: str) -> list[dict]:
    """Agrega el turno (mensaje del usuario + respuesta del asistente) al
    historial persistido y devuelve el historial completo actualizado."""
    now = datetime.now(timezone.utc).isoformat()
    new_messages = [
        {"role": "user", "content": user_message, "ts": now},
        {"role": "assistant", "content": assistant_reply, "ts": now},
    ]

    try:
        client = _get_client()
        doc_ref = client.collection(_COLLECTION).document(str(user_id))
        snapshot = await doc_ref.get()
        history = snapshot.to_dict().get("messages", []) if snapshot.exists else []
        history.extend(new_messages)
        await doc_ref.set({"messages": history, "updated_at": now})
        return history
    except Exception as exc:
        logger.exception("No se pudo guardar el turno de chat en Firestore")
        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo guardar la conversación (Firestore no disponible). "
                f"Detalle técnico: {exc}"
            ),
        ) from exc


async def reset_conversation(user_id: int) -> None:
    try:
        client = _get_client()
        await client.collection(_COLLECTION).document(str(user_id)).delete()
    except Exception:
        logger.warning("No se pudo borrar el historial de chat en Firestore", exc_info=True)
