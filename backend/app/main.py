from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.pokeapi_client import get_pokeapi_client

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cierra el cliente httpx de PokéAPI de forma ordenada al apagar la app
    await get_pokeapi_client().aclose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API para PokéDex Manager: autenticación con Google, integración con "
        "PokéAPI y gestión de la colección personal de Pokémon del usuario."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

if settings.storage_backend == "local":
    import os

    os.makedirs(settings.local_upload_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.local_upload_dir), name="uploads")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.get("/", tags=["health"])
def root():
    return {
        "message": "PokéDex Manager API",
        "docs": "/docs",
        "health": "/health",
    }
