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
(id = str(user.id)), con un solo campo `threads`: un dict `{thread_id: {...}}`
donde cada conversación tiene su propio `title`, `messages` (lista completa
de turnos {role, content, ts}), `created_at` y `updated_at`. Antes había un
solo array `messages` a nivel de usuario (una sola conversación posible);
esto pasó a un dict de conversaciones para soportar "Iniciar nueva
conversación" + poder ver/retomar cualquier conversación anterior, pedido
explícito del usuario. Se mantiene como UN SOLO documento (no una
subcolección `threads/{id}`) por el mismo motivo original: para el volumen de
un chat personal esto es más simple (una sola lectura/escritura, sin
paginar) y sigue evitando tener que administrar una subcolección aparte.

Import perezoso de `google.cloud.firestore` — mismo motivo que gemini_client.py
y storage.py: el backend debe poder arrancar (y correr sus tests) sin
credenciales de GCP configuradas.
"""
from __future__ import annotations

import logging
import uuid
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


def _make_title(user_message: str) -> str:
    """Título derivado del primer mensaje del usuario en la conversación —
    evita otra llamada al modelo solo para "resumir en un título"."""
    text = " ".join(user_message.strip().split())
    if not text:
        return "Nueva conversación"
    return text if len(text) <= 40 else text[:39].rstrip() + "…"


async def _get_threads_doc(user_id: int) -> dict:
    """Todas las conversaciones (crudas, sin recortar) del usuario. Vacío si
    nunca ha chateado o si Firestore no está disponible en este entorno."""
    try:
        client = _get_client()
        doc = await client.collection(_COLLECTION).document(str(user_id)).get()
    except Exception:
        logger.warning("No se pudo leer las conversaciones de chat desde Firestore", exc_info=True)
        return {}

    if not doc.exists:
        return {}
    return doc.to_dict().get("threads", {})


async def list_threads(user_id: int) -> list[dict]:
    """Resumen de TODAS las conversaciones del usuario (sin sus mensajes),
    más reciente primero — para el selector de 'todas mis conversaciones'."""
    threads = await _get_threads_doc(user_id)
    summaries = [
        {
            "id": thread_id,
            "title": data.get("title") or "Nueva conversación",
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "message_count": len(data.get("messages", [])),
        }
        for thread_id, data in threads.items()
    ]
    summaries.sort(key=lambda s: s["updated_at"] or "", reverse=True)
    return summaries


async def get_thread_messages(user_id: int, thread_id: str) -> list[dict]:
    """Mensajes de UNA conversación en particular (vacío si no existe — por
    ejemplo, una conversación recién creada en el frontend que todavía no ha
    recibido su primer turno)."""
    threads = await _get_threads_doc(user_id)
    return threads.get(thread_id, {}).get("messages", [])


async def create_thread(user_id: int) -> dict:
    """Crea una conversación nueva y vacía — 'Iniciar nueva conversación'."""
    now = datetime.now(timezone.utc).isoformat()
    thread_id = uuid.uuid4().hex
    thread_data = {"title": "Nueva conversación", "messages": [], "created_at": now, "updated_at": now}
    try:
        client = _get_client()
        doc_ref = client.collection(_COLLECTION).document(str(user_id))
        snapshot = await doc_ref.get()
        threads = snapshot.to_dict().get("threads", {}) if snapshot.exists else {}
        threads[thread_id] = thread_data
        await doc_ref.set({"threads": threads})
    except Exception as exc:
        logger.exception("No se pudo crear la conversación de chat en Firestore")
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo iniciar la conversación (Firestore no disponible). Detalle técnico: {exc}",
        ) from exc
    return {"id": thread_id, "message_count": 0, **{k: thread_data[k] for k in ("title", "created_at", "updated_at")}}


async def append_turn(
    user_id: int,
    thread_id: str,
    *,
    user_message: str,
    assistant_reply: str,
    base_history: list[dict] | None = None,
) -> list[dict]:
    """Agrega el turno (mensaje del usuario + respuesta del asistente) a ESA
    conversación (`thread_id`) y devuelve su historial completo actualizado.
    Si la conversación no existía todavía (por ejemplo, el frontend mandó
    `thread_id=None` y este es el primer mensaje), se crea aquí mismo, con un
    título derivado de este primer mensaje.

    `base_history`, si se pasa (ver chat.py — es el historial ya fusionado
    con lo que mandó el frontend), se usa como base en vez de releer el
    documento de Firestore: así, si el documento se había quedado corto por
    fallos de guardado anteriores, este guardado "autocura" con la versión
    más completa que se tenga, en vez de perpetuar el hueco. Si no se pasa
    (compatibilidad con otros llamadores), se relee Firestore como antes.
    """
    now = datetime.now(timezone.utc).isoformat()
    new_messages = [
        {"role": "user", "content": user_message, "ts": now},
        {"role": "assistant", "content": assistant_reply, "ts": now},
    ]

    try:
        client = _get_client()
        doc_ref = client.collection(_COLLECTION).document(str(user_id))
        snapshot = await doc_ref.get()
        threads = snapshot.to_dict().get("threads", {}) if snapshot.exists else {}
        existing = threads.get(thread_id, {})

        if base_history is not None:
            history = list(base_history)
        else:
            history = list(existing.get("messages", []))
        history.extend(new_messages)

        threads[thread_id] = {
            "title": existing.get("title") or _make_title(user_message),
            "messages": history,
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }
        await doc_ref.set({"threads": threads})
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


async def delete_thread(user_id: int, thread_id: str) -> None:
    """Borra UNA conversación (no todas) — usado para "eliminar" una
    conversación puntual de la lista, sin perder las demás."""
    try:
        client = _get_client()
        doc_ref = client.collection(_COLLECTION).document(str(user_id))
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return
        threads = snapshot.to_dict().get("threads", {})
        if thread_id in threads:
            threads.pop(thread_id)
            await doc_ref.set({"threads": threads})
    except Exception:
        logger.warning("No se pudo borrar la conversación de chat en Firestore", exc_info=True)


# --- Historial de Vision (bonus 1) -----------------------------------------
#
# Mismo patrón/razonamiento que mcp_conversations arriba: una colección
# `vision_history`, un documento por usuario, con el array completo de
# consultas pasadas (incluida la imagen que subió cada vez). A diferencia del
# chat, guardar el historial de Vision es "best effort": si Firestore falla,
# la identificación ya se hizo y de todos modos se le muestra al usuario —
# solo no queda guardada para verla después. Por eso estas funciones nunca
# lanzan HTTPException.

_VISION_COLLECTION = "vision_history"
_MAX_VISION_HISTORY = 50  # se recorta a las últimas N consultas por usuario


async def get_vision_history(user_id: int) -> list[dict]:
    """Más reciente primero. Vacío si el usuario nunca ha usado Vision o si
    Firestore no está disponible en este entorno."""
    try:
        client = _get_client()
        doc = await client.collection(_VISION_COLLECTION).document(str(user_id)).get()
    except Exception:
        logger.warning("No se pudo leer el historial de Vision desde Firestore", exc_info=True)
        return []

    if not doc.exists:
        return []
    entries = doc.to_dict().get("entries", [])
    return list(reversed(entries))


async def append_vision_entry(user_id: int, entry: dict) -> bool:
    """Devuelve True si se guardó, False si falló (nunca lanza excepción: la
    identificación ya se le mostró al usuario, perder el guardado en el
    historial es un problema menor, no debe tumbar la respuesta — pero sí se
    le informa al frontend vía el campo `history_persisted`, igual que en el
    chat, en vez de fallar en silencio total)."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        client = _get_client()
        doc_ref = client.collection(_VISION_COLLECTION).document(str(user_id))
        snapshot = await doc_ref.get()
        entries = snapshot.to_dict().get("entries", []) if snapshot.exists else []
        entries.append(entry)
        entries = entries[-_MAX_VISION_HISTORY:]
        await doc_ref.set({"entries": entries, "updated_at": now})
        return True
    except Exception:
        logger.warning("No se pudo guardar la consulta de Vision en el historial", exc_info=True)
        return False
