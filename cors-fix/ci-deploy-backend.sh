#!/usr/bin/env bash
# =============================================================================
# ci-deploy-backend.sh — Ejecutado por Cloud Build (ver ../../cloudbuild.yaml),
# NO manualmente. Las variables llegan como env vars desde el step de Cloud
# Build (PROJECT_ID, REGION, BACKEND_SERVICE, IMAGE, SQL_INSTANCE,
# RUNTIME_SA_EMAIL, GCS_BUCKET, SECRET_*).
# =============================================================================
set -euo pipefail
source "$(dirname "$0")/lib-service-urls.sh"

CONNECTION_NAME="$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" --format='value(connectionName)')"

# IMPORTANTE: `gcloud run deploy --set-env-vars` REEMPLAZA TODAS las
# variables de entorno del servicio, no es aditivo. Si CORS_ORIGINS no se
# incluye aquí explícitamente, cada deploy de CI/CD la borraría y el
# backend caería al default del código (localhost:5173), rompiendo CORS
# para el frontend real desplegado en Cloud Run. Por eso se auto-detecta
# la URL del frontend ya desplegado en cada build, en vez de depender de
# que alguien la recuerde.
#
# OJO: un mismo servicio de Cloud Run puede tener más de una URL válida
# (formato legado con hash y formato nuevo con número de proyecto) y
# `describe --format=value(status.url)` no siempre devuelve la misma que
# usa el navegador como Origin. Por eso se piden TODAS las URLs conocidas
# del frontend (get_all_service_urls) y se incluyen todas en CORS_ORIGINS,
# separadas por coma — así no importa cuál de las dos "sea la correcta".
FRONTEND_URLS="$(get_all_service_urls "${FRONTEND_SERVICE}" "${PROJECT_ID}" "${REGION}")"
CORS_ORIGINS_VALUE="${FRONTEND_URLS:-*}"

# OJO 2: por defecto `--set-env-vars` separa pares KEY=VALUE con coma, pero
# CORS_ORIGINS_VALUE puede tener varias URLs separadas por coma dentro de
# UN SOLO valor (ver arriba) — con la sintaxis por defecto, gcloud las
# interpretaría como variables adicionales sin "=" y fallaría con "Bad
# syntax for dict arg". El prefijo "^;^" le dice a gcloud que use ";" como
# separador entre pares en vez de ",", así las comas dentro del valor de
# CORS_ORIGINS quedan intactas (ver `gcloud topic escaping`).
gcloud run deploy "${BACKEND_SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --service-account="${RUNTIME_SA_EMAIL}" \
  --add-cloudsql-instances="${CONNECTION_NAME}" \
  --set-secrets="DATABASE_URL=${SECRET_DB_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT_KEY}:latest,GOOGLE_CLIENT_ID=${SECRET_GOOGLE_CLIENT_ID}:latest" \
  --set-env-vars="^;^STORAGE_BACKEND=gcs;GCS_BUCKET_NAME=${GCS_BUCKET};ENVIRONMENT=production;CORS_ORIGINS=${CORS_ORIGINS_VALUE}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=4 \
  --memory=512Mi \
  --cpu=1 \
  --quiet

echo ">> Backend desplegado por CI/CD. CORS_ORIGINS configurado con: ${CORS_ORIGINS_VALUE}"
echo ">> URLs conocidas del backend: $(get_all_service_urls "${BACKEND_SERVICE}" "${PROJECT_ID}" "${REGION}")"
