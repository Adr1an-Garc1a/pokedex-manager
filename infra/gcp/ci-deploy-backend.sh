#!/usr/bin/env bash
# =============================================================================
# ci-deploy-backend.sh — Ejecutado por Cloud Build (ver ../../cloudbuild.yaml),
# NO manualmente. Las variables llegan como env vars desde el step de Cloud
# Build (PROJECT_ID, REGION, BACKEND_SERVICE, IMAGE, SQL_INSTANCE,
# RUNTIME_SA_EMAIL, GCS_BUCKET, SECRET_*).
# =============================================================================
set -euo pipefail

CONNECTION_NAME="$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" --format='value(connectionName)')"

gcloud run deploy "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${RUNTIME_SA_EMAIL}" \
  --add-cloudsql-instances="${CONNECTION_NAME}" \
  --set-secrets="DATABASE_URL=${SECRET_DB_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT_KEY}:latest,GOOGLE_CLIENT_ID=${SECRET_GOOGLE_CLIENT_ID}:latest" \
  --set-env-vars="STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=${GCS_BUCKET},ENVIRONMENT=production" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=512Mi \
  --cpu=1 \
  --quiet

echo ">> Backend desplegado por CI/CD: $(gcloud run services describe "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
