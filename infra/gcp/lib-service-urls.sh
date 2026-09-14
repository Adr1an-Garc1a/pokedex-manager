#!/usr/bin/env bash
# =============================================================================
# lib-service-urls.sh — Devuelve TODAS las URLs válidas de un servicio de
# Cloud Run, no solo una.
#
# Por qué existe: en este proyecto se detectó que
# `gcloud run services describe --format='value(status.url)'` puede devolver
# una URL con formato legado (https://servicio-xxxxxx-uc.a.run.app)
# distinta a la URL que realmente usa el navegador como Origin, y que el
# propio `gcloud run deploy` reportó en su salida "Service URL:" al momento
# de desplegar (formato nuevo, con número de proyecto:
# https://servicio-NNNNNNNN.region.run.app). Ambas resuelven al mismo
# servicio (Cloud Run las acepta como alias), pero si CORS_ORIGINS solo
# confía en una de las dos, el navegador bloquea el origen real por CORS.
#
# La solución: en vez de adivinar cuál de las dos es "la correcta" para este
# proyecto, se piden TODAS las URLs que Cloud Run reconoce como válidas para
# el servicio (metadata.annotations['run.googleapis.com/urls'], un array
# JSON con todos los alias) además de status.url por si acaso, y se
# devuelven separadas por coma — config.py ya soporta CORS_ORIGINS con
# múltiples orígenes separados por coma (ver cors_origins_list).
# =============================================================================

get_all_service_urls() {
  local service="$1" project="$2" region="$3"
  gcloud run services describe "${service}" \
    --project="${project}" --region="${region}" --format=json 2>/dev/null \
    | python3 -c '
import json, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

urls = set()

status_url = (data.get("status") or {}).get("url")
if status_url:
    urls.add(status_url)

annotations = (data.get("metadata") or {}).get("annotations") or {}
raw = annotations.get("run.googleapis.com/urls")
if raw:
    try:
        for u in json.loads(raw):
            urls.add(u)
    except Exception:
        pass

print(",".join(sorted(urls)))
' 2>/dev/null || true
}
