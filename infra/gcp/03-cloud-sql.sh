#!/usr/bin/env bash
# =============================================================================
# 03-cloud-sql.sh — Aprovisiona la instancia Cloud SQL (PostgreSQL), la base
# de datos y el usuario de aplicación. La contraseña se genera aleatoriamente
# y se guarda directamente en Secret Manager (nunca en texto plano en disco).
#
# Nota: crear la instancia puede tardar 5-10 minutos.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

echo ">> Verificando si la instancia ${SQL_INSTANCE} ya existe..."
if gcloud sql instances describe "${SQL_INSTANCE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "   Ya existe, se omite creación de la instancia."
else
  echo ">> Creando instancia Cloud SQL (PostgreSQL 16, tier ${SQL_TIER})... esto puede tardar varios minutos."
  gcloud sql instances create "${SQL_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --database-version=POSTGRES_16 \
    --tier="${SQL_TIER}" \
    --region="${SQL_REGION}" \
    --storage-auto-increase \
    --storage-size=10GB \
    --availability-type=zonal
fi

echo ">> Creando base de datos ${SQL_DATABASE} (si no existe)..."
gcloud sql databases create "${SQL_DATABASE}" \
  --instance="${SQL_INSTANCE}" --project="${PROJECT_ID}" 2>/dev/null || \
  echo "   Ya existe."

DB_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/')"

echo ">> Creando usuario de aplicación ${SQL_USER}..."
if gcloud sql users list --instance="${SQL_INSTANCE}" --project="${PROJECT_ID}" \
    --format="value(name)" | grep -qx "${SQL_USER}"; then
  echo "   El usuario ya existe; se actualiza su contraseña."
  gcloud sql users set-password "${SQL_USER}" \
    --instance="${SQL_INSTANCE}" --project="${PROJECT_ID}" --password="${DB_PASSWORD}"
else
  gcloud sql users create "${SQL_USER}" \
    --instance="${SQL_INSTANCE}" --project="${PROJECT_ID}" --password="${DB_PASSWORD}"
fi

CONNECTION_NAME="$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --project="${PROJECT_ID}" --format="value(connectionName)")"

# Cadena de conexión para el Cloud SQL Python Connector (usada por Cloud Run).
# Ver docs/GCP_DEPLOYMENT.md para cómo el backend la consume.
DATABASE_URL="postgresql+psycopg://${SQL_USER}:${DB_PASSWORD}@/${SQL_DATABASE}?host=/cloudsql/${CONNECTION_NAME}"

echo ">> Guardando DATABASE_URL en Secret Manager (${SECRET_DB_URL})..."
if gcloud secrets describe "${SECRET_DB_URL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  printf '%s' "${DATABASE_URL}" | gcloud secrets versions add "${SECRET_DB_URL}" \
    --project="${PROJECT_ID}" --data-file=-
else
  printf '%s' "${DATABASE_URL}" | gcloud secrets create "${SECRET_DB_URL}" \
    --project="${PROJECT_ID}" --replication-policy="automatic" --data-file=-
fi

echo ""
echo ">> Cloud SQL listo."
echo "   Instancia:        ${SQL_INSTANCE}"
echo "   Connection name:  ${CONNECTION_NAME}"
echo "   Secret con la URL: ${SECRET_DB_URL} (Secret Manager)"
echo ""
echo "   Para desarrollo local con Cloud SQL Auth Proxy:"
echo "     cloud-sql-proxy ${CONNECTION_NAME} --port 5432"
