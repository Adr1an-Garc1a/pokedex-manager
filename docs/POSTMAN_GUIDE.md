# Probar la API con Postman

Esta guía es para quien nunca ha usado Postman. Cubre cómo probar el CRUD
completo de la colección personal (crear, leer, editar, borrar un Pokémon de
tu colección) y el proxy de solo lectura hacia PokéAPI.

> **Resumen de lo que ya existe:** el catálogo de Pokémon (`GET /pokemon...`)
> es de **solo lectura** porque viene de una API externa de terceros — no
> tendría sentido "editar" un Pokémon del catálogo. Lo que sí es tuyo y
> tiene **CRUD completo** (crear, leer, actualizar, borrar) es tu **colección
> personal** (`/collection`): cada Pokémon que agregas ahí es un registro
> propio en tu base de datos, con tu apodo, nivel, notas, favorito, etc.

## 0. Instalar Postman

Descarga la app de escritorio desde https://www.postman.com/downloads/ (o usa
la versión web si prefieres) y crea una cuenta gratuita (o usa "Skip and
go to the app" para no crear cuenta).

## 1. Conseguir un token (JWT) para autenticarte

La API usa JWT (`Authorization: Bearer <token>`) para las rutas protegidas.
Como el login es con Google, la forma más simple de conseguir un token es
iniciar sesión una vez desde el navegador, en la instancia ya desplegada
(o en tu propia copia corriendo en local, si levantaste `docker compose up`),
y copiar el token:

1. Abre la app en el navegador e inicia sesión con Google (si es la primera
   vez, completa el formulario de registro que aparece).
2. Abre las herramientas de desarrollador del navegador (F12 o clic derecho
   → "Inspeccionar").
3. Ve a la pestaña **Application** (Chrome) o **Storage** (Firefox) → **Local
   Storage** → la URL de tu app.
4. Busca la clave `pokedex_manager_token` y copia su valor completo (es un
   texto largo tipo `eyJhbGciOi...`). Ese es tu JWT.

Alternativa: en la pestaña **Network**, busca la petición
`POST /auth/google/login` (o `.../register` si fue tu primer login), ábrela,
ve a la respuesta (**Response**) y copia el campo `"access_token"`.

> El token dura 24 horas (`JWT_EXPIRE_MINUTES=1440`). Si Postman empieza a
> responder 401, repite este paso para conseguir uno nuevo.

## 2. Crear la colección en Postman

1. Abre Postman → **New** → **Collection** → nómbrala `PokéDex Manager API`.
2. Click en la colección → pestaña **Variables** → agrega:
   - `base_url` = `http://localhost:8000/api/v1` (si corres local con Docker
     Compose) o la URL del **backend** en Cloud Run + `/api/v1` (si
     desplegaste en GCP, la encuentras en `infra/gcp/.last-backend-url`, o
     con `gcloud run services describe pokedex-manager-backend
     --region=us-central1 --format='value(status.url)'`).
   - `token` = el JWT que copiaste en el paso 1.
3. Pestaña **Authorization** de la colección → Type: **Bearer Token** → Token:
   `{{token}}`. Así todas las requests de la colección heredan el header
   `Authorization: Bearer <token>` automáticamente, sin repetirlo en cada una.

> ⚠️ **Error muy común: usar la URL del FRONTEND en `base_url`.** El
> proyecto tiene dos servicios en Cloud Run — `pokedex-manager-backend`
> (la API) y `pokedex-manager-frontend` (la página web) — y es fácil
> copiar la que no es. Si `base_url` apunta al frontend por error, **todas
> las requests de esta guía van a responder `200 OK` con el HTML de la
> página** (no un error visible, así que puede pasar desapercibido) en vez
> del JSON de la API — esto pasa porque el frontend sirve `index.html`
> para cualquier ruta desconocida, sea GET, POST, PUT o DELETE (es una SPA
> de React). **Cómo verificarlo:** después de configurar `base_url`, haz
> el GET de la sección 4.1 y mira la pestaña **Body** de la respuesta — si
> ves un objeto/array JSON, vas bien; si ves `<!DOCTYPE html>` o
> `<div id="root">`, `base_url` está apuntando al servicio equivocado
> (revisa también el `Content-Type` en la pestaña **Headers** de la
> respuesta: debe ser `application/json`, no `text/html`).

## 3. Requests de solo lectura (catálogo PokéAPI, no requieren tu colección)

Crea una carpeta "Pokédex (catálogo)" con estas requests (no necesitan auth,
aunque heredarla no hace daño):

| Método | URL | Notas |
|---|---|---|
| GET | `{{base_url}}/pokemon?limit=10&offset=0` | Lista paginada |
| GET | `{{base_url}}/pokemon?search=pikachu` | Búsqueda por nombre exacto |
| GET | `{{base_url}}/pokemon/25` | Detalle por ID (25 = Pikachu) |
| GET | `{{base_url}}/pokemon/charizard` | Detalle por nombre |

## 4. Requests de tu colección (CRUD completo, sí requieren tu token)

Crea otra carpeta "Mi Colección":

### 4.1 Leer (GET)

- `GET {{base_url}}/collection` → lista todo lo que tienes.
- `GET {{base_url}}/collection/stats` → totales, favoritos, distribución por tipo.

### 4.2 Crear (POST) — agregar un Pokémon a tu colección

- Método: `POST`
- URL: `{{base_url}}/collection`
- Pestaña **Body** → selecciona **raw** → tipo **JSON** → pega:

```json
{
  "pokemon_id": 25,
  "nickname": "Sparky",
  "level": 10,
  "notes": "Mi primer Pikachu de prueba",
  "is_favorite": true
}
```

- Send. Deberías recibir `201 Created` con el objeto completo, incluyendo su
  `"id"` (guárdalo, lo usas en los siguientes pasos — Postman lo llama
  `entry_id` en esta guía).

### 4.3 Editar (PUT) — actualizar apodo, nivel, notas o favorito

- Método: `PUT`
- URL: `{{base_url}}/collection/<entry_id>` (reemplaza `<entry_id>` por el
  `id` que te devolvió el POST, ej. `{{base_url}}/collection/1`)
- Body raw JSON (solo manda los campos que quieras cambiar):

```json
{
  "nickname": "Sparky Jr.",
  "level": 15
}
```

- Send → `200 OK` con la entrada actualizada.

### 4.4 Borrar (DELETE) — quitar un Pokémon de tu colección

- Método: `DELETE`
- URL: `{{base_url}}/collection/<entry_id>`
- Send → `204 No Content` (sin cuerpo de respuesta = éxito).
- Verifica con `GET {{base_url}}/collection` que ya no aparece.

### 4.5 Subir una imagen propia para una entrada (opcional)

- Método: `POST`
- URL: `{{base_url}}/collection/<entry_id>/image`
- Pestaña **Body** → **form-data** → key `file` (cambia el tipo de la key de
  "Text" a **"File"** con el desplegable a la derecha) → selecciona una
  imagen de tu computadora.
- Send → `200 OK` con `custom_image_url` apuntando a la imagen guardada.

## 5. Probar la validación de "no lo dejes entrar si no está registrado"

Para ver el flujo de registro obligatorio en acción directamente desde
Postman (sin frontend), necesitas un `id_token` de Google real, lo cual
Postman no puede generar por sí solo (requiere el flujo OAuth completo del
navegador). La forma práctica de verlo:

1. Inicia sesión con una cuenta de Google que **nunca** hayas usado en la
   app → el backend responde `404` con `code: "user_not_registered"` (esto
   ya lo ves en el navegador, en la pestaña Network, en la petición a
   `/auth/google/login`).
2. Completa el formulario de registro en el frontend → dispara
   `/auth/google/register` → `201 Created`.
3. Copia el nuevo token a Postman (paso 1 de esta guía) y ya puedes probar
   el CRUD de colección con esa cuenta.

## 6. Errores comunes al probar

| Respuesta | Causa | Solución |
|---|---|---|
| `200 OK` pero el Body es HTML (`<!DOCTYPE html>...`), no JSON — en cualquier request, incluido POST/PUT/DELETE | `base_url` apunta al servicio de **frontend** en vez del **backend** | Corrige la variable `base_url` de la colección (ver advertencia de la sección 2) — debe ser la URL de `pokedex-manager-backend` + `/api/v1` |
| `401 Unauthorized` | Falta el token, expiró, o no configuraste el Bearer Token en la colección | Repite el paso 1 y revisa la pestaña Authorization |
| `404` en `/collection/<id>` | Ese `id` no existe o pertenece a otro usuario | Verifica con `GET /collection` cuáles son tus IDs reales |
| `404` en `/pokemon/<algo>` | El nombre/ID no existe en PokéAPI | Revisa la ortografía (en inglés, ej. `charizard` no `charizar`) |
| `422 Unprocessable Entity` | El JSON del Body no cumple el esquema (ej. `level` fuera de 1-100) | Revisa el mensaje de error, indica exactamente qué campo falló |
