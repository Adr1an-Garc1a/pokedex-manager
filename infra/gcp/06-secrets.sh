#!/usr/bin/env bash
# =============================================================================
# 06-secrets.sh — Crea/actualiza en Secret Manager los secretos que aún no
# genera automáticamente 03-cloud-sql.sh: el JWT secret y el Google Client ID.
#
# El Google OAuth Client ID se crea manualmente en la consola (ver
# docs/GCP_DEPLOYMENT.md, sección "Configurar Google OAuth consent screen"),
# porque la API de OAuth consent no es totalmente automatizable por CLI.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

upsert_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    printf '%s' "${value}" | gcloud secrets versions add "${name}" \
      --project="${PROJECT_ID}" --data-file=-
    echo "   Actualizado: ${name}"
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" \
      --project="${PROJECT_ID}" --replication-policy="automatic" --data-file=-
    echo "   Creado: ${name}"
  fi
}

echo ">> JWT_SECRET_KEY:"
# Idempotente por diseño: si el secreto ya existe, NO se regenera solo porque
# volviste a correr este script por otra razón (ej. agregar ANTHROPIC_API_KEY).
# Cada vez que JWT_SECRET_KEY cambia, todas las sesiones ya iniciadas quedan
# invalidadas (el JWT de cada usuario deja de validar) y tienen que volver a
# iniciar sesión — eso solo se quiere hacer a propósito, nunca como efecto
# secundario. Si de verdad quieres rotarlo, corre:
#   export ROTATE_JWT_SECRET=1 && ./06-secrets.sh
if gcloud secrets describe "${SECRET_JWT_KEY}" --project="${PROJECT_ID}" >/dev/null 2>&1 \
   && [[ -z "${ROTATE_JWT_SECRET:-}" ]]; then
  echo "   Ya existe, se deja igual (no se invalidan sesiones activas)."
else
  JWT_SECRET="$(openssl rand -hex 32)"
  upsert_secret "${SECRET_JWT_KEY}" "${JWT_SECRET}"
  echo "   OJO: esto invalida las sesiones ya iniciadas — todos tendrán que volver a hacer login."
fi

echo ""
echo ">> GOOGLE_CLIENT_ID:"
if [[ -z "${GOOGLE_CLIENT_ID:-}" ]]; then
  echo "   No se definió la variable de entorno GOOGLE_CLIENT_ID."
  echo "   Crea credenciales OAuth 'Web application' en:"
  echo "     https://console.cloud.google.com/apis/credentials?project=${PROJECT_ID}"
  echo "   y vuelve a correr este script así:"
  echo "     export GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com"
  echo "     ./06-secrets.sh"
else
  upsert_secret "${SECRET_GOOGLE_CLIENT_ID}" "${GOOGLE_CLIENT_ID}"
fi

echo ""
echo ">> ANTHROPIC_API_KEY (bonus: chat MCP con Claude Sonnet 5):"
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "   No se definió la variable de entorno ANTHROPIC_API_KEY."
  echo "   Crea una API key en https://console.anthropic.com/settings/keys"
  echo "   (cuenta de Anthropic, separada de tu facturación de GCP) y vuelve a"
  echo "   correr este script así:"
  echo "     export ANTHROPIC_API_KEY=sk-ant-..."
  echo "     ./06-secrets.sh"
  echo "   Sin este secreto, el botón de chat de la app responde 503 (el resto"
  echo "   de la app funciona igual)."
else
  upsert_secret "${SECRET_ANTHROPIC_API_KEY}" "${ANTHROPIC_API_KEY}"
fi

echo ""
echo ">> Secretos disponibles en Secret Manager:"
gcloud secrets list --project="${PROJECT_ID}" \
  --filter="name~${APP_NAME}" --format="table(name)"
