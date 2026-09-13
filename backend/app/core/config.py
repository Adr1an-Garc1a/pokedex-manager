"""Configuración central de la aplicación (Pydantic Settings).

Todas las variables se leen de entorno / .env. Nunca se hardcodean secretos.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "PokéDex Manager API"
    environment: Literal["development", "production", "test"] = "development"
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg://pokedex:pokedex_dev_password@localhost:5432/pokedex_manager"
    )

    # --- Auth ---
    google_client_id: str = "REPLACE_ME.apps.googleusercontent.com"
    jwt_secret_key: str = "change_me_dev_only_change_me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # --- PokéAPI (fuente externa, solo lectura) ---
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"
    pokeapi_cache_ttl_seconds: int = 3600

    # --- Storage ---
    storage_backend: Literal["local", "gcs"] = "local"
    gcs_bucket_name: str = ""
    local_upload_dir: str = "uploads"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- IA (funcionalidades bonus) ---
    # Vertex AI (Gemini) — usado por: identificación de Pokémon por foto (Vision)
    # e insights de colección. Si google_cloud_project queda vacío, el SDK
    # intenta resolverlo solo de las credenciales por defecto (ADC) — en Cloud
    # Run normalmente basta, pero se puede fijar explícito si hace falta.
    google_cloud_project: str = ""
    vertex_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-flash"

    # Anthropic (Claude) — usado por: chat MCP sobre la colección. Requiere una
    # API key propia de https://console.anthropic.com (no es parte de GCP, ver
    # docs/BONUS_FEATURES.md). Si queda vacía, el endpoint de chat responde 503
    # en vez de fallar el arranque del backend.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
