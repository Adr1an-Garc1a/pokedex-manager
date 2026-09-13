"""Tests de las funcionalidades bonus de IA.

Igual que test_pokemon.py y test_auth.py: nada de red real ni credenciales
de GCP/Anthropic. Se monkeypatch-ean los puntos donde el código habla con
servicios externos (Gemini, Claude, Firestore, storage) y se deja correr de
verdad la parte que sí es "nuestra": la resolución contra PokéAPI (con SU
cliente también monkeypatched) y, en el caso del chat, el loop MCP completo
de principio a fin (servidor MCP real, en memoria, contra la base de datos
de test).
"""
from __future__ import annotations

import pytest

from app.api.v1 import ai as ai_module
from app.api.v1 import auth as auth_module
from app.schemas.pokemon import PokemonDetail, PokemonStat
from app.services import pokeapi_client as pokeapi_client_module
from app.services.ai import chat as chat_module


class _FakeGoogleUser:
    def __init__(self, sub: str, email: str, name: str):
        self.sub, self.email, self.name, self.picture = sub, email, name, None


def _register_and_get_token(client, monkeypatch, *, sub: str, email: str, name: str) -> str:
    monkeypatch.setattr(
        auth_module, "verify_google_id_token", lambda token: _FakeGoogleUser(sub, email, name)
    )
    response = client.post(
        "/api/v1/auth/google/register", json={"id_token": "fake-token", "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


@pytest.fixture(autouse=True)
def _reset_pokeapi_singleton():
    pokeapi_client_module._client_singleton = None
    yield
    pokeapi_client_module._client_singleton = None


def _fake_pikachu() -> PokemonDetail:
    return PokemonDetail(
        id=25,
        name="pikachu",
        height=4,
        weight=60,
        sprite_url="https://example.com/25.png",
        artwork_url="https://example.com/artwork/25.png",
        types=["electric"],
        abilities=["static"],
        stats=[PokemonStat(name="hp", base_stat=35)],
    )


# --- 1. Vision -------------------------------------------------------------


def test_vision_identify_requires_auth(client):
    response = client.post(
        "/api/v1/ai/vision/identify",
        files={"file": ("foto.jpg", b"contenido-fake", "image/jpeg")},
    )
    assert response.status_code == 401


def test_vision_identify_rejects_unsupported_file_type(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-vision-1", email="vision1@example.com", name="Vision Uno"
    )
    response = client.post(
        "/api/v1/ai/vision/identify",
        files={"file": ("nota.txt", b"esto no es una imagen", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_vision_identify_resolves_against_pokeapi(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-vision-2", email="vision2@example.com", name="Vision Dos"
    )

    async def fake_generate_structured_json(*, parts, response_schema, system_instruction):
        return {
            "pokemon_name": "pikachu",
            "description": "Un ratón eléctrico amarillo.",
            "fun_fact": "Puede generar hasta 100.000 voltios.",
            "confidence": "alta",
        }

    monkeypatch.setattr(
        "app.services.ai.vision.generate_structured_json", fake_generate_structured_json
    )

    async def fake_get_pokemon(self, id_or_name):
        assert str(id_or_name).lower() == "pikachu"
        return _fake_pikachu()

    async def fake_get_type_matchups(self, types):
        assert types == ["electric"]
        return (["water", "flying"], ["ground"])

    monkeypatch.setattr(pokeapi_client_module.PokeAPIClient, "get_pokemon", fake_get_pokemon)
    monkeypatch.setattr(
        pokeapi_client_module.PokeAPIClient, "get_type_matchups", fake_get_type_matchups
    )

    class _FakeStorage:
        async def save_image(self, file, *, subfolder):
            return f"https://fake-storage.example.com/{subfolder}/foto.jpg"

    monkeypatch.setattr(ai_module, "get_storage_service", lambda: _FakeStorage())

    response = client.post(
        "/api/v1/ai/vision/identify",
        files={"file": ("foto.jpg", b"contenido-fake-de-imagen", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pokemon_name"] == "pikachu"
    assert body["fun_fact"]
    assert body["matched_pokemon_id"] == 25
    assert body["types"] == ["electric"]
    assert body["strong_against"] == ["water", "flying"]
    assert body["weak_against"] == ["ground"]
    assert body["image_url"].startswith("https://fake-storage.example.com/")


# --- 2. Chat MCP -------------------------------------------------------------


def test_chat_without_anthropic_key_returns_503(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-chat-1", email="chat1@example.com", name="Chat Uno"
    )
    # En el entorno de tests ANTHROPIC_API_KEY nunca se define (ver conftest.py),
    # así que el endpoint debe negarse explícitamente en vez de intentar llamar
    # a la API real y fallar de forma menos clara.
    assert ai_module.settings.anthropic_api_key == ""
    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "¿qué pokémon tengo?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict):
        self.id, self.name, self.input = id, name, input


class _FakeAnthropicMessages:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self.create_calls: list[dict] = []

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._responses.pop(0)


class _FakeMessage:
    def __init__(self, content: list):
        self.content = content


class _FakeAsyncAnthropic:
    """Reemplaza anthropic.AsyncAnthropic: simula que Claude primero pide la
    tool `get_collection_stats` y en el segundo turno ya responde con texto."""

    _shared_responses: list
    last_instance: "_FakeAsyncAnthropic | None" = None

    def __init__(self, *args, **kwargs):
        self.messages = _FakeAnthropicMessages(_FakeAsyncAnthropic._shared_responses)
        _FakeAsyncAnthropic.last_instance = self


@pytest.mark.asyncio
async def test_run_pokedex_chat_calls_mcp_tool_and_persists_history(monkeypatch):
    from app.db.session import SessionLocal
    from app.models.collection import CollectionEntry
    from app.models.user import User

    db = SessionLocal()
    user = User(
        google_sub="sub-chat-mcp",
        email="chatmcp@example.com",
        name="Chat MCP",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        CollectionEntry(
            user_id=user.id,
            pokemon_id=25,
            pokemon_name="pikachu",
            types=["electric"],
            is_favorite=True,
        )
    )
    db.commit()

    _FakeAsyncAnthropic._shared_responses = [
        _FakeMessage(
            content=[_FakeToolUseBlock(id="tool-1", name="get_collection_stats", input={})]
        ),
        _FakeMessage(
            content=[
                _FakeTextBlock(
                    "Tienes 1 Pokémon en tu colección y 1 es favorito. ¡Vas muy bien!"
                )
            ]
        ),
    ]
    monkeypatch.setattr(chat_module, "AsyncAnthropic", _FakeAsyncAnthropic)
    monkeypatch.setattr(chat_module.settings, "anthropic_api_key", "fake-key-de-prueba")

    saved_histories: list[list[dict]] = []

    async def fake_get_conversation(user_id):
        return []

    async def fake_append_turn(user_id, *, user_message, assistant_reply):
        history = [
            {"role": "user", "content": user_message, "ts": "now"},
            {"role": "assistant", "content": assistant_reply, "ts": "now"},
        ]
        saved_histories.append(history)
        return history

    monkeypatch.setattr(chat_module, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(chat_module, "append_turn", fake_append_turn)

    reply, history = await chat_module.run_pokedex_chat(
        db=db, user=user, user_message="¿cuántos pokémon tengo?"
    )

    assert "1 Pokémon" in reply
    assert history == saved_histories[0]
    # Confirma que el loop de tool_use en chat.py llamó a Claude exactamente dos
    # veces (tool_use -> ejecuta la tool MCP -> le manda el resultado -> texto final).
    assert len(_FakeAsyncAnthropic.last_instance.messages.create_calls) == 2

    db.close()


# --- 3. Insights -------------------------------------------------------------


def test_insights_requires_at_least_one_pokemon(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-insights-1", email="insights1@example.com", name="Insights Uno"
    )
    response = client.get("/api/v1/ai/insights", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422


def test_insights_returns_structured_result(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-insights-2", email="insights2@example.com", name="Insights Dos"
    )
    # Agrega un Pokémon a la colección para poder pedir insights.
    monkeypatch.setattr(
        pokeapi_client_module.PokeAPIClient, "get_pokemon", lambda self, x: _fake_pikachu()
    )

    async def fake_get_pokemon(self, id_or_name):
        return _fake_pikachu()

    monkeypatch.setattr(pokeapi_client_module.PokeAPIClient, "get_pokemon", fake_get_pokemon)

    add_response = client.post(
        "/api/v1/collection",
        json={"pokemon_id": 25},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_response.status_code == 201, add_response.text

    async def fake_generate_structured_json(*, parts, response_schema, system_instruction):
        return {
            "ideal_team": [
                {"pokemon_name": "pikachu", "reason": "Ya lo tienes y es versátil", "already_in_collection": True}
            ],
            "strengths": ["Buen ataque especial eléctrico"],
            "weaknesses": ["Sin cobertura contra tipo tierra"],
            "fun_facts": [{"pokemon_name": "pikachu", "fact": "Es la mascota de la franquicia"}],
            "suggested_additions": [{"pokemon_name": "garchomp", "reason": "Cubre la debilidad a tierra"}],
        }

    monkeypatch.setattr(
        "app.services.ai.insights.generate_structured_json", fake_generate_structured_json
    )

    response = client.get("/api/v1/ai/insights", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ideal_team"][0]["pokemon_name"] == "pikachu"
    assert body["suggested_additions"][0]["pokemon_name"] == "garchomp"
