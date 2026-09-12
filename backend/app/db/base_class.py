from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa compartida por todos los modelos ORM.

    Vive en su propio módulo (separado de db/base.py) para evitar imports
    circulares: los modelos importan `Base` de aquí, mientras que
    `db/base.py` importa Base + todos los modelos, y ese es el módulo que
    usa Alembic para poblar `Base.metadata`.
    """

    pass
