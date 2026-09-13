#!/usr/bin/env bash
# =============================================================================
# 01-enable-apis.sh — Habilita las APIs de GCP necesarias para el proyecto.
# Idempotente: se puede correr varias veces sin efectos negativos.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

echo ">> Habilitando APIs en el proyecto ${PROJECT_ID}..."

gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  sql-component.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  compute.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  --project="${PROJECT_ID}"

echo ">> APIs habilitadas correctamente."
echo ">> aiplatform.googleapis.com (Vertex AI, Gemini 2.5 Flash) y firestore.googleapis.com"
echo "   (historial del chat) son para las funcionalidades bonus de IA — ver docs/BONUS_FEATURES.md."
