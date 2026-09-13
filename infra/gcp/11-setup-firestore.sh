#!/usr/bin/env bash
# =============================================================================
# 11-setup-firestore.sh — Crea la base de datos de Firestore en modo Native
# (una sola vez por proyecto de GCP; a diferencia de Cloud SQL, no es un
# servicio que se "despliega" — es una base de datos serverless a nivel de
# proyecto). La usa el chat MCP con Claude Sonnet 5 para guardar el
# historial de conversación de cada usuario (ver docs/BONUS_FEATURES.md).
#
# Idempotente: si ya existe una base de datos "(default)", no hace nada.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

echo ">> Verificando si ya existe una base de datos de Firestore en ${PROJECT_ID}..."

if gcloud firestore databases describe --database="(default)" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "   Ya existe, se omite creación."
else
  echo ">> Creando base de datos Firestore (modo Native, región ${VERTEX_LOCATION})..."
  # nam5 / eur3 son las multi-regiones más comunes; si tu proyecto ya tiene
  # recursos en una región puntual (como Cloud SQL), gcloud igual acepta esa
  # región para Firestore siempre que exista como ubicación válida.
  gcloud firestore databases create \
    --project="${PROJECT_ID}" \
    --location="${VERTEX_LOCATION}" \
    --type=firestore-native \
    --quiet
fi

echo ">> Firestore listo. Colección usada por la app: mcp_conversations/{user_id}"
