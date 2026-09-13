#!/usr/bin/env bash
# =============================================================================
# 12-reset-data.sh — Borra TODOS los datos de la app (usuarios, colecciones,
# historial de chat, historial de Vision, imágenes subidas) para "reiniciar
# desde cero", sin tocar la infraestructura desplegada.
#
# Qué borra:
#   - Cloud SQL (${SQL_INSTANCE} / ${SQL_DATABASE}): vacía TODAS las tablas de
#     la app (usuarios, entradas de colección, etc.) — el ESQUEMA se
#     conserva (no se borra ni se recrea la base, no hace falta volver a
#     correr migraciones de Alembic).
#   - Cloud Storage (gs://${GCS_BUCKET}): borra todas las imágenes subidas
#     (fotos de Vision, imágenes personalizadas de la colección).
#   - Firestore: borra todos los documentos de las colecciones
#     `mcp_conversations` (conversaciones del chat IA) y `vision_history`
#     (historial de identificaciones).
#
# Qué NO borra (para eso está 99-teardown.sh, que sí elimina infraestructura):
#   - Las instancias/servicios en sí (Cloud SQL, Cloud Run, el bucket, la
#     base de datos de Firestore) — todo se queda desplegado y funcionando,
#     solo que sin ningún dato de usuario. La app queda utilizable de
#     inmediato, como recién desplegada.
#
# Requisitos:
#   - psql instalado localmente (lo usa `gcloud sql connect`; en Cloud Shell
#     ya viene instalado).
#   - Credenciales de aplicación por defecto para Firestore: si no las has
#     configurado, corre primero `gcloud auth application-default login`.
#
# Pide confirmación explícita antes de borrar nada.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./00-config.sh

echo "Esto BORRA TODOS LOS DATOS (usuarios, colecciones, chat, Vision) en el proyecto ${PROJECT_ID}:"
echo "  - Cloud SQL (${SQL_INSTANCE} / ${SQL_DATABASE}): se vacían todas las tablas (el esquema se conserva)"
echo "  - Cloud Storage (gs://${GCS_BUCKET}): se borran todas las imágenes subidas"
echo "  - Firestore: se borran los documentos de mcp_conversations y vision_history"
echo ""
echo "La infraestructura en sí (instancias, servicios, el bucket, la base de Firestore)"
echo "NO se borra — la app queda lista para usarse de inmediato, sin ningún dato."
echo ""
read -r -p "¿Confirmas? Escribe 'reiniciar todo' para continuar: " CONFIRM
if [[ "${CONFIRM}" != "reiniciar todo" ]]; then
  echo "Cancelado."
  exit 0
fi

# --- 1. Cloud SQL: vaciar todas las tablas de la app (conserva el esquema) --
echo ""
echo ">> [1/3] Vaciando las tablas de Cloud SQL..."

if ! gcloud sql instances describe "${SQL_INSTANCE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "   La instancia ${SQL_INSTANCE} no existe — ¿ya corriste 03-cloud-sql.sh? Se omite este paso."
elif ! command -v psql >/dev/null 2>&1; then
  echo "   ADVERTENCIA: psql no está instalado en esta máquina (lo necesita 'gcloud sql connect')."
  echo "   Instálalo (o corre este script desde Cloud Shell, que ya lo trae) y vuelve a intentar."
  echo "   Se omite el borrado de Cloud SQL; continúa con Storage y Firestore."
