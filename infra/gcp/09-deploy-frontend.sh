#!/usr/bin/env bash
# =============================================================================
# 09-deploy-frontend.sh — Despliega el frontend (React build servido por
# nginx) en Cloud Run. Debe correrse DESPUÉS de 08-deploy-backend.sh, y la
# imagen del frontend debe haberse construido con el BACKEND_URL correcto
# (ver 07-build-push.sh).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

if [[ ! -f .last-frontend-image ]]; then
  echo "ERROR: no se encontró .last-frontend-image. Corre primero ./07-build-push.sh" >&2
  exit 1
fi
FRONTEND_IMAGE="$(cat .last-frontend-image)"

echo ">> Desplegando frontend en Cloud Run: ${FRONTEND_SERVICE}"
gcloud run deploy "${FRONTEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${FRONTEND_IMAGE}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=256Mi \
  --cpu=1

FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)")"

echo ""
echo ">> Frontend desplegado: ${FRONTEND_URL}"
echo ""
echo ">> IMPORTANTE — pasos manuales que quedan:"
echo "   1. En Google Cloud Console > APIs & Services > Credentials, agrega"
echo "      '${FRONTEND_URL}' a los 'Authorized JavaScript origins' de tu OAuth Client."
echo "   2. Si CORS_ORIGINS del backend seguía en '*', vuelve a correr"
echo "      08-deploy-backend.sh con: export FRONTEND_URL=${FRONTEND_URL}"
echo "${FRONTEND_URL}" > .last-frontend-url
