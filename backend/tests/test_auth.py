"""Tests del flujo de login/registro con Google.

`verify_google_id_token` se monkeypatch-ea para no depender de la red real
de Google (mismo criterio que tests/test_pokemon.py con PokéAPI).
"""
from app.api.v1 import auth as auth_module


class _FakeGoogleUser:
    def __init__(self, sub: str, email: str, name: str, picture: str | None = None):
        self.sub = sub
        self.email = email
        self.name = name
        self.picture = picture


def test_login_with_unregistered_google_account_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "verify_google_id_token",
        lambda token: _FakeGoogleUser("google-sub-nuevo", "nuevo@example.com", "Nuevo Usuario"),
    )

    response = client.post("/api/v1/auth/google/login", json={"id_token": "fake-token"})

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "user_not_registered"
    assert detail["profile"]["email"] == "nuevo@example.com"
    assert detail["profile"]["name"] == "Nuevo Usuario"


def test_register_then_login_and_me(client, monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "verify_google_id_token",
        lambda token: _FakeGoogleUser("google-sub-ana", "ana@example.com", "Ana Google"),
    )

    # 1. Registro: el nombre editado por el usuario prevalece sobre el de Google
    register_response = client.post(
        "/api/v1/auth/google/register",
        json={"id_token": "fake-token", "name": "Ana (editado)"},
    )
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["user"]["name"] == "Ana (editado)"
    assert body["user"]["email"] == "ana@example.com"
    token = body["access_token"]

    # 2. Registrar la misma cuenta dos veces debe fallar (409)
    duplicate_response = client.post(
        "/api/v1/auth/google/register",
        json={"id_token": "fake-token", "name": "Ana"},
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"]["code"] == "user_already_registered"

    # 3. Ahora sí puede iniciar sesión (ya está registrada)
    login_response = client.post("/api/v1/auth/google/login", json={"id_token": "fake-token"})
    assert login_response.status_code == 200
    assert login_response.json()["user"]["email"] == "ana@example.com"

    # 4. El token del registro funciona contra /auth/me
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "ana@example.com"


def test_login_without_registering_never_creates_user(client, monkeypatch):
    """Refuerza el requisito explícito: login NUNCA debe dar de alta a nadie."""
    monkeypatch.setattr(
        auth_module,
        "verify_google_id_token",
        lambda token: _FakeGoogleUser("google-sub-fantasma", "fantasma@example.com", "Fantasma"),
    )

    for _ in range(3):
        response = client.post("/api/v1/auth/google/login", json={"id_token": "fake-token"})
        assert response.status_code == 404
