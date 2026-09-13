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
from app.services.ai import vision as vision_module


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


@pytest.fixture(autouse=True)
def _fake_vision_history(monkeypatch):
    """Ninguno de los tests de este archivo necesita Firestore real — se
    reemplaza por un dict en memoria compartido entre append/get, así los
    tests son deterministas y no dependen de credenciales de GCP."""
    store: dict[int, list[dict]] = {}

    async def fake_append(user_id, entry):
        store.setdefault(user_id, []).append(entry)
        return True

    async def fake_get(user_id):
        return list(reversed(store.get(user_id, [])))

    monkeypatch.setattr(vision_module, "append_vision_entry", fake_append)
    monkeypatch.setattr(ai_module, "get_vision_history", fake_get)
    return store


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


async def _fake_species_info(self, id_or_name):
    return {
        "generation": "generation-i",
        "first_appearance_game": "Pokémon Rojo, Azul y Amarillo",
        "habitat": "forest",
        "habitat_zones": "bosques",
    }


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


def test_vision_identify_resolves_against_pokeapi_and_translates_types(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-vision-2", email="vision2@example.com", name="Vision Dos"
    )

    async def fake_generate_structured_json(*, parts, response_schema, system_instruction):
        return {
            "pokemon_name": "pikachu",
            "description": "Un ratón eléctrico amarillo.",
            "first_appearance_game": "estimado del modelo (se sobreescribe)",
            "habitat_zones": "estimado del modelo (se sobreescribe)",
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
    monkeypatch.setattr(
        pokeapi_client_module.PokeAPIClient, "get_species_info", _fake_species_info
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
    assert body["matched_pokemon_id"] == 25
    assert body["types"] == ["electric"]
    assert body["strong_against"] == ["water", "flying"]
    assert body["weak_against"] == ["ground"]
    assert body["strong_against_es"] == ["agua", "volador"]
    assert body["weak_against_es"] == ["tierra"]
    assert body["first_appearance_game"] == "Pokémon Rojo, Azul y Amarillo"
    assert body["habitat_zones"] == "bosques"
    assert body["height_m"] == 0.4
    assert body["weight_kg"] == 6.0
    assert body["abilities"] == ["static"]
    assert body["image_url"].startswith("https://fake-storage.example.com/")
    assert body["entry_id"]
    assert body["created_at"]
    assert body["history_persisted"] is True

    # Y quedó guardada en el historial (más reciente primero).
    history_response = client.get(
        "/api/v1/ai/vision/history", headers={"Authorization": f"Bearer {token}"}
    )
    assert history_response.status_code == 200, history_response.text
    history_body = history_response.json()
    assert len(history_body) == 1
    assert history_body[0]["pokemon_name"] == "pikachu"


@pytest.mark.asyncio
async def test_get_evolution_info_finds_pre_evolution_and_evolutions(monkeypatch):
    """pichu -> pikachu -> raichu: para pikachu, la pre-evolución es pichu y
    la evolución directa es raichu."""
    fake_chain = {
        "chain": {
            "species": {"name": "pichu"},
            "evolves_to": [
                {
                    "species": {"name": "pikachu"},
                    "evolves_to": [
                        {"species": {"name": "raichu"}, "evolves_to": []}
                    ],
                }
            ],
        }
    }

    client_instance = pokeapi_client_module.PokeAPIClient()

    async def fake_get(self, path, params=None):
        assert path == "/evolution-chain/10/"
        return fake_chain

    monkeypatch.setattr(pokeapi_client_module.PokeAPIClient, "_get", fake_get)

    result = await client_instance.get_evolution_info(
        evolution_chain_url="https://pokeapi.co/api/v2/evolution-chain/10/",
        pokemon_name="pikachu",
    )
    assert result == {"pre_evolution": "pichu", "evolutions": ["raichu"]}

    # La primera etapa de la cadena no tiene pre-evolución.
    result_first_stage = await client_instance.get_evolution_info(
        evolution_chain_url="https://pokeapi.co/api/v2/evolution-chain/10/",
        pokemon_name="pichu",
    )
    assert result_first_stage == {"pre_evolution": None, "evolutions": ["pikachu"]}


def test_vision_history_empty_for_new_user(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-vision-3", email="vision3@example.com", name="Vision Tres"
    )
    response = client.get(
        "/api/v1/ai/vision/history", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == []


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

    def model_dump(self, *, exclude_none=False):
        return {"type": "text", "text": self.text}


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict):
        self.id, self.name, self.input = id, name, input

    def model_dump(self, *, exclude_none=False):
        return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}


class _FakeThinkingBlock:
    """Reproduce el bug real: Claude Sonnet 5 a veces incluye bloques de
    razonamiento junto con el tool_use — un ThinkingBlock real no tiene
    atributo `.id`, así que reconstruir el turno del asistente asumiendo
    solo "text"/"tool_use" reventaba con
    "'ThinkingBlock' object has no attribute 'id'"."""

    type = "thinking"

    def __init__(self, thinking: str, signature: str = "fake-signature"):
        self.thinking, self.signature = thinking, signature

    def model_dump(self, *, exclude_none=False):
        return {"type": "thinking", "thinking": self.thinking, "signature": self.signature}


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

    async def fake_append_turn(user_id, *, user_message, assistant_reply, base_history=None):
        history = [
            {"role": "user", "content": user_message, "ts": "now"},
            {"role": "assistant", "content": assistant_reply, "ts": "now"},
        ]
        saved_histories.append(history)
        return history

    monkeypatch.setattr(chat_module, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(chat_module, "append_turn", fake_append_turn)

    reply, history, persisted = await chat_module.run_pokedex_chat(
        db=db, user=user, user_message="¿cuántos pokémon tengo?"
    )

    assert "1 Pokémon" in reply
    assert history == saved_histories[0]
    assert persisted is True
    # Confirma que el loop de tool_use en chat.py llamó a Claude exactamente dos
    # veces (tool_use -> ejecuta la tool MCP -> le manda el resultado -> texto final).
    assert len(_FakeAsyncAnthropic.last_instance.messages.create_calls) == 2

    db.close()


@pytest.mark.asyncio
async def test_run_pokedex_chat_handles_thinking_blocks(monkeypatch):
    """Regresión del bug real reportado en producción: la respuesta de Claude
    Sonnet 5 traía un bloque `thinking` junto al `tool_use`, y reconstruir el
    turno del asistente a mano (asumiendo solo texto/tool_use) reventaba con
    "'ThinkingBlock' object has no attribute 'id'" — envuelto además en el
    ExceptionGroup de la sesión MCP, así que antes solo se veía el mensaje
    genérico de la TaskGroup."""
    from app.db.session import SessionLocal
    from app.models.collection import CollectionEntry
    from app.models.user import User

    db = SessionLocal()
    user = User(google_sub="sub-chat-thinking", email="thinking@example.com", name="Pensador")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        CollectionEntry(user_id=user.id, pokemon_id=25, pokemon_name="pikachu", types=["electric"])
    )
    db.commit()

    _FakeAsyncAnthropic._shared_responses = [
        _FakeMessage(
            content=[
                _FakeThinkingBlock("Voy a revisar la colección del usuario primero..."),
                _FakeToolUseBlock(id="tool-1", name="get_collection_stats", input={}),
            ]
        ),
        _FakeMessage(content=[_FakeTextBlock("Tienes 1 Pokémon en tu colección.")]),
    ]
    monkeypatch.setattr(chat_module, "AsyncAnthropic", _FakeAsyncAnthropic)
    monkeypatch.setattr(chat_module.settings, "anthropic_api_key", "fake-key-de-prueba")

    async def fake_get_conversation(user_id):
        return []

    async def fake_append_turn(user_id, *, user_message, assistant_reply, base_history=None):
        return [
            {"role": "user", "content": user_message, "ts": "now"},
            {"role": "assistant", "content": assistant_reply, "ts": "now"},
        ]

    monkeypatch.setattr(chat_module, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(chat_module, "append_turn", fake_append_turn)

    reply, history, persisted = await chat_module.run_pokedex_chat(
        db=db, user=user, user_message="¿cuántos pokémon tengo?"
    )

    assert "1 Pokémon" in reply
    assert persisted is True

    db.close()


@pytest.mark.asyncio
async def test_run_pokedex_chat_survives_firestore_write_failure(monkeypatch):
    """Si Claude respondió bien pero Firestore no pudo guardar el turno (el
    bug reportado: 403 de permisos), el chat debe seguir funcionando — nunca
    tirar toda la respuesta por un fallo de persistencia."""
    from app.db.session import SessionLocal
    from app.models.user import User
    from fastapi import HTTPException

    db = SessionLocal()
    user = User(google_sub="sub-chat-resiliente", email="resiliente@example.com", name="R")
    db.add(user)
    db.commit()
    db.refresh(user)

    _FakeAsyncAnthropic._shared_responses = [
        _FakeMessage(content=[_FakeTextBlock("¡Hola! Todo bien por acá.")]),
    ]
    monkeypatch.setattr(chat_module, "AsyncAnthropic", _FakeAsyncAnthropic)
    monkeypatch.setattr(chat_module.settings, "anthropic_api_key", "fake-key-de-prueba")

    async def fake_get_conversation(user_id):
        return []

    async def fake_append_turn_fails(user_id, *, user_message, assistant_reply, base_history=None):
        raise HTTPException(status_code=503, detail="Firestore no disponible: 403 permisos")

    monkeypatch.setattr(chat_module, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(chat_module, "append_turn", fake_append_turn_fails)

    reply, history, persisted = await chat_module.run_pokedex_chat(
        db=db, user=user, user_message="hola"
    )

    assert reply == "¡Hola! Todo bien por acá."
    assert persisted is False
    assert history[-1]["content"] == reply
    assert history[-2]["content"] == "hola"

    db.close()


@pytest.mark.asyncio
async def test_run_pokedex_chat_uses_client_history_when_firestore_has_none(monkeypatch):
    """Si Firestore no tiene nada guardado (por ejemplo, porque el guardado
    llevaba tiempo fallando por el 403 de permisos), pero el frontend manda
    su propia copia local de la conversación (`client_history`), Claude debe
    seguir recibiendo ese contexto — el chat no debe "olvidar" la
    conversación solo porque Firestore está fallando. Además, el guardado
    debe autocurarse: debe escribirse la versión completa (fusionada), no
    solo el turno nuevo."""
    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    user = User(google_sub="sub-chat-contexto", email="contexto@example.com", name="Contexto")
    db.add(user)
    db.commit()
    db.refresh(user)

    _FakeAsyncAnthropic._shared_responses = [
        _FakeMessage(content=[_FakeTextBlock("Sí, ya me habías dicho eso.")]),
    ]
    monkeypatch.setattr(chat_module, "AsyncAnthropic", _FakeAsyncAnthropic)
    monkeypatch.setattr(chat_module.settings, "anthropic_api_key", "fake-key-de-prueba")

    async def fake_get_conversation(user_id):
        return []  # Firestore "vacío" — simula que el guardado ha estado fallando

    append_calls: list[dict] = []

    async def fake_append_turn(user_id, *, user_message, assistant_reply, base_history=None):
        append_calls.append({"base_history": base_history})
        merged = list(base_history or []) + [
            {"role": "user", "content": user_message, "ts": "now"},
            {"role": "assistant", "content": assistant_reply, "ts": "now"},
        ]
        return merged

    monkeypatch.setattr(chat_module, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(chat_module, "append_turn", fake_append_turn)

    client_history = [
        {"role": "user", "content": "Mi Pokémon favorito es Pikachu", "ts": "2026-01-01T00:00:00"},
        {"role": "assistant", "content": "¡Genial, Pikachu es un gran Pokémon!", "ts": "2026-01-01T00:00:01"},
    ]

    reply, history, persisted = await chat_module.run_pokedex_chat(
        db=db, user=user, user_message="¿cuál dije que era mi favorito?", client_history=client_history
    )

    assert reply == "Sí, ya me habías dicho eso."
    assert persisted is True

    # Claude sí recibió el contexto anterior (mandado solo por el frontend).
    sent_messages = _FakeAsyncAnthropic.last_instance.messages.create_calls[0]["messages"]
    assert any("Pikachu" in str(m["content"]) for m in sent_messages)

    # Y el guardado se autocura: escribe la versión completa (2 mensajes
    # previos del cliente + el turno nuevo), no solo el turno nuevo solo.
    assert len(append_calls[0]["base_history"]) == 2
    assert len(history) == 4

    db.close()


def test_root_cause_unwraps_task_group_exception_group():
    """El fix principal: sin esto, cualquier error real (API key inválida,
    fallo de red hacia Anthropic, etc.) dentro del `async with` de MCP se ve
    siempre como el mismo mensaje inútil de anyio. Se debe poder recuperar la
    excepción real de adentro."""
    real_error = ValueError("api key inválida de mentiras")
    wrapped = ExceptionGroup("unhandled errors in a TaskGroup", [real_error])
    assert chat_module._root_cause(wrapped) is real_error
    # Y una excepción normal (no agrupada) se devuelve tal cual.
    assert chat_module._root_cause(real_error) is real_error


# --- 3. Insights -------------------------------------------------------------


def test_insights_requires_at_least_one_pokemon(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-insights-1", email="insights1@example.com", name="Insights Uno"
    )
    response = client.get("/api/v1/ai/insights", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422


def _fake_insights_payload():
    return {
        "team_score": 7,
        "team_score_reason": "Buena cobertura ofensiva pero le falta defensa contra tierra.",
        "ideal_team": [
            {
                "pokemon_name": "pikachu",
                "reason": "Ya lo tienes y es versátil",
                "already_in_collection": True,
                "alternatives": [
                    {"pokemon_name": "raichu", "reason": "Evolución con más ataque especial"}
                ],
            },
            {
                "pokemon_name": "garchomp",
                "reason": "Cubre tu debilidad a tipo tierra",
                "already_in_collection": False,
                "alternatives": [
                    {"pokemon_name": "excadrill", "reason": "Alternativa más rápida"}
                ],
            },
        ],
        "strengths": ["Pikachu te da buen ataque especial eléctrico"],
        "weaknesses": ["Sin cobertura contra tipo tierra"],
        "fun_facts": [{"pokemon_name": "pikachu", "fact": "Es la mascota de la franquicia"}],
    }


def test_insights_returns_structured_result_limited_to_first_six(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-insights-2", email="insights2@example.com", name="Insights Dos"
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
        # El resumen de la colección (primeros 6) va en el prompt del último
        # `Part` de texto — se confirma que la restricción a 6 ya se hizo
        # antes de llegar aquí (esta función solo recibe lo que le pasan).
        assert "pikachu" in parts[0].text
        return _fake_insights_payload()

    monkeypatch.setattr(
        "app.services.ai.insights.generate_structured_json", fake_generate_structured_json
    )

    response = client.get("/api/v1/ai/insights", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["team_score"] == 7
    assert body["analyzed_team"][0]["pokemon_name"] == "pikachu"
    assert body["analyzed_team"][0]["sprite_url"] == "https://example.com/25.png"
    assert body["ideal_team"][0]["pokemon_name"] == "pikachu"
    assert body["ideal_team"][0]["sprite_url"] == "https://example.com/25.png"
    assert body["ideal_team"][1]["already_in_collection"] is False
    assert body["ideal_team"][1]["alternatives"][0]["pokemon_name"] == "excadrill"
