#!/usr/bin/env bash
# =============================================================================
# 08-deploy-backend.sh — Despliega el backend (FastAPI) en Cloud Run,
# conectado a Cloud SQL vía Unix socket y con secretos inyectados desde
# Secret Manager (nunca variables de entorno en texto plano).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

if [[ ! -f .last-backend-image ]]; then
  echo "ERROR: no se encontró .last-backend-image. Corre primero ./07-build-push.sh" >&2
  exit 1
fi
BACKEND_IMAGE="$(cat .last-backend-image)"

CONNECTION_NAME="$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" --format="value(connectionName)")"

echo ">> Desplegando backend en Cloud Run: ${BACKEND_SERVICE}"
gcloud run deploy "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${BACKEND_IMAGE}" \
  --service-account="${RUNTIME_SA_EMAIL}" \
  --add-cloudsql-instances="${CONNECTION_NAME}" \
  --set-secrets="DATABASE_URL=${SECRET_DB_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT_KEY}:latest,GOOGLE_CLIENT_ID=${SECRET_GOOGLE_CLIENT_ID}:latest" \
  --set-env-vars="STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=${GCS_BUCKET},ENVIRONMENT=production,CORS_ORIGINS=${FRONTEND_URL:-*}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=512Mi \
  --cpu=1

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)")"

echo ""
echo ">> Backend desplegado: ${BACKEND_URL}"
echo "   Swagger UI: ${BACKEND_URL}/docs"
echo "   Health:     ${BACKEND_URL}/health"
echo ""
echo ">> Guarda esta URL — la necesitas para construir el frontend (VITE_API_BASE_URL)"
echo "   y para configurar los 'Authorized redirect URIs' de Google OAuth."
echo "${BACKEND_URL}" > .last-backend-url
