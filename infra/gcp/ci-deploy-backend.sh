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

# IMPORTANTE: `gcloud run deploy --set-env-vars` REEMPLAZA TODAS las
# variables de entorno del servicio, no es aditivo. Si CORS_ORIGINS no se
# incluye aquí explícitamente, cada deploy de CI/CD la borraría y el
# backend caería al default del código (localhost:5173), rompiendo CORS
# para el frontend real desplegado en Cloud Run. Por eso se auto-detecta
# la URL del frontend ya desplegado en cada build, en vez de depender de
# que alguien la recuerde.
FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)"
CORS_ORIGINS_VALUE="${FRONTEND_URL:-*}"

gcloud run deploy "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${RUNTIME_SA_EMAIL}" \
  --add-cloudsql-instances="${CONNECTION_NAME}" \
  --set-secrets="DATABASE_URL=${SECRET_DB_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT_KEY}:latest,GOOGLE_CLIENT_ID=${SECRET_GOOGLE_CLIENT_ID}:latest" \
  --set-env-vars="STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=${GCS_BUCKET},ENVIRONMENT=production,CORS_ORIGINS=${CORS_ORIGINS_VALUE}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=512Mi \
  --cpu=1 \
  --quiet

echo ">> Backend desplegado por CI/CD: $(gcloud run services describe "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
