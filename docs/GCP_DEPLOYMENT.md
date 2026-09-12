# Despliegue en Google Cloud Platform

> **Recordatorio del enunciado:** *"No es necesario que la aplicación esté
> desplegada en producción."* Esta guía existe porque se pidió explícitamente
> como parte del ejercicio (arquitectura + scripts `.sh`), no porque sea un
> requisito de la prueba. Para evaluar el proyecto, `docker compose up` (ver
> README.md) es suficiente y más rápido.

## 0. Prerrequisitos

- Tener un proyecto de GCP con facturación habilitada.
- `gcloud` CLI instalado y autenticado: `gcloud auth login`.
- `gcloud config set project <TU_PROJECT_ID>` (o exporta `PROJECT_ID` antes de cada script).

## 1. Configurar Google OAuth consent screen (manual, una sola vez)

Esto no se automatiza por script porque la consola de OAuth no expone una API
CLI completa para el consent screen:

1. Ve a [Google Cloud Console → APIs & Services → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent).
2. Tipo de usuario: **External** (o Internal si usas Google Workspace).
3. Completa nombre de la app ("PokéDex Manager"), correo de soporte, dominio (opcional en dev).
4. Scopes: deja los básicos (`email`, `profile`, `openid`).
5. Ve a **Credentials → Create Credentials → OAuth Client ID**, tipo **Web application**.
6. En **Authorized JavaScript origins** agrega, por ahora, `http://localhost:5173`
   (más adelante agregarás la URL de Cloud Run del frontend).
7. Copia el **Client ID** generado — lo usarás como `GOOGLE_CLIENT_ID`.

## 2. Orden de ejecución de los scripts (`infra/gcp/`)

```bash
cd infra/gcp
chmod +x *.sh   # ya vienen con permisos de ejecución en el repo, por si acaso

export PROJECT_ID=tu-proyecto-gcp
export GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com   # el del paso 1

./01-enable-apis.sh
./02-service-accounts-iam.sh
./03-cloud-sql.sh            # tarda varios minutos
./04-storage-bucket.sh
./05-artifact-registry.sh
./06-secrets.sh
./07-build-push.sh           # construye backend y frontend con Cloud Build
./08-deploy-backend.sh       # despliega backend, imprime su URL
# Reconstruye el frontend ya con la URL real del backend:
export BACKEND_URL=$(cat .last-backend-url)
./07-build-push.sh
./09-deploy-frontend.sh
```

Cada script es idempotente: se puede volver a correr sin duplicar recursos.

## 3. Qué crea cada script

| Script | Recurso |
|---|---|
| `00-config.sh` | Variables compartidas (no crea nada, se importa con `source`) |
| `01-enable-apis.sh` | Habilita Cloud Run, Cloud SQL, Storage, Artifact Registry, Secret Manager, Cloud Build, Vertex AI |
| `02-service-accounts-iam.sh` | Service account de runtime + roles mínimos (`cloudsql.client`, `storage.objectAdmin`, `secretmanager.secretAccessor`, `aiplatform.user`) |
| `03-cloud-sql.sh` | Instancia Postgres 16, base de datos, usuario, y guarda `DATABASE_URL` en Secret Manager |
| `04-storage-bucket.sh` | Bucket GCS para imágenes + CORS |
| `05-artifact-registry.sh` | Repositorio Docker |
| `06-secrets.sh` | `JWT_SECRET_KEY` (autogenerado) y `GOOGLE_CLIENT_ID` en Secret Manager |
| `07-build-push.sh` | Build con Cloud Build (sin necesidad de Docker local) y push a Artifact Registry |
| `08-deploy-backend.sh` | Cloud Run del backend, conectado a Cloud SQL por Unix socket, secretos inyectados |
| `09-deploy-frontend.sh` | Cloud Run del frontend (nginx sirviendo el build de Vite) |
| `99-teardown.sh` | Borra todo lo anterior (pide confirmación explícita) |

## 4. Verificar el despliegue

```bash
curl "$(cat infra/gcp/.last-backend-url)/health"
# {"status":"ok","service":"PokéDex Manager API","environment":"production"}
```

Abre la URL del frontend (`cat infra/gcp/.last-frontend-url`) en el navegador
e inicia sesión con Google.

## 5. Costos y limpieza

Todos los recursos usados (`db-f1-micro`, Cloud Run con `min-instances=0`,
bucket estándar) están dentro o cerca del *free tier* de GCP para uso de
demo/evaluación. Aun así, para no dejar nada facturando:

```bash
cd infra/gcp
./99-teardown.sh
```

## 6. De `.sh` a Terraform (siguiente paso natural)

Estos scripts son intencionalmente simples (según lo pedido) y aptos para 3
días de desarrollo. Si el proyecto creciera, el siguiente paso natural es
convertir cada script en un módulo de Terraform (o Pulumi) para tener estado
declarativo, `plan`/`apply` y detección de drift — la lógica de qué recursos
se necesitan y con qué configuración ya está resuelta aquí y se traduce casi
1:1.
