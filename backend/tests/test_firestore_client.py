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


@pytest.mark.asyncio
async def test_create_thread_persists_normally_when_firestore_works(monkeypatch):
    """Camino feliz: sin fallos, la conversación sí queda guardada y luego
    aparece en list_threads."""
    store: dict[str, dict] = {}

    class _FakeSnapshot:
        def __init__(self, data):
            self._data = data

        @property
        def exists(self):
            return self._data is not None

        def to_dict(self):
            return self._data

    class _FakeDocRef:
        async def get(self):
            return _FakeSnapshot(store.get("doc"))

        async def set(self, data):
            store["doc"] = data

    class _FakeCollection:
        def document(self, doc_id):
            return _FakeDocRef()

    class _FakeClient:
        def collection(self, name):
            return _FakeCollection()

    monkeypatch.setattr(firestore_client, "_get_client", lambda: _FakeClient())

    thread = await firestore_client.create_thread(user_id=123)
    assert thread["message_count"] == 0

    threads = await firestore_client.list_threads(user_id=123)
    assert [t["id"] for t in threads] == [thread["id"]]
