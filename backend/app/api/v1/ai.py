"""Rutas de las funcionalidades bonus de IA:
  1. POST /ai/vision/identify   — identificar un Pokémon por foto (Gemini)
  2. POST /ai/chat              — chat MCP sobre tu colección (Claude Sonnet 5)
  3. GET  /ai/chat/history      — recuperar el historial de chat
  4. DELETE /ai/chat/history    — reiniciar la conversación
  5. GET  /ai/insights          — análisis inteligente de tu colección (Gemini)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.collection import CollectionEntry
from app.models.user import User
from app.schemas.ai import ChatRequest, ChatResponse, CollectionInsights, PokemonVisionResult
from app.services.ai.chat import run_pokedex_chat
from app.services.ai.insights import generate_collection_insights
from app.services.ai.vision import identify_pokemon_from_image
from app.services.firestore_client import get_conversation, reset_conversation
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
        image_bytes=content, mime_type=file.content_type, image_url=image_url
    )


@router.get("/chat/history", response_model=list[dict])
async def chat_history(current_user: User = Depends(get_current_user)):
    return await get_conversation(current_user.id)


@router.delete("/chat/history", status_code=204)
async def chat_reset(current_user: User = Depends(get_current_user)):
    await reset_conversation(current_user.id)


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
    reply, history = await run_pokedex_chat(
        db=db, user=current_user, user_message=payload.message
    )
    return ChatResponse(reply=reply, history=history)


@router.get("/insights", response_model=CollectionInsights)
async def insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = (
        db.query(CollectionEntry).filter(CollectionEntry.user_id == current_user.id).all()
    )
    if not entries:
        raise HTTPException(
            status_code=422,
            detail="Agrega al menos un Pokémon a tu colección para poder generar insights.",
        )
    return await generate_collection_insights(entries)
