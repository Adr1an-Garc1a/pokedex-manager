#!/usr/bin/env bash
# =============================================================================
# ci-deploy-frontend.sh — Ejecutado por Cloud Build (ver ../../cloudbuild.yaml),
# NO manualmente. Variables como env vars del step: PROJECT_ID, REGION,
# FRONTEND_SERVICE, IMAGE.
# =============================================================================
set -euo pipefail

gcloud run deploy "${FRONTEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=256Mi \
  --cpu=1 \
  --quiet

echo ">> Frontend desplegado por CI/CD: $(gcloud run services describe "${FRONTEND_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
