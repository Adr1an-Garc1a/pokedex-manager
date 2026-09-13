from sqlalchemy.orm import Session

from app.models.collection import CollectionEntry

MAX_TEAM_SIZE = 6


def get_effective_team(db: Session, user_id: int) -> list[CollectionEntry]:
    """Devuelve el equipo "efectivo" de un usuario (hasta `MAX_TEAM_SIZE`),
    usado por Insights para decidir a qué Pokémon analizar.

    - Si el usuario ya eligió un equipo a mano (`PUT /collection/team`, algún
      `is_team_member=True`), esos son su equipo, en el orden en que los
      agregó a su colección.
    - Si no ha elegido ninguno todavía, se cae de vuelta al comportamiento
      original: los primeros `MAX_TEAM_SIZE` Pokémon que agregó (por fecha de
      creación) — así una colección de 6 o menos nunca necesita elegir nada
      a mano, y las cuentas que ya existían antes de esta función siguen
      viendo el mismo análisis de siempre.
    """
    all_entries = (
        db.query(CollectionEntry)
        .filter(CollectionEntry.user_id == user_id)
        .order_by(CollectionEntry.created_at.asc())
        .all()
    )
    chosen = [entry for entry in all_entries if entry.is_team_member]
    if chosen:
        return chosen[:MAX_TEAM_SIZE]
    return all_entries[:MAX_TEAM_SIZE]
