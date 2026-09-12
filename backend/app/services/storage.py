"""Servicio de almacenamiento de imágenes.

Dos backends intercambiables (ver STORAGE_BACKEND en config):
  - "local": guarda en disco (backend/uploads) — cómodo para desarrollo sin GCP.
  - "gcs":   sube a un bucket de Google Cloud Storage y devuelve una URL pública
             o firmada. Es el backend recomendado para producción (Cloud Run
             tiene filesystem efímero).
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()


class StorageService:
    def __init__(self) -> None:
        self.backend = settings.storage_backend
        if self.backend == "local":
            Path(settings.local_upload_dir).mkdir(parents=True, exist_ok=True)

    async def save_image(self, file: UploadFile, *, subfolder: str = "collection") -> str:
        extension = Path(file.filename or "image.jpg").suffix or ".jpg"
        filename = f"{subfolder}/{uuid.uuid4().hex}{extension}"

        content = await file.read()

        if self.backend == "gcs":
            return self._save_to_gcs(filename, content, file.content_type)
        return self._save_to_local(filename, content)

    def _save_to_local(self, filename: str, content: bytes) -> str:
        full_path = Path(settings.local_upload_dir) / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        # En dev, el backend sirve /uploads como estático (ver main.py)
        return f"/uploads/{filename}"

    def _save_to_gcs(self, filename: str, content: bytes, content_type: str | None) -> str:
        from google.cloud import storage  # import perezoso: solo se necesita si backend=gcs

        client = storage.Client()
        bucket = client.bucket(settings.gcs_bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(content, content_type=content_type or "application/octet-stream")
        return blob.public_url


_storage_singleton: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = StorageService()
    return _storage_singleton
