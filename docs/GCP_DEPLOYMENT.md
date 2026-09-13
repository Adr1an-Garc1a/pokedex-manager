# Despliegue en Google Cloud Platform

## Prerrequisitos

- Un proyecto de GCP con facturación habilitada.
- `gcloud` CLI instalado y autenticado (`gcloud auth login`).
- `gcloud config set project <TU_PROJECT_ID>` (o exportar `PROJECT_ID` antes
  de cada script).

## OAuth consent screen (manual, una sola vez)

La consola de OAuth no expone una API CLI completa para el consent screen,
así que este paso no se automatiza:

1. [Google Cloud Console → APIs & Services → OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent).
2. Tipo de usuario: **External** (o Internal con Google Workspace).
3. Nombre de la app, correo de soporte, dominio (opcional en dev).
4. Scopes básicos (`email`, `profile`, `openid`).
5. **Credentials → Create Credentials → OAuth Client ID**, tipo **Web application**.
6. En **Authorized JavaScript origins** agregar `http://localhost:5173` y, más
   adelante, la URL de Cloud Run del frontend.
7. Copiar el **Client ID** — es `GOOGLE_CLIENT_ID`.

## Scripts de aprovisionamiento (`infra/gcp/`)

Cada script es idempotente (se puede volver a correr sin duplicar recursos)
y numerado en el orden en que se ejecutan la primera vez:

| Script | Recurso |
|---|---|
| `00-config.sh` | Variables compartidas (no crea nada, se importa con `source`) |
| `01-enable-apis.sh` | Habilita Cloud Run, Cloud SQL, Storage, Artifact Registry, Secret Manager, Cloud Build, Vertex AI |
| `02-service-accounts-iam.sh` | Service account de runtime + roles mínimos (`cloudsql.client`, `storage.objectAdmin`, `secretmanager.secretAccessor`, `aiplatform.user`, `datastore.user`) |
| `03-cloud-sql.sh` | Instancia Postgres 16, base de datos, usuario, y guarda `DATABASE_URL` en Secret Manager |
| `04-storage-bucket.sh` | Bucket GCS para imágenes + CORS |
| `05-artifact-registry.sh` | Repositorio Docker |
| `06-secrets.sh` | `JWT_SECRET_KEY` (autogenerado), `GOOGLE_CLIENT_ID` y, si se exporta `ANTHROPIC_API_KEY`, el secreto del chat IA |
| `07-build-push.sh` | Build con Cloud Build (sin Docker local) y push a Artifact Registry |
| `08-deploy-backend.sh` | Cloud Run del backend, conectado a Cloud SQL por Unix socket, secretos inyectados |
| `09-deploy-frontend.sh` | Cloud Run del frontend (nginx sirviendo el build de Vite) |
| `10-setup-ci-cd-iam.sh` | Permisos de la service account de Cloud Build para el pipeline de CI/CD — ver [`CI_CD.md`](CI_CD.md) |
| `11-setup-firestore.sh` | Base de datos de Firestore (historial de chat IA y de Vision) — ver [`BONUS_FEATURES.md`](BONUS_FEATURES.md) |
| `12-reset-data.sh` | Vacía todos los datos (usuarios, colección, chat, Vision) sin borrar infraestructura, para "reiniciar" la app |
| `99-teardown.sh` | Borra toda la infraestructura anterior (pide confirmación explícita) |
| `ci-deploy-backend.sh`, `ci-deploy-frontend.sh`, `lib-service-urls.sh` | Usados solo por el pipeline de Cloud Build (ver [`CI_CD.md`](CI_CD.md)) — no se corren a mano |

### Orden de ejecución (primera vez)

```bash
cd infra/gcp
export PROJECT_ID=tu-proyecto-gcp
export GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com   # del paso de OAuth

./01-enable-apis.sh
./02-service-accounts-iam.sh
./03-cloud-sql.sh            # tarda varios minutos
./04-storage-bucket.sh
./05-artifact-registry.sh
./06-secrets.sh
./11-setup-firestore.sh      # necesario para el chat IA y el historial de Vision
./07-build-push.sh           # construye backend y frontend con Cloud Build
./08-deploy-backend.sh       # despliega backend, imprime su URL

export BACKEND_URL=$(cat .last-backend-url)
./07-build-push.sh           # reconstruye el frontend ya con la URL real del backend
./09-deploy-frontend.sh
```

Verificación:

```bash
curl "$(cat infra/gcp/.last-backend-url)/health"
# {"status":"ok","service":"PokéDex Manager API","environment":"production"}
```

La URL del frontend (`cat infra/gcp/.last-frontend-url`) es la que abre el
navegador para iniciar sesión con Google.

### Actualizaciones posteriores

Con la infraestructura ya creada, un cambio de código solo necesita
reconstruir y redesplegar (no hace falta repetir `01`-`06`, que ya hicieron
su trabajo):

```bash
cd infra/gcp
export PROJECT_ID=tu-proyecto-gcp

./07-build-push.sh
./08-deploy-backend.sh

export BACKEND_URL=$(cat .last-backend-url)
./07-build-push.sh
./09-deploy-frontend.sh
```

Con el pipeline de CI/CD configurado (ver [`CI_CD.md`](CI_CD.md)), esto
ocurre automáticamente en cada push a `main`.

## Reiniciar los datos sin borrar la infraestructura

Para vaciar usuarios, colección, historial de chat y de Vision — dejando la
app lista para usarse de inmediato, sin tener que volver a desplegar nada:

```bash
cd infra/gcp
export PROJECT_ID=tu-proyecto-gcp
./12-reset-data.sh
```

Pide confirmación explícita antes de borrar nada. Vacía las tablas de Cloud
SQL (conserva el esquema — no hace falta volver a correr las migraciones de
Alembic), borra las imágenes del bucket de Cloud Storage, y borra los
documentos de Firestore (`mcp_conversations`, `vision_history`). Requiere
`psql` instalado localmente (ya viene en Cloud Shell) y credenciales de
aplicación por defecto (`gcloud auth application-default login`) para el
paso de Firestore.

Esto es distinto de `99-teardown.sh`: ese sí elimina la infraestructura en
sí (instancias, servicios, el bucket); `12-reset-data.sh` solo vacía los
datos.

## Costos y limpieza

Todos los recursos usados (`db-f1-micro`, Cloud Run con `min-instances=0`,
bucket estándar) están dentro o cerca del *free tier* de GCP para uso de
demo/evaluación. Para no dejar nada facturando:

```bash
cd infra/gcp
./99-teardown.sh
```

## De `.sh` a Terraform (siguiente paso natural)

Estos scripts son intencionalmente simples y aptos para un desarrollo de
pocos días. Si el proyecto creciera, el siguiente paso natural es convertir
cada script en un módulo de Terraform (o Pulumi) para tener estado
declarativo, `plan`/`apply` y detección de drift — la lógica de qué recursos
se necesitan y con qué configuración ya está resuelta aquí y se traduce casi
1:1.