else
  DATABASE_URL="$(gcloud secrets versions access latest --secret="${SECRET_DB_URL}" --project="${PROJECT_ID}" 2>/dev/null || true)"
  if [[ -z "${DATABASE_URL}" ]]; then
    echo "   No se encontró el secreto ${SECRET_DB_URL} — se omite este paso."
  else
    # DATABASE_URL tiene forma postgresql+psycopg://usuario:password@/... — se
    # extrae la contraseña para pasarla vía PGPASSWORD y que psql no la pida
    # de forma interactiva (03-cloud-sql.sh la genera solo con caracteres
    # alfanuméricos, así que este recorte con sed es seguro).
    DB_PASSWORD="$(printf '%s' "${DATABASE_URL}" | sed -E 's#^[a-zA-Z+]+://[^:]+:([^@]+)@.*#\1#')"
    export PGPASSWORD="${DB_PASSWORD}"

    # `gcloud sql connect` autoriza temporalmente la IP actual y lanza psql
    # contra la instancia — con PGPASSWORD ya en el ambiente no debería pedir
    # contraseña de forma interactiva. El bloque PL/pgSQL recorre TODAS las
    # tablas del esquema `public` (para no tener que mantener a mano una
    # lista fija que se desactualice si cambia el modelo de datos) y las
    # vacía, EXCEPTO `alembic_version` (así el backend no cree que hace falta
    # volver a correr las migraciones).
    gcloud sql connect "${SQL_INSTANCE}" \
      --project="${PROJECT_ID}" \
      --user="${SQL_USER}" \
      --database="${SQL_DATABASE}" \
      --quiet <<'SQL'
DO $$
DECLARE
  tabla text;
BEGIN
  FOR tabla IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
  LOOP
    EXECUTE format('TRUNCATE TABLE %I RESTART IDENTITY CASCADE;', tabla);
  END LOOP;
END $$;
SQL
    unset PGPASSWORD
    echo "   Tablas vaciadas (esquema y versión de Alembic intactos)."
  fi
fi

# --- 2. Cloud Storage: borrar todas las imágenes subidas --------------------
echo ""
echo ">> [2/3] Borrando imágenes en gs://${GCS_BUCKET}..."
if gcloud storage buckets describe "gs://${GCS_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  # El comodín "/**" borra todo el CONTENIDO del bucket sin borrar el bucket
  # en sí (a diferencia de apuntar --recursive directo a "gs://bucket").
  gcloud storage rm --recursive "gs://${GCS_BUCKET}/**" --quiet 2>/dev/null || \
    echo "   El bucket ya estaba vacío."
  echo "   Imágenes borradas."
else
  echo "   El bucket gs://${GCS_BUCKET} no existe — se omite."
fi

# --- 3. Firestore: borrar historial de chat e identificaciones --------------
echo ""
echo ">> [3/3] Borrando documentos de Firestore (mcp_conversations, vision_history)..."
if ! gcloud firestore databases describe --database="(default)" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "   No hay base de datos de Firestore en este proyecto — se omite."
else
  # gcloud no tiene un comando para borrar colecciones completas de
  # Firestore (eso sí lo trae la CLI de Firebase, pero es una herramienta
  # aparte que este proyecto no usa para nada más) — se usa en su lugar el
  # cliente de Python que YA es una dependencia del backend
  # (google-cloud-firestore), con un script de una sola vez que borra todos
  # los documentos de las dos colecciones que usa esta app.
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "   No hay credenciales de aplicación por defecto configuradas."
    echo "   Corre 'gcloud auth application-default login' y vuelve a ejecutar este script."
  else
    if ! python3 -c "import google.cloud.firestore" >/dev/null 2>&1; then
      echo "   Instalando el cliente de Firestore para Python (google-cloud-firestore)..."
      pip install --quiet google-cloud-firestore
    fi
    GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" python3 - <<'PYEOF'
import os

from google.cloud import firestore

project = os.environ["GOOGLE_CLOUD_PROJECT"]
client = firestore.Client(project=project)

for collection_name in ("mcp_conversations", "vision_history"):
    docs = list(client.collection(collection_name).stream())
    for doc in docs:
        doc.reference.delete()
    print(f"   {collection_name}: {len(docs)} documento(s) borrado(s).")
PYEOF
  fi
fi

echo ""
echo ">> Listo — todos los datos fueron borrados. La app queda como recién desplegada,"
echo "   sin ningún usuario ni colección, lista para usarse de inmediato."
