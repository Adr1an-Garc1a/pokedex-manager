#!/usr/bin/env bash
# =============================================================================
# 04-storage-bucket.sh — Crea el bucket de Cloud Storage donde se guardan las
# imágenes/capturas subidas por los usuarios (custom_image_url).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

if gsutil ls -b "gs://${GCS_BUCKET}" >/dev/null 2>&1; then
  echo ">> El bucket gs://${GCS_BUCKET} ya existe, se omite creación."
else
  echo ">> Creando bucket gs://${GCS_BUCKET} en ${REGION}..."
  gcloud storage buckets create "gs://${GCS_BUCKET}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi

echo ">> Configurando CORS para que el frontend pueda subir/mostrar imágenes..."
cat > /tmp/pokedex-cors.json <<EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "POST", "PUT"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF
gcloud storage buckets update "gs://${GCS_BUCKET}" --cors-file=/tmp/pokedex-cors.json
rm -f /tmp/pokedex-cors.json

echo ">> Bucket listo: gs://${GCS_BUCKET}"
echo "   El backend sube objetos y expone su URL pública (o firmada, si se endurece"
echo "   la seguridad más adelante) — ver app/services/storage.py (backend=gcs)."
