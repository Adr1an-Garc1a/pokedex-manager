#!/usr/bin/env bash
# =============================================================================
# 10-setup-ci-cd-iam.sh — Otorga a la service account de Cloud Build los
# permisos necesarios para construir imágenes y desplegar a Cloud Run
# automáticamente en cada build disparado por push a GitHub.
#
# Correr UNA sola vez, después de haber corrido 01-09 al menos una vez
# (necesita que la runtime SA ya exista). Ver docs/CI_CD.md para el resto
# del setup (conectar el repo de GitHub y crear el trigger).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo ">> Otorgando permisos a la service account de Cloud Build: ${CLOUDBUILD_SA}"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/run.admin" --quiet

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/artifactregistry.writer" --quiet

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/secretmanager.secretAccessor" --quiet

# Permite a Cloud Build "actuar como" la service account de runtime al
# desplegar (necesario para el flag --service-account de gcloud run deploy).
gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/iam.serviceAccountUser" --quiet

echo ""
echo ">> Listo. Cloud Build (${CLOUDBUILD_SA}) ya puede construir y desplegar."
echo "   Siguiente paso: conectar el repo de GitHub y crear el trigger — ver docs/CI_CD.md"
