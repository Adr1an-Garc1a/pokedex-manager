"""Esquemas de las funcionalidades bonus de IA (Vision, Chat MCP, Insights)."""
from __future__ import annotations

from pydantic import BaseModel, Field


# --- 1. Vision (Gemini 2.5 Flash vía Vertex AI) ---------------------------


class PokemonVisionResult(BaseModel):
    image_url: str = Field(description="URL de la foto subida por el usuario (Cloud Storage/local)")

    pokemon_name: str = Field(description="Nombre del Pokémon identificado por el modelo")
    description: str = Field(description="Descripción breve generada por el modelo")
    fun_fact: str = Field(description="Un dato curioso sobre el Pokémon")
    confidence: str = Field(
        description="Qué tan seguro dice estar el modelo de la identificación (texto libre, ej. 'alta'/'media'/'baja')"
    )

    # Resueltos contra PokéAPI (no directamente del modelo) cuando el nombre
    # identificado existe en el catálogo real — ver services/ai/vision.py.
    matched_pokemon_id: int | None = Field(
        default=None, description="ID en PokéAPI si el nombre identificado se pudo resolver"
    )
    sprite_url: str | None = None
    types: list[str] = Field(default_factory=list)
    strong_against: list[str] = Field(default_factory=list, description="Tipos contra los que es fuerte")
    weak_against: list[str] = Field(default_factory=list, description="Tipos contra los que es débil")


# --- 2. Chat MCP (Claude Sonnet 5) ----------------------------------------


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    ts: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessage]


# --- 3. Insights de colección (Gemini 2.5 Flash) --------------------------


class TeamRecommendation(BaseModel):
    pokemon_name: str
    reason: str
    already_in_collection: bool = False


class FunFactEntry(BaseModel):
    pokemon_name: str
    fact: str


class SuggestedAddition(BaseModel):
    pokemon_name: str
    reason: str


class CollectionInsights(BaseModel):
    ideal_team: list[TeamRecommendation] = Field(default_factory=list, max_length=6)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    fun_facts: list[FunFactEntry] = Field(default_factory=list)
    suggested_additions: list[SuggestedAddition] = Field(default_factory=list)
