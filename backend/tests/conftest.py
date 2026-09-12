import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

# Base de datos de prueba limpia en cada corrida de pytest.
_TEST_DB_PATH = Path(__file__).resolve().parent.parent / "test.db"
if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app

# Los tests de auth/colección sí leen y escriben en la base (a diferencia de
# los de PokéAPI, que están mockeados), así que el esquema debe existir.
Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
