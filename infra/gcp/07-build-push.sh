#!/usr/bin/env bash
# =============================================================================
# 07-build-push.sh — Construye las imágenes Docker de backend y frontend con
# Cloud Build y las publica en Artifact Registry. No requiere Docker local.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

REPO_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}"
BACKEND_IMAGE="${REPO_URL}/${BACKEND_SERVICE}:$(date +%Y%m%d%H%M%S)"
FRONTEND_IMAGE="${REPO_URL}/${FRONTEND_SERVICE}:$(date +%Y%m%d%H%M%S)"

REPO_ROOT="$(cd ../../ && pwd)"

echo ">> Construyendo y publicando imagen del backend con Cloud Build..."
gcloud builds submit "${REPO_ROOT}/backend" \
  --project="${PROJECT_ID}" \
  --tag="${BACKEND_IMAGE}"

echo "${BACKEND_IMAGE}" > .last-backend-image
echo "   Imagen backend: ${BACKEND_IMAGE}"

echo ""
echo ">> Construyendo y publicando imagen del frontend con Cloud Build..."

BACKEND_URL="${BACKEND_URL:-https://REEMPLAZA-DESPUES-DE-DESPLEGAR-BACKEND}"

CLOUDBUILD_CONFIG="$(mktemp /tmp/pokedex-frontend-cloudbuild.XXXXXX.yaml)"
cat > "${CLOUDBUILD_CONFIG}" <<EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - build
      - --build-arg=VITE_API_BASE_URL=${BACKEND_URL}/api/v1
      - --build-arg=VITE_GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-}
      - --target=production
      - -t
      - ${FRONTEND_IMAGE}
      - .
images:
  - '${FRONTEND_IMAGE}'
EOF

gcloud builds submit "${REPO_ROOT}/frontend" \
  --project="${PROJECT_ID}" \
  --config="${CLOUDBUILD_CONFIG}"

rm -f "${CLOUDBUILD_CONFIG}"

echo "${FRONTEND_IMAGE}" > .last-frontend-image
echo "   Imagen frontend: ${FRONTEND_IMAGE}"

echo ""
echo ">> Imágenes publicadas. Siguiente paso: ./08-deploy-backend.sh y ./09-deploy-frontend.sh"
