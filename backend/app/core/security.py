"""Seguridad: verificación de Google ID Token y emisión/validación de JWT propio."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
_bearer_scheme = HTTPBearer(auto_error=False)

_google_request = google_requests.Request()


class GoogleTokenPayload:
    def __init__(self, sub: str, email: str, name: str, picture: Optional[str]):
        self.sub = sub
        self.email = email
        self.name = name
        self.picture = picture


def verify_google_id_token(token: str) -> GoogleTokenPayload:
    """Valida un id_token de Google Sign-In contra los certificados públicos de Google.

    Lanza HTTPException(401) si el token es inválido, expiró o no coincide con
    nuestro Client ID (protección contra "confused deputy").
    """
    try:
        info: dict[str, Any] = google_id_token.verify_oauth2_token(
            token, _google_request, audience=settings.google_client_id
        )
    except ValueError as exc:  # token inválido / expirado / audiencia incorrecta
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de Google inválido: {exc}",
        ) from exc

    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Emisor de token no confiable")

    return GoogleTokenPayload(
        sub=info["sub"],
        email=info["email"],
        name=info.get("name", info["email"]),
        picture=info.get("picture"),
    )


def create_access_token(*, user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
