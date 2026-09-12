# Decisión: cómo se resuelve el tema de "la API"

Este documento responde directamente al punto abierto: *"El tema de la API externa
PokéAPI la verdad es que esta abierto... a mi se me ocurre maybe crear una API llamada
PokeAPI para meter datos"*.

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

### Por qué esta es la opción correcta para este caso de uso

1. **No reinventa lo que ya existe y es gratuito.** Levantar una réplica completa de
   PokéAPI (con ~1300 especies, formas, movimientos, cadenas de evolución) sería
   trabajo desperdiciado en una prueba de 3 días y además quedaría desactualizado.
2. **Evita el problema de nombres.** Si "nuestra" API también se llamara PokeAPI,
   cualquier lector (o el propio equipo evaluador) tendría que adivinar todo el tiempo
   de cuál de las dos se está hablando. Por eso el backend propio se nombra
   explícitamente **PokéDex Manager API**.
3. **Cumple el requisito literal del enunciado** ("Integración con API externa —
   PokéAPI"): la integración es real (llamadas HTTP salientes, manejo de errores,
   normalización de datos), no una simulación.
4. **Deja la puerta abierta a resiliencia**: los campos relevantes de un Pokémon
   (nombre, sprite, tipos) se copian a la fila de `collection_entries` cuando el
   usuario lo agrega a su colección, así que si PokéAPI está caída o cambia de forma,
   la colección guardada del usuario sigue siendo consistente.
5. **Escala naturalmente a los features bonus**: el mismo cliente cacheado de PokéAPI
   es el que alimentaría, por ejemplo, el LMM (para verificar que el Pokémon detectado
   en una foto existe y completar sus stats reales) o el motor de insights.

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
