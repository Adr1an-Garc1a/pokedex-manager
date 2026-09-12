from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.collection import CollectionEntry
from app.models.user import User
from app.schemas.collection import (
    CollectionEntryCreate,
    CollectionEntryRead,
    CollectionEntryUpdate,
    CollectionStats,
)
from app.services.pokeapi_client import get_pokeapi_client
from app.services.storage import get_storage_service

router = APIRouter(prefix="/collection", tags=["collection"])


def _get_owned_entry(db: Session, entry_id: int, user: User) -> CollectionEntry:
    entry = db.get(CollectionEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entrada de colección no encontrada")
    return entry


@router.get("", response_model=list[CollectionEntryRead])
def list_my_collection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(CollectionEntry)
        .filter(CollectionEntry.user_id == current_user.id)
        .order_by(CollectionEntry.created_at.desc())
        .all()
    )


@router.get("/stats", response_model=CollectionStats)
def get_collection_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = (
        db.query(CollectionEntry).filter(CollectionEntry.user_id == current_user.id).all()
    )
    type_counter: Counter = Counter()
    for entry in entries:
        type_counter.update(entry.types or [])

    return CollectionStats(
        total=len(entries),
        by_type=dict(type_counter),
        favorites=sum(1 for e in entries if e.is_favorite),
    )


@router.post("", response_model=CollectionEntryRead, status_code=201)
async def add_to_collection(
    payload: CollectionEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Se valida contra PokéAPI y se desnormalizan nombre/sprite/tipos (ver
    # docs/POKEAPI_DECISION.md) para que la colección sobreviva a caídas o
    # cambios de la fuente externa.
    client = get_pokeapi_client()
    pokemon = await client.get_pokemon(payload.pokemon_id)

    entry = CollectionEntry(
        user_id=current_user.id,
        pokemon_id=pokemon.id,
        pokemon_name=pokemon.name,
        sprite_url=pokemon.sprite_url,
        types=pokemon.types,
        nickname=payload.nickname,
        level=payload.level,
        notes=payload.notes,
        is_favorite=payload.is_favorite,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/{entry_id}", response_model=CollectionEntryRead)
def update_collection_entry(
    entry_id: int,
    payload: CollectionEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = _get_owned_entry(db, entry_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_collection_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = _get_owned_entry(db, entry_id, current_user)
    db.delete(entry)
    db.commit()


@router.post("/{entry_id}/image", response_model=CollectionEntryRead)
async def upload_entry_image(
    entry_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = _get_owned_entry(db, entry_id, current_user)
    storage = get_storage_service()
    url = await storage.save_image(file, subfolder=f"collection/{current_user.id}")
    entry.custom_image_url = url
    db.commit()
    db.refresh(entry)
    return entry
