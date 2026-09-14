#!/usr/bin/env bash
# =============================================================================
# ci-deploy-backend.sh — Ejecutado por Cloud Build (ver ../../cloudbuild.yaml),
# NO manualmente. Las variables llegan como env vars desde el step de Cloud
# Build (PROJECT_ID, REGION, BACKEND_SERVICE, IMAGE, SQL_INSTANCE,
# RUNTIME_SA_EMAIL, GCS_BUCKET, SECRET_*, VERTEX_LOCATION, GEMINI_MODEL,
# ANTHROPIC_MODEL).
# =============================================================================
set -euo pipefail
source "$(dirname "$0")/lib-service-urls.sh"

CONNECTION_NAME="$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" --format='value(connectionName)')"


FRONTEND_URLS="$(get_all_service_urls "${FRONTEND_SERVICE}" "${PROJECT_ID}" "${REGION}")"
CORS_ORIGINS_VALUE="${FRONTEND_URLS:-*}"

SECRETS_VALUE="DATABASE_URL=${SECRET_DB_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT_KEY}:latest,GOOGLE_CLIENT_ID=${SECRET_GOOGLE_CLIENT_ID}:latest"
if gcloud secrets describe "${SECRET_ANTHROPIC_API_KEY}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  SECRETS_VALUE="${SECRETS_VALUE},ANTHROPIC_API_KEY=${SECRET_ANTHROPIC_API_KEY}:latest"
fi

gcloud run deploy "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${RUNTIME_SA_EMAIL}" \
  --add-cloudsql-instances="${CONNECTION_NAME}" \
  --set-secrets="${SECRETS_VALUE}" \
  --set-env-vars="^;^STORAGE_BACKEND=gcs;GCS_BUCKET_NAME=${GCS_BUCKET};ENVIRONMENT=production;CORS_ORIGINS=${CORS_ORIGINS_VALUE};GOOGLE_CLOUD_PROJECT=${PROJECT_ID};VERTEX_LOCATION=${VERTEX_LOCATION};GEMINI_MODEL=${GEMINI_MODEL};ANTHROPIC_MODEL=${ANTHROPIC_MODEL}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=512Mi \
  --cpu=1 \
  --quiet

echo ">> Backend desplegado por CI/CD. CORS_ORIGINS configurado con: ${CORS_ORIGINS_VALUE}"
echo ">> URLs conocidas del backend: $(get_all_service_urls "${BACKEND_SERVICE}" "${PROJECT_ID}" "${REGION}")"
