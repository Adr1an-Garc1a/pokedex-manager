# Funcionalidades bonus de IA

Las tres funcionalidades bonus del enunciado están implementadas. Ninguna es
necesaria para el core de la app: si no se configuran (ver
[Configuración](#configuración) más abajo), sus endpoints responden `503` con
un mensaje claro y el resto de la aplicación sigue funcionando con
normalidad.

## Resumen

| # | Feature | Modelo | Endpoint |
|---|---|---|---|
| 1 | Integración con LLMs — identificar Pokémon por foto (Vision) | **Gemini 2.5 Flash** (Vertex AI / Model Garden) | `POST /api/v1/ai/vision/identify` |
| 2 | Integración MCP — chat sobre tu colección | **Claude** (API de Anthropic) — `claude-haiku-4-5` por defecto, configurable a `claude-sonnet-5` | `POST /api/v1/ai/chat` |
| 3 | Insights de colección | **Gemini 2.5 Flash** (Vertex AI) | `GET /api/v1/ai/insights` |

## 1. Vision — identificar un Pokémon por foto

**Qué es:** subes una foto y la app identifica de qué Pokémon se trata,
mostrando su tipo, ventajas/desventajas, peso, altura, habilidades y cadena
evolutiva; queda un historial de las identificaciones pasadas.

**Cómo funciona:** la foto se sube a Cloud Storage y se le pide a **Gemini
2.5 Flash** (Vertex AI, SDK `google-genai`) que identifique el Pokémon con
salida JSON estructurada. El modelo solo aporta el nombre — los datos "duros"
(tipos, ventajas/desventajas, peso/altura, habilidades, evoluciones, juego de
primera aparición) se resuelven aparte contra **PokéAPI**, para no depender
de que el modelo los recuerde bien. Cada consulta (con la foto) se guarda en
Firestore de forma *best effort* (si falla, la identificación se muestra
igual, marcada `history_persisted: false`); el frontend además cachea el
historial en `localStorage` por cuenta de usuario como respaldo.

**Dónde está en el código:**
- Backend: `app/api/v1/ai.py` (endpoints `/vision/identify` y `/vision/history`), `app/services/ai/vision.py` (llamada a Gemini + resolución contra PokéAPI).
- Frontend: `pages/VisionPage.tsx`, `utils/visionHistoryCache.ts`.

## 2. Chat MCP — Claude sobre tu colección

**Qué es:** un chat con Claude que responde preguntas sobre tu colección real
("¿qué Pokémon de tipo fuego tengo?", "¿mi equipo actual le gana a uno de
tipo agua?"), con varias conversaciones por usuario (crear, listar, borrar) y
títulos generados automáticamente.

**Cómo funciona:** por cada mensaje se construye, en memoria, un servidor MCP
(`FastMCP`) con tools ya "cerradas" sobre el usuario y la sesión de DB de ese
request — el modelo nunca puede pedir la colección de otro usuario, porque
las tools no reciben `user_id` como parámetro. Las tools disponibles son
`list_my_collection` (toda la colección), `get_my_team` (el equipo efectivo,
hasta 6 — el mismo que usa Insights), `get_collection_stats` y
`get_pokemon_info`. `list_my_collection` y `get_my_team` son tools separadas
a propósito: "colección" (todo) y "equipo" (hasta 6) no son lo mismo, y el
system prompt le instruye a Claude usar siempre `get_my_team` para preguntas
sobre el equipo (nunca adivinar a partir de favoritos), así el chat siempre
refleja el mismo equipo que ve Insights. El servidor se conecta a Claude vía
un `ClientSession` MCP con streams en memoria (`mcp.shared.memory`) — mismo
protocolo JSON-RPC de MCP, sin transporte de red. El historial de cada
conversación se guarda en Firestore de forma *best effort*, fusionado con una
copia local que manda el frontend (`localStorage`) para no perder contexto
si el guardado falla.

**Dónde está en el código:**
- Backend: `app/api/v1/ai.py` (endpoints `/chat` y `/chat/threads*`), `app/services/ai/chat.py` (loop de tool-use con Claude, `_SYSTEM_PROMPT_TEMPLATE`), `app/services/ai/mcp_tools.py` (`build_mcp_server`, las tools).
- Frontend: `pages/PokedexChatPage.tsx`, `utils/chatHistoryCache.ts`.

## 3. Insights de colección

**Qué es:** un análisis con IA de tu equipo actual (hasta 6 Pokémon):
puntaje del 1 al 10, fortalezas y debilidades concretas, un equipo ideal
(mezclando lo que ya tienes con sugerencias nuevas) y datos curiosos. Un
botón **"🔄 Actualizar insights"** permite recalcular el análisis en
cualquier momento (por ejemplo, después de cambiar de equipo).

**Cómo funciona:** el análisis se basa en el **equipo efectivo** del usuario
(`app/services/team.py::get_effective_team`) — el equipo que eligió a mano
en Mi Colección (botón "Hacer de mi equipo", solo visible con más de 6 en la
colección) o, por defecto, los primeros 6 que agregó. Ese resumen (nombres,
tipos, apodos, favoritos, niveles) se le manda a **Gemini 2.5 Flash**, que
devuelve el análisis en JSON estructurado; los nombres que menciona se
resuelven contra PokéAPI para obtener su sprite real. Elegir un equipo nuevo
(`PUT /api/v1/collection/team`) invalida también la query de Insights en el
frontend, y el botón de refresco fuerza un `refetch()` de React Query bajo la
misma `queryKey` sin depender de que la página se vuelva a montar.

**Dónde está en el código:**
- Backend: `app/api/v1/ai.py` (`/insights`), `app/services/ai/insights.py` (prompt + llamada a Gemini), `app/services/team.py` (`get_effective_team`), `app/api/v1/collection.py` (`PUT /collection/team`).
- Frontend: `pages/InsightsPage.tsx`, `pages/CollectionPage.tsx` (selección de equipo).

## Aislamiento entre cuentas

Todas las queries del frontend que dependen de la cuenta con sesión iniciada
(insights, historial de Vision, hilos de chat, colección) escopan su caché de
React Query por `user.id`, y `AuthContext.tsx` limpia todo el caché
(`queryClient.clear()`) al cerrar sesión. El backend nunca mezcla datos entre
cuentas — cubierto con tests dedicados (`backend/tests/test_ai.py`).

## Configuración

Los tres pasos siguientes ya se resuelven solos si el proyecto se desplegó
con los scripts de `infra/gcp/` (ver [`GCP_DEPLOYMENT.md`](GCP_DEPLOYMENT.md)):

- **A. Vertex AI / Gemini** (Vision + Insights): habilitado por
  `01-enable-apis.sh` / `02-service-accounts-iam.sh` (`aiplatform.googleapis.com`
  + rol `roles/aiplatform.user`). Cloud Run resuelve las credenciales solo
  (ADC de la service account de runtime).
- **B. Firestore** (historial de chat y de Vision): `./11-setup-firestore.sh`
  crea la base en modo Native (una por proyecto).
- **C. API key de Anthropic** (chat MCP) — el único paso 100% manual:
  1. Crear una API key en [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) (facturación separada de GCP).
  2. Guardarla en Secret Manager: `export ANTHROPIC_API_KEY=sk-ant-... && ./06-secrets.sh`.
  3. Redesplegar el backend para que recoja el secreto (`./08-deploy-backend.sh`, o vía CI/CD).

Sin el paso C, el resto de la app (incluidos Vision e Insights) funciona
igual; solo `/ai/chat` responde `503` hasta que exista el secreto.

## Modelos usados

- **Vision e Insights**: `gemini-2.5-flash` (configurable vía `GEMINI_MODEL`),
  facturado por Vertex AI — no por una API key de Gemini pública.
- **Chat**: `claude-haiku-4-5-20251001` por defecto (configurable vía
  `ANTHROPIC_MODEL`, por ejemplo a `claude-sonnet-5`), elegido por costo y
  porque el contexto (200K tokens) sobra para esta app. El título de cada
  conversación también se genera con Claude Haiku 4.5, fijo, independiente
  del modelo de chat configurado.

## Probar estos endpoints con Postman

Los tres requieren el mismo Bearer token que el resto de la API — ver
[`POSTMAN_GUIDE.md`](POSTMAN_GUIDE.md). Diferencias a tener en cuenta:

- `POST /ai/vision/identify` — Body → **form-data**, key `file` tipo **File**, no JSON.
- `POST /ai/chat` — Body raw JSON `{"message": "¿qué pokémon tengo?"}`. Puede tardar varios segundos (dos idas y vueltas: Claude → tool → Claude).
- `GET /ai/insights` — sin body; requiere al menos un Pokémon en la colección o responde `422`.
- `PUT /collection/team` — Body raw JSON `{"entry_ids": [1, 2, 3]}` (hasta 6 ids, de tu propia colección). `404` si algún id no es tuyo, `422` si son más de 6.
