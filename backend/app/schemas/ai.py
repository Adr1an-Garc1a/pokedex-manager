"""Esquemas de las funcionalidades bonus de IA (Vision, Chat MCP, Insights)."""
from __future__ import annotations

from pydantic import BaseModel, Field


# --- 1. Vision (Gemini 2.5 Flash vía Vertex AI) ---------------------------


class PokemonVisionResult(BaseModel):
    entry_id: str | None = Field(
        default=None, description="ID de esta consulta en el historial (None hasta que se persiste)"
    )
    created_at: str | None = Field(default=None, description="Timestamp ISO de cuándo se hizo la consulta")

    image_url: str = Field(description="URL de la foto subida por el usuario (Cloud Storage/local)")

    pokemon_name: str = Field(description="Nombre del Pokémon identificado por el modelo")
    description: str = Field(description="Descripción breve generada por el modelo")
    confidence: str = Field(
        description="Qué tan seguro dice estar el modelo de la identificación (texto libre, ej. 'alta'/'media'/'baja')"
    )

    # "En qué juego salió por primera vez" / "en qué zonas es fácil encontrarlo".
    # Se le pide un estimado al modelo como respaldo, pero se sobreescribe con
    # el dato real de PokéAPI (generación / hábitat) cuando el nombre
    # identificado se resuelve contra la Pokédex oficial — ver services/ai/vision.py.
    first_appearance_game: str = Field(description="Juego(s) en que el Pokémon apareció por primera vez")
    habitat_zones: str = Field(description="Zonas/hábitats donde suele ser fácil encontrar a este Pokémon")

    # Resueltos contra PokéAPI (no directamente del modelo) cuando el nombre
    # identificado existe en el catálogo real — ver services/ai/vision.py.
    matched_pokemon_id: int | None = Field(
        default=None, description="ID en PokéAPI si el nombre identificado se pudo resolver"
    )
    sprite_url: str | None = None
    types: list[str] = Field(default_factory=list)
    strong_against: list[str] = Field(default_factory=list, description="Tipos (slug EN) contra los que es fuerte")
    weak_against: list[str] = Field(default_factory=list, description="Tipos (slug EN) contra los que es débil")
    strong_against_es: list[str] = Field(
        default_factory=list, description="Igual que strong_against, traducido a español (mismo orden)"
    )
    weak_against_es: list[str] = Field(
        default_factory=list, description="Igual que weak_against, traducido a español (mismo orden)"
    )
    height_m: float | None = Field(default=None, description="Altura en metros (dato real de PokéAPI)")
    weight_kg: float | None = Field(default=None, description="Peso en kilogramos (dato real de PokéAPI)")
    abilities: list[str] = Field(default_factory=list, description="Habilidades (dato real de PokéAPI)")
    pre_evolution: str | None = Field(
        default=None, description="Nombre de la pre-evolución inmediata, si tiene"
    )
    evolutions: list[str] = Field(
        default_factory=list, description="Nombres de sus evoluciones directas (puede ser más de una, ej. Eevee)"
    )

    history_persisted: bool = Field(
        default=True,
        description="false si la identificación se hizo bien pero no se pudo guardar en el historial de Firestore",
    )


# --- 2. Chat MCP (Claude, modelo configurable vía ANTHROPIC_MODEL) --------


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    ts: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    client_history: list[ChatMessage] = Field(
        default_factory=list,
        description=(
            "Copia local (frontend) del historial de esta conversación — se fusiona con lo que "
            "Firestore tenga guardado, para que el contexto de la conversación sobreviva aunque "
            "el guardado en Firestore esté fallando (ver docs/BONUS_FEATURES.md)"
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessage]
    history_persisted: bool = Field(
        default=True,
        description=(
            "false si Claude sí respondió pero no se pudo guardar este turno en Firestore "
            "(el chat sigue funcionando igual, solo no queda guardado para la próxima vez)"
        ),
    )


# --- 3. Insights de colección (Gemini 2.5 Flash) --------------------------


class AnalyzedTeamMember(BaseModel):
    """Uno de los primeros 6 Pokémon de la colección del usuario — el equipo
    real sobre el que se basa TODO el análisis. Se arma directamente desde la
    base de datos (no desde el modelo), así que sprite_url siempre es el real."""

    pokemon_name: str
    sprite_url: str | None = None
    types: list[str] = Field(default_factory=list)


class AlternativeSuggestion(BaseModel):
    pokemon_name: str
    reason: str
    sprite_url: str | None = None


class TeamRecommendation(BaseModel):
    pokemon_name: str
    reason: str
    already_in_collection: bool = False
    sprite_url: str | None = None
    alternatives: list[AlternativeSuggestion] = Field(
        default_factory=list,
        description="Otros Pokémon que podrían ocupar este mismo puesto del equipo ideal",
    )


class FunFactEntry(BaseModel):
    pokemon_name: str
    fact: str
    sprite_url: str | None = None


class CollectionInsights(BaseModel):
    analyzed_team: list[AnalyzedTeamMember] = Field(
        default_factory=list,
        description="Los primeros 6 Pokémon de la colección del usuario (o menos si tiene menos) — base de todo el análisis",
    )
    team_score: int = Field(ge=1, le=10, description="Qué tan bueno es este equipo, de 1 a 10")
    team_score_reason: str = Field(default="", description="Por qué obtuvo ese puntaje")
    ideal_team: list[TeamRecommendation] = Field(default_factory=list, max_length=6)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    fun_facts: list[FunFactEntry] = Field(default_factory=list)
