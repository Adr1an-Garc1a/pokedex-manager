"""Punto único de importación de Base + todos los modelos ORM.

Alembic (migrations/env.py) importa `Base` desde este módulo para que
`Base.metadata` incluya todas las tablas. El resto de la app (modelos
individuales) importa `Base` desde `app.db.base_class` para evitar imports
circulares.
"""
from app.db.base_class import Base  # noqa: F401

from app.models.user import User  # noqa: E402,F401
from app.models.collection import CollectionEntry  # noqa: E402,F401
