from fastapi import APIRouter

from app.api.v1 import ai, auth, collection, pokemon

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(pokemon.router)
api_router.include_router(collection.router)
api_router.include_router(ai.router)
