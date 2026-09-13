#!/usr/bin/env bash
# =============================================================================
# 00-config.sh — Variables compartidas por todos los scripts de infra/gcp/*.sh
#
# Este archivo NO se ejecuta solo: los demás scripts hacen
#   source "$(dirname "$0")/00-config.sh"
# Ajusta los valores por defecto aquí o expórtalos antes de correr los scripts,
# por ejemplo:
#   export PROJECT_ID=mi-proyecto-pokedex
#   ./03-cloud-sql.sh
# =============================================================================
set -euo pipefail

# --- Identidad del proyecto ---
export PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
export REGION="${REGION:-us-central1}"
export ZONE="${ZONE:-us-central1-a}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: define PROJECT_ID (export PROJECT_ID=tu-proyecto-gcp) o corre 'gcloud config set project <id>'." >&2
  exit 1
fi

# --- Nombres de recursos (puedes cambiarlos, pero deben ser consistentes entre scripts) ---
export APP_NAME="pokedex-manager"

export ARTIFACT_REPO="${APP_NAME}-repo"
export BACKEND_SERVICE="${APP_NAME}-backend"
export FRONTEND_SERVICE="${APP_NAME}-frontend"

export SQL_INSTANCE="${APP_NAME}-db"
export SQL_DATABASE="pokedex_manager"
export SQL_USER="pokedex_app"
export SQL_TIER="db-f1-micro"           # suficiente para dev/demo; subir en prod
export SQL_REGION="${REGION}"

export GCS_BUCKET="${PROJECT_ID}-${APP_NAME}-images"

export RUNTIME_SA_NAME="${APP_NAME}-runtime"
export RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export SECRET_DB_URL="${APP_NAME}-database-url"
export SECRET_JWT_KEY="${APP_NAME}-jwt-secret"
export SECRET_GOOGLE_CLIENT_ID="${APP_NAME}-google-client-id"
export SECRET_ANTHROPIC_API_KEY="${APP_NAME}-anthropic-api-key"

# --- IA (funcionalidades bonus) ---
export VERTEX_LOCATION="${VERTEX_LOCATION:-${REGION}}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-sonnet-5}"

echo "Config cargada: PROJECT_ID=${PROJECT_ID} REGION=${REGION} APP_NAME=${APP_NAME}"
