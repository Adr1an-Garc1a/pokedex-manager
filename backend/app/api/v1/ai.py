"""Rutas de las funcionalidades bonus de IA:
  1. POST   /ai/vision/identify        — identificar un Pokémon por foto (Gemini)
  2. GET    /ai/vision/history         — historial de identificaciones pasadas (con imagen)
  3. POST   /ai/chat                   — chat MCP sobre tu colección (Claude), en una conversación
  4. GET    /ai/chat/threads           — lista de TODAS tus conversaciones (sin sus mensajes)
  5. POST   /ai/chat/threads           — "Iniciar nueva conversación" (crea una vacía)
  6. GET    /ai/chat/threads/{id}      — mensajes de una conversación en particular
  7. DELETE /ai/chat/threads/{id}      — borrar una conversación puntual
  8. GET    /ai/insights               — análisis inteligente de tu colección (Gemini)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatThreadSummary,
    CollectionInsights,
    PokemonVisionResult,
)
from app.services.ai.chat import run_pokedex_chat
from app.services.ai.insights import generate_collection_insights
from app.services.ai.vision import identify_pokemon_from_image
from app.services.team import get_effective_team
from app.services.firestore_client import (
    create_thread,
    delete_thread,
    get_thread_messages,
    get_vision_history,
    list_threads,
)
from app.services.storage import get_storage_service

router = APIRouter(prefix="/ai", tags=["ai"])
settings = get_settings()

_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/vision/identify", response_model=PokemonVisionResult)
async def vision_identify(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=422, detail="Formato de imagen no soportado (usa JPG, PNG o WEBP)")

    content = await file.read()
    if len(content) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="La imagen es demasiado grande (máximo 8 MB)")
    await file.seek(0)

    storage = get_storage_service()
    image_url = await storage.save_image(file, subfolder=f"vision/{current_user.id}")

    return await identify_pokemon_from_image(
        image_bytes=content,
        mime_type=file.content_type,
        image_url=image_url,
        user_id=current_user.id,
    )


@router.get("/vision/history", response_model=list[PokemonVisionResult])
async def vision_history(current_user: User = Depends(get_current_user)):
    """Historial de consultas pasadas del usuario (más reciente primero),
    incluida la imagen que subió cada vez."""
    return await get_vision_history(current_user.id)


@router.get("/chat/threads", response_model=list[ChatThreadSummary])
async def chat_list_threads(current_user: User = Depends(get_current_user)):
    """Todas las conversaciones del usuario (más reciente primero), sin sus
    mensajes — para el selector de "todas mis conversaciones"."""
    return await list_threads(current_user.id)


@router.post("/chat/threads", response_model=ChatThreadSummary, status_code=201)
async def chat_create_thread(current_user: User = Depends(get_current_user)):
    """"Iniciar nueva conversación": crea una conversación vacía y la
    devuelve — el frontend la vuelve la conversación activa de inmediato."""
    return await create_thread(current_user.id)


@router.get("/chat/threads/{thread_id}", response_model=list[ChatMessage])
async def chat_thread_messages(thread_id: str, current_user: User = Depends(get_current_user)):
    """Mensajes de UNA conversación — el usuario la abre desde la lista para
    retomarla donde la dejó."""
    return await get_thread_messages(current_user.id, thread_id)


@router.delete("/chat/threads/{thread_id}", status_code=204)
async def chat_delete_thread(thread_id: str, current_user: User = Depends(get_current_user)):
    await delete_thread(current_user.id, thread_id)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "El chat con IA no está configurado en este entorno: falta ANTHROPIC_API_KEY. "
                "Ver docs/BONUS_FEATURES.md."
            ),
        )
    reply, history, persisted, thread_id = await run_pokedex_chat(
        db=db,
        user=current_user,
        user_message=payload.message,
        client_history=[m.model_dump() for m in payload.client_history],
        thread_id=payload.thread_id,
    )
    return ChatResponse(reply=reply, history=history, history_persisted=persisted, thread_id=thread_id)


@router.get("/insights", response_model=CollectionInsights)
async def insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # El análisis se basa en el "equipo efectivo" del usuario (hasta 6): el
    # que eligió a mano con PUT /collection/team si ya lo hizo, o si no, los
    # primeros 6 Pokémon que agregó (comportamiento por defecto, ver
    # app/services/team.py) — así una colección de 6 o menos nunca necesita
    # elegir nada.
    team = get_effective_team(db, current_user.id)
    if not team:
        raise HTTPException(
            status_code=422,
            detail="Agrega al menos un Pokémon a tu colección para poder generar insights.",
        )
    return await generate_collection_insights(team)
