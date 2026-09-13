"""Tests del CRUD de la colección y de la elección de equipo
(PUT /collection/team) — ver app/services/team.py para la lógica de
"equipo efectivo" que usa Insights.
"""
from __future__ import annotations

import pytest

from app.api.v1 import auth as auth_module
from app.schemas.pokemon import PokemonDetail, PokemonStat
from app.services import pokeapi_client as pokeapi_client_module


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


def _fake_pokemon(pokemon_id: int) -> PokemonDetail:
    return PokemonDetail(
        id=pokemon_id,
        name=f"pokemon-{pokemon_id}",
        sprite_url=f"https://example.com/{pokemon_id}.png",
        types=["normal"],
        height=1,
        weight=1,
        stats=[PokemonStat(name="hp", base_stat=50)],
    )


def _add_entries(client, token: str, monkeypatch, count: int) -> list[int]:
    async def fake_get_pokemon(self, id_or_name):
        # El id que llega es siempre un entero incremental en estos tests.
        return _fake_pokemon(int(id_or_name) if isinstance(id_or_name, (int, str)) else 1)

    monkeypatch.setattr(pokeapi_client_module.PokeAPIClient, "get_pokemon", fake_get_pokemon)

    ids = []
    for i in range(1, count + 1):
        response = client.post(
            "/api/v1/collection",
            json={"pokemon_id": i},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return ids


def test_new_entries_default_to_not_in_team(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-team-1", email="team1@example.com", name="Team Uno"
    )
    ids = _add_entries(client, token, monkeypatch, count=2)

    response = client.get("/api/v1/collection", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert all(entry["is_team_member"] is False for entry in response.json())
    assert {e["id"] for e in response.json()} == set(ids)


def test_update_team_sets_flags_only_on_chosen_entries(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-team-2", email="team2@example.com", name="Team Dos"
    )
    ids = _add_entries(client, token, monkeypatch, count=8)
    chosen = ids[:3]

    response = client.put(
        "/api/v1/collection/team",
        json={"entry_ids": chosen},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    returned_ids = {e["id"] for e in response.json()}
    assert returned_ids == set(chosen)

    all_entries = client.get(
        "/api/v1/collection", headers={"Authorization": f"Bearer {token}"}
    ).json()
    team_ids = {e["id"] for e in all_entries if e["is_team_member"]}
    assert team_ids == set(chosen)


def test_update_team_rejects_more_than_six(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-team-3", email="team3@example.com", name="Team Tres"
    )
    ids = _add_entries(client, token, monkeypatch, count=8)

    response = client.put(
        "/api/v1/collection/team",
        json={"entry_ids": ids[:7]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_update_team_rejects_entries_not_owned_by_user(client, monkeypatch):
    token_a = _register_and_get_token(
        client, monkeypatch, sub="sub-team-4a", email="team4a@example.com", name="Team Cuatro A"
    )
    token_b = _register_and_get_token(
        client, monkeypatch, sub="sub-team-4b", email="team4b@example.com", name="Team Cuatro B"
    )
    ids_a = _add_entries(client, token_a, monkeypatch, count=1)

    response = client.put(
        "/api/v1/collection/team",
        json={"entry_ids": ids_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404


def test_update_team_with_empty_list_clears_the_team(client, monkeypatch):
    token = _register_and_get_token(
        client, monkeypatch, sub="sub-team-5", email="team5@example.com", name="Team Cinco"
    )
    ids = _add_entries(client, token, monkeypatch, count=8)
    client.put(
        "/api/v1/collection/team",
        json={"entry_ids": ids[:3]},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.put(
        "/api/v1/collection/team",
        json={"entry_ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []

    all_entries = client.get(
        "/api/v1/collection", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert all(entry["is_team_member"] is False for entry in all_entries)
