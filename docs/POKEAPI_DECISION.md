# Decisión: cómo se resuelve el tema de "la API"

PokéAPI se usa como el catálogo público de Pokémon (solo lectura): especies,
stats, sprites, tipos, movimientos y cadenas de evolución. Pero además, el
proyecto crea **su propia API** (FastAPI) con CRUD completo — crear, editar,
borrar y ver — sobre la **colección personal** de cada usuario, que es un dato
que PokéAPI nunca tiene (no tiene usuarios ni persistencia propia). Este
documento explica cómo se dividen las responsabilidades entre ambas.

## El problema de nombres

Hay dos cosas distintas que es fácil confundir porque comparten el nombre "API":

1. **PokéAPI (pokeapi.co)** — una API pública, de solo lectura, mantenida por la
   comunidad, con el catálogo completo de Pokémon (especies, stats, sprites, tipos,
   movimientos, cadenas de evolución, etc.). No tiene usuarios, no tiene "mi colección",
   no acepta escritura.
2. **Nuestra propia API de backend** (FastAPI) — la que sí tiene usuarios, autenticación
   y persistencia, y que gestiona la colección personal de cada usuario.

## Decisión

**No se crea una copia/espejo de PokéAPI.** En vez de eso:

- **PokéAPI se usa como fuente de datos externa, de solo lectura**, consumida
  únicamente desde el backend (nunca desde el frontend directamente). El backend actúa
  como *proxy con caché*: expone `GET /api/v1/pokemon` y `GET /api/v1/pokemon/{id_o_nombre}`,
  que internamente llaman a `https://pokeapi.co/api/v2/pokemon/...` con `httpx`
  (async) y cachean la respuesta (in-memory TTL en dev; se puede pasar a Memorystore/
  Redis en producción) porque el catálogo de Pokémon prácticamente no cambia.
- **Nuestra API se llama, de forma explícita y sin ambigüedad, "PokéDex Manager API"**
  (prefijo de rutas `/api/v1/...`). Es la dueña de:
  - `auth` — login con Google y sesión propia.
  - `collection` — CRUD de la colección personal de cada usuario (esto es lo que en
    ningún caso existe en PokéAPI).
  - `pokemon` — el *proxy* hacia PokéAPI descrito arriba.

## Contrato resultante (v1, core)

| Ruta (PokéDex Manager API) | Origen del dato | Notas |
|---|---|---|
| `GET /api/v1/pokemon?search=&limit=&offset=` | Proxy cacheado a PokéAPI | Búsqueda/listado paginado para la pantalla "Pokédex" |
| `GET /api/v1/pokemon/{id_or_name}` | Proxy cacheado a PokéAPI | Detalle de un Pokémon |
| `GET /api/v1/collection` | Cloud SQL (propio) | Colección del usuario autenticado |
| `POST /api/v1/collection` | Cloud SQL (propio) | Agregar Pokémon a la colección (valida contra PokéAPI antes de guardar) |
| `PUT /api/v1/collection/{id}` | Cloud SQL (propio) | Editar apodo, nivel, notas, favorito |
| `DELETE /api/v1/collection/{id}` | Cloud SQL (propio) | Quitar de la colección |
| `POST /api/v1/collection/{id}/image` | Cloud Storage (propio) | Subir imagen/captura propia de esa entrada |

Si más adelante se necesita ingerir datos que PokéAPI no ofrece (por ejemplo,
resultados del análisis de imagen del feature bonus), esos datos son responsabilidad de
**nuestra** API — nunca se intentará "escribirle" a PokéAPI, que es de solo lectura y de
terceros.

Para probar el CRUD de la colección directamente (sin pasar por el frontend), ver
[`docs/POSTMAN_GUIDE.md`](POSTMAN_GUIDE.md).
