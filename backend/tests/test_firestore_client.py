"""Tests unitarios del cliente de Firestore para el chat (sin FastAPI de por
medio) — en particular, la resiliencia de `create_thread` ante fallos de
Firestore (el bug real reportado: "Iniciar nueva conversación" parecía no
hacer nada cuando Firestore estaba fallando)."""
from __future__ import annotations

import pytest

from app.services import firestore_client


def _boom():
    raise RuntimeError("403 Missing or insufficient permissions (simulado)")


@pytest.mark.asyncio
async def test_create_thread_never_raises_even_if_firestore_fails(monkeypatch):
    """Una conversación recién creada no tiene ningún mensaje que perder —
    así que aunque Firestore esté fallando, `create_thread` debe devolver
    igual un thread_id utilizable (la conversación se termina de crear sola
    en Firestore la primera vez que se le manda un mensaje, vía
    `append_turn`). Antes esto lanzaba HTTPException(503), y como el
    frontend no mostraba ningún error para esta acción en particular, el
    botón "Iniciar nueva conversación" parecía no hacer nada."""
    monkeypatch.setattr(firestore_client, "_get_client", lambda: _boom())

    thread = await firestore_client.create_thread(user_id=999)

    assert thread["id"]
    assert thread["title"] == "Nueva conversación"
    assert thread["message_count"] == 0


class _FakeSnapshot:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return self._data


class _FakeDocRef:
    def __init__(self, store: dict):
        self._store = store

    async def get(self):
        return _FakeSnapshot(self._store.get("doc"))

    async def set(self, data):
        self._store["doc"] = data


class _FakeCollection:
    def __init__(self, store: dict):
        self._store = store

    def document(self, doc_id):
        return _FakeDocRef(self._store)


class _FakeClient:
    def __init__(self, store: dict):
        self._store = store

    def collection(self, name):
        return _FakeCollection(self._store)


@pytest.mark.asyncio
async def test_append_turn_replaces_stuck_default_title(monkeypatch):
    """Bug real corregido: una conversación creada por 'Iniciar nueva
    conversación' arranca con el título genérico DEFAULT_THREAD_TITLE
    ('Nueva conversación'). Antes, `existing.get('title') or _make_title(...)`
    nunca reemplazaba ese título porque una cadena no vacía es "truthy" — se
    quedaba pegado para siempre. Ahora, sin pasar un `title` explícito
    (simulando que la generación por IA falló o no aplicaba), el genérico SÍ
    se reemplaza por el recorte simple del mensaje."""
    store: dict = {"doc": {"threads": {"t1": {"title": firestore_client.DEFAULT_THREAD_TITLE, "messages": []}}}}
    monkeypatch.setattr(firestore_client, "_get_client", lambda: _FakeClient(store))

    history = await firestore_client.append_turn(
        user_id=1,
        thread_id="t1",
        user_message="¿Qué tan fuerte es mi Gyarados?",
        assistant_reply="¡Muy fuerte!",
    )
    assert len(history) == 2

    threads = await firestore_client.list_threads(user_id=1)
    assert threads[0]["title"] == "¿Qué tan fuerte es mi Gyarados?"


@pytest.mark.asyncio
async def test_append_turn_explicit_title_wins_over_placeholder(monkeypatch):
    """Cuando chat.py SÍ logró generar un título con IA, ese es el que se
    guarda — no el recorte simple de respaldo."""
    store: dict = {"doc": {"threads": {"t1": {"title": firestore_client.DEFAULT_THREAD_TITLE, "messages": []}}}}
    monkeypatch.setattr(firestore_client, "_get_client", lambda: _FakeClient(store))

    await firestore_client.append_turn(
        user_id=1,
        thread_id="t1",
        user_message="¿Qué tan fuerte es mi Gyarados?",
        assistant_reply="¡Muy fuerte!",
        title="Fuerza de Gyarados",
    )

    threads = await firestore_client.list_threads(user_id=1)
    assert threads[0]["title"] == "Fuerza de Gyarados"


@pytest.mark.asyncio
async def test_append_turn_preserves_existing_real_title(monkeypatch):
    """Una conversación que YA tiene un título real (no el genérico) no se le
    debe cambiar en mensajes posteriores solo porque no se le pasó `title`."""
    store: dict = {"doc": {"threads": {"t1": {"title": "Mi equipo ideal", "messages": []}}}}
    monkeypatch.setattr(firestore_client, "_get_client", lambda: _FakeClient(store))

    await firestore_client.append_turn(
        user_id=1, thread_id="t1", user_message="otra pregunta", assistant_reply="otra respuesta"
    )

    threads = await firestore_client.list_threads(user_id=1)
    assert threads[0]["title"] == "Mi equipo ideal"


@pytest.mark.asyncio
async def test_create_thread_persists_normally_when_firestore_works(monkeypatch):
    """Camino feliz: sin fallos, la conversación sí queda guardada y luego
    aparece en list_threads."""
    store: dict = {}
    monkeypatch.setattr(firestore_client, "_get_client", lambda: _FakeClient(store))

    thread = await firestore_client.create_thread(user_id=123)
    assert thread["message_count"] == 0

    threads = await firestore_client.list_threads(user_id=123)
    assert [t["id"] for t in threads] == [thread["id"]]
