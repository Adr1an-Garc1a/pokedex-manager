# Manual de ejecución — versión con registro obligatorio + CRUD colección

Este manual cubre cómo correr la versión más reciente del proyecto, tanto en
local como reflejando los cambios en tu despliegue de GCP ya existente.

## 0. Qué cambió respecto a la primera versión

- El login ya **no** crea usuarios automáticamente: si tu cuenta de Google no
  está registrada, verás un formulario de registro autocompletado antes de
  poder entrar (ver `docs/ARCHITECTURE.md`, sección 4).
- La colección personal (`/collection`) tiene CRUD completo — crear, editar,
  borrar — y ahora hay una guía dedicada para probarlo con Postman
  (`docs/POSTMAN_GUIDE.md`).
- El navbar ya no se rompe en pantallas de celular.
- Nuevo: pipeline de CI/CD opcional (`docs/CI_CD.md`).
- Nuevo: las 3 funcionalidades bonus de IA — identificar Pokémon por foto,
  chat MCP con Claude Sonnet 5, e insights de colección. Requieren un par de
  pasos de configuración manuales (una API key de Anthropic + crear la base
  de Firestore) que no afectan al resto de la app si se omiten — ver
  `docs/BONUS_FEATURES.md`.

## 1. Correr localmente (recomendado para revisar los cambios)

Requisitos: Docker y Docker Compose instalados.

```bash
cd pokedex-manager
cp .env.example .env      # si no lo tienes ya de antes
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend (Swagger UI): http://localhost:8000/docs

Si ya tenías el proyecto corriendo antes y solo copiaste los archivos
nuevos encima, un `docker compose up --build` reconstruye las imágenes con
el código actualizado (las migraciones de Alembic corren solas al iniciar).

### Probar el flujo de registro

1. Abre http://localhost:5173 → botón "Iniciar sesión con Google".
2. Si es una cuenta de Google que nunca usaste en esta app, verás el
   formulario "¡Bienvenido, {tu nombre}!" con el nombre editable — confirma
   para registrarte.
3. La próxima vez que inicies sesión con esa misma cuenta, entra directo
   (ya está registrada).

### Ejecutar los tests del backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # si no existe ya
pip install -r requirements.txt
pytest -q
```

Deberías ver `28 passed` (incluye login/registro, colección, y las 3 funcionalidades bonus de IA).

## 2. Actualizar tu despliegue en GCP ya existente (manual, una vez más)

Como ya tienes la infraestructura creada (Cloud SQL, bucket, Artifact
Registry, service account), **no** vuelvas a correr `01` a `06` — esos ya
hicieron su trabajo y son idempotentes, pero no hace falta repetirlos.

**Excepción esta vez**: si quieres las funcionalidades bonus de IA (chat,
vision, insights), sí corre de nuevo `01-enable-apis.sh` y
`02-service-accounts-iam.sh` (habilitan Firestore y agregan el permiso
`roles/datastore.user` — no rompen nada de lo que ya tenías, son
idempotentes), más el script nuevo `11-setup-firestore.sh` y, si quieres el
chat, `06-secrets.sh` con tu API key de Anthropic. Detalle completo en
`docs/BONUS_FEATURES.md`. Si no te interesa el bonus por ahora, sáltate este
párrafo — el resto de la app funciona igual.

Para lo demás, solo necesitas reconstruir las imágenes con el código nuevo y
volver a desplegar:

```bash
cd infra/gcp
export PROJECT_ID=tu-proyecto-gcp   # el que ya usaste antes

./07-build-push.sh
./08-deploy-backend.sh

export BACKEND_URL=$(cat .last-backend-url)
./07-build-push.sh        # reconstruye el frontend con la URL real del backend
./09-deploy-frontend.sh
```

Verifica:

```bash
curl "$(cat .last-backend-url)/health"
```

Abre la URL del frontend (`cat .last-frontend-url`) y prueba login/registro
igual que en local.

## 3. Probar la API con Postman

Sigue [`docs/POSTMAN_GUIDE.md`](POSTMAN_GUIDE.md) paso a paso: cómo sacar tu
JWT desde el navegador, configurarlo en Postman, y probar crear/editar/borrar
Pokémon de tu colección.

## 4. (Opcional) Dejar que los próximos cambios se desplieguen solos

Por ahora, cada actualización a GCP sigue siendo manual (paso 2 de este
manual). Si quieres que un `git push` a `main` dispare el build y el deploy
automáticamente, sigue [`docs/CI_CD.md`](CI_CD.md) — son 3 pasos, uno de
ellos (conectar el repo) se hace una sola vez desde la consola de GCP.
