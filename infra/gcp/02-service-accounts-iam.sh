#!/usr/bin/env bash
# =============================================================================
# 02-service-accounts-iam.sh — Crea la service account de runtime que usarán
# los servicios de Cloud Run (backend y frontend) y le otorga permisos
# mínimos (principio de menor privilegio).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

echo ">> Creando service account de runtime: ${RUNTIME_SA_EMAIL}"

if ! gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${RUNTIME_SA_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="PokéDex Manager - runtime (Cloud Run)"
else
  echo "   Ya existe, se omite creación."
fi

echo ">> Asignando roles IAM mínimos necesarios..."

# Cloud SQL: conectarse vía Cloud SQL Auth Proxy / connector
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/cloudsql.client" --quiet

# Cloud Storage: leer/escribir imágenes en el bucket del proyecto
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/storage.objectAdmin" --quiet

# Secret Manager: leer secretos (DATABASE_URL, JWT key, etc.)
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" --quiet

# Vertex AI: invocar modelos (Fase 2 / bonus) — no se usa en el core, pero se
# deja listo para no reconfigurar IAM cuando se agregue.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/aiplatform.user" --quiet

echo ">> Listo. La service account ${RUNTIME_SA_EMAIL} tiene los permisos necesarios."
