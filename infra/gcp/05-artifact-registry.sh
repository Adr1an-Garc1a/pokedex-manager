#!/usr/bin/env bash
# =============================================================================
# 05-artifact-registry.sh — Crea el repositorio Docker en Artifact Registry
# donde se publican las imágenes del backend y frontend.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

if gcloud artifacts repositories describe "${ARTIFACT_REPO}" \
    --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo ">> El repositorio ${ARTIFACT_REPO} ya existe."
else
  echo ">> Creando repositorio Artifact Registry (Docker): ${ARTIFACT_REPO}"
  gcloud artifacts repositories create "${ARTIFACT_REPO}" \
    --project="${PROJECT_ID}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Imágenes de PokéDex Manager (backend/frontend)"
fi

echo ">> Configurando autenticación de Docker con Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo ">> Listo. Registry URL base:"
echo "   ${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}"
