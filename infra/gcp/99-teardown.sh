#!/usr/bin/env bash
# =============================================================================
# 99-teardown.sh — Elimina TODOS los recursos creados por estos scripts.
# Úsalo para no dejar nada facturando después de la evaluación.
#
# Pide confirmación explícita antes de borrar nada.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

echo "Esto eliminará en el proyecto ${PROJECT_ID}:"
echo "  - Cloud Run:   ${BACKEND_SERVICE}, ${FRONTEND_SERVICE}"
echo "  - Cloud SQL:   ${SQL_INSTANCE} (¡borra los datos!)"
echo "  - GCS bucket:  gs://${GCS_BUCKET} (¡borra las imágenes!)"
echo "  - Artifact Registry repo: ${ARTIFACT_REPO}"
echo "  - Secrets:     ${SECRET_DB_URL}, ${SECRET_JWT_KEY}, ${SECRET_GOOGLE_CLIENT_ID}"
echo "  - Service account: ${RUNTIME_SA_EMAIL}"
read -r -p "¿Confirmas? Escribe 'borrar todo' para continuar: " CONFIRM
if [[ "${CONFIRM}" != "borrar todo" ]]; then
  echo "Cancelado."
  exit 0
fi

gcloud run services delete "${BACKEND_SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" --quiet || true
gcloud run services delete "${FRONTEND_SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" --quiet || true

gcloud sql instances delete "${SQL_INSTANCE}" --project="${PROJECT_ID}" --quiet || true

gcloud storage rm --recursive "gs://${GCS_BUCKET}" --quiet || true

gcloud artifacts repositories delete "${ARTIFACT_REPO}" --project="${PROJECT_ID}" --location="${REGION}" --quiet || true

for secret in "${SECRET_DB_URL}" "${SECRET_JWT_KEY}" "${SECRET_GOOGLE_CLIENT_ID}"; do
  gcloud secrets delete "${secret}" --project="${PROJECT_ID}" --quiet || true
done

gcloud iam service-accounts delete "${RUNTIME_SA_EMAIL}" --project="${PROJECT_ID}" --quiet || true

rm -f .last-backend-image .last-frontend-image .last-backend-url .last-frontend-url

echo ">> Teardown completado."
