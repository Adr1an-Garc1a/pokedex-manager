# Funcionalidades bonus de IA

Las tres funcionalidades bonus del enunciado están implementadas. Ninguna es
necesaria para el core de la app: si no se configuran (ver
[Configuración](#configuración) más abajo), sus endpoints responden `503` con
un mensaje claro y el resto de la aplicación sigue funcionando con
normalidad.

## Resumen

| # | Feature | Modelo | Endpoint |
|---|---|---|---|
| 1 | Identificar Pokémon por foto (Vision) | **Gemini 2.5 Flash** (Vertex AI / Model Garden) | `POST /api/v1/ai/vision/identify` |
| 2 | Chat sobre tu colección (MCP) | **Claude** (API de Anthropic) — `claude-haiku-4-5` por defecto, configurable a `claude-sonnet-5` | `POST /api/v1/ai/chat` |
| 3 | Insights de colección | **Gemini 2.5 Flash** (Vertex AI) | `GET /api/v1/ai/insights` |

## 1. Vision — identificar un Pokémon por foto

`POST /api/v1/ai/vision/identify` (multipart, campo `file`, requiere sesión) ·
`GET /api/v1/ai/vision/history` (historial de consultas pasadas, más reciente
primero, incluida la foto de cada una).

Flujo:

1. La foto se sube a Cloud Storage (o disco en local) con el mismo
   `StorageService` que usan las imágenes de la colección.
2. Se le pide a **Gemini 2.5 Flash** (SDK `google-genai`, apuntando a Vertex
   AI) que identifique el Pokémon y redacte una descripción, con salida JSON
   estructurada (`response_schema`) para no tener que parsear texto libre.
3. El modelo **no** decide datos duros de la Pokédex (tipos, generación de
   debut, hábitat, peso, altura, habilidades, cadena evolutiva) — eso se
   resuelve aparte contra **PokéAPI**, la misma fuente de verdad que usa el
   resto de la app, a partir del nombre que identificó Gemini:
   - Fuerte/débil contra qué tipo (`PokeAPIClient.get_type_matchups`,
     traducido a español).
   - Juego de primera aparición y zonas donde es fácil encontrarlo
     (`PokeAPIClient.get_species_info`, contra `/pokemon-species/{id}`). El
     estimado del propio modelo se usa solo como respaldo si el nombre
     identificado no se pudo resolver contra PokéAPI.
   - Peso y altura (convertidos a kg/metros) y habilidades.
   - Pre-evolución y evoluciones directas (`get_evolution_info`, recorriendo
     el árbol completo de `/evolution-chain/{id}`, que puede ramificarse
     como en Eevee).
   Si lo identificado no existe tal cual en PokéAPI, se devuelve igual la
   descripción del modelo, sin esos campos extra ni la opción de agregarlo a
   la colección con un id oficial.
4. La consulta (con la foto) se guarda en Firestore (`vision_history`, un
   documento por usuario con las últimas 50 consultas) de forma **best
   effort**: si el guardado falla, la identificación se muestra igual al
   usuario, marcada con `history_persisted: false`. El frontend además
   guarda cada identificación en `localStorage`
   (`utils/visionHistoryCache.ts`), por cuenta de usuario, y la fusiona con
   lo que devuelve el backend por `entry_id` — el historial se ve completo
   sin importar a qué otra sección navegue el usuario o si recarga la
   página. Firestore es siempre la fuente de verdad cuando responde bien; el
   caché local es solo un respaldo que se fusiona con ella, nunca al revés
   — por eso, si una consulta ya se guardó correctamente, cualquier bandera
   `history_persisted: false` vieja que hubiera quedado en el caché local se
   corrige sola en la siguiente carga.

Se usa Vertex AI / Model Garden (y no la API pública de Gemini) para
mantener todo dentro de la misma cuenta de servicio y facturación de GCP que
ya usa el resto del proyecto (Cloud Run, Cloud SQL, GCS) — un solo lugar
donde gestionar IAM y costos.

En el frontend, el resultado recién identificado se muestra como una tarjeta
con el detalle completo (foto, nombre, tipo, descripción, peso, altura,
habilidades, pre-evolución/evoluciones, juego de primera aparición, zonas
donde encontrarlo, fuerte/débil contra en español) y el botón de agregar a
la colección; debajo, el historial completo se muestra como tabla con esas
mismas columnas.

## 2. Chat MCP — Claude sobre tu colección

`POST /api/v1/ai/chat` (body `{"message": "...", "thread_id": "..." | null,
"client_history": [...]}`, requiere sesión), más un CRUD de
**conversaciones** (varias por usuario, no solo una):

- `GET /api/v1/ai/chat/threads` — todas tus conversaciones (id, título,
  fecha, cantidad de mensajes), más reciente primero.
- `POST /api/v1/ai/chat/threads` — crea una conversación vacía y devuelve su
  id ("Iniciar nueva conversación" en el frontend).
- `GET /api/v1/ai/chat/threads/{id}` — mensajes de una conversación puntual.
- `DELETE /api/v1/ai/chat/threads/{id}` — borra una conversación (las demás
  quedan intactas).

### Por qué Anthropic directo (y no Claude vía Vertex AI Model Garden)

GCP también ofrece modelos Claude en su Model Garden, lo que hubiera
mantenido todo "dentro de GCP" igual que Vision e Insights. Se eligió la
**API directa de Anthropic** en su lugar porque MCP es el protocolo de
Anthropic, y es ahí donde su soporte (incluidas las convenciones de
`tool_use` que usa esta app) está más probado y documentado. El costo de
esa decisión: se necesita una API key propia de Anthropic (ver
[Configuración](#configuración)), con facturación separada de GCP — es el
único paso manual de todo este bonus que no se resuelve con un script de
`gcloud`.

### Cómo funciona el servidor MCP

No hay un proceso ni contenedor MCP aparte — sería infraestructura extra sin
necesidad real para esta app. En su lugar, por cada mensaje de chat:

1. Se construye un servidor MCP (`FastMCP`, SDK oficial `mcp`) con tools ya
   "cerradas" sobre el usuario que está chateando y la sesión de base de
   datos de ese request: `list_my_collection`, `get_collection_stats`,
   `get_pokemon_info`. El servidor no puede leer la colección de otro
   usuario — ni el modelo puede pedírselo pasando un id, porque las tools no
   reciben `user_id` como parámetro.
2. Se conecta un `ClientSession` MCP real a ese servidor con streams **en
   memoria** (`mcp.shared.memory`, el mismo mecanismo que usa el propio SDK
   `mcp` en sus tests) — el mismo protocolo JSON-RPC de MCP, sin la capa de
   transporte de red que tendría un servidor MCP standalone (stdio o HTTP).
3. Se listan las tools del servidor y se traducen al formato `tools` de la
   API de Claude.
4. Se llama a Claude con el historial de esa conversación (`thread_id`) más
   el mensaje nuevo. Ese historial se arma fusionando lo guardado en
   Firestore con `client_history` — la copia local que manda el frontend en
   cada request (`utils/chatHistoryCache.ts`, en `localStorage` por cuenta
   de usuario y por conversación) — así el contexto real de la conversación
   sobrevive aunque el guardado en Firestore esté fallando para ese
   usuario. Si `thread_id` viene `null` (conversación nueva), se genera uno
   aquí mismo y se devuelve en la respuesta. Si Claude responde con
   `tool_use`, la tool se ejecuta a través del `ClientSession` MCP (nunca
   llamando directo a una función de Python) y el resultado se le devuelve
   como `tool_result`; esto se repite hasta que responde con texto final
   (tope de 5 iteraciones).
5. El turno completo se guarda en Firestore, en esa conversación, de forma
   **best effort**: si el guardado falla, la respuesta de Claude se entrega
   igual (`history_persisted: false`), solo que no queda registrada del
   lado del servidor — el frontend la sigue mostrando porque ya la tiene en
   su copia local.

### Varias conversaciones por usuario

Firestore guarda, por usuario, un **dict de conversaciones**
(`threads: {thread_id: {title, messages, created_at, updated_at}}`) en un
único documento — el volumen de un chat personal no justifica una
subcolección aparte con su propio paginado. El frontend
(`PokedexChatPage.tsx`) muestra la lista de conversaciones a un costado, con
un botón para iniciar una nueva y borrar cualquiera de las existentes sin
afectar al resto.

El título de cada conversación se genera con IA (**Claude Haiku 4.5, fijo y
barato, independiente de `ANTHROPIC_MODEL`**, el modelo que conversa) a
partir de su primer intercambio real, en vez de un simple recorte del
mensaje — así el título resume de qué se habló. Solo se pide una vez por
conversación (mientras no tenga todavía un título "real"); si esa llamada
falla, se cae de vuelta a un recorte simple del mensaje en vez de dejar la
conversación sin título.

```mermaid
sequenceDiagram
    participant U as Usuario
    participant FE as Frontend (+ caché local)
    participant BE as Backend (FastAPI)
    participant MCP as Servidor MCP (en memoria)
    participant C as Claude (Anthropic)
    participant FS as Firestore

    U->>FE: Escribe una pregunta (en la conversación activa)
    FE->>BE: POST /ai/chat {message, thread_id, client_history}
    BE->>FS: Cargar historial de ese thread_id (o generar uno nuevo si venía null)
    Note over BE: se fusiona con client_history
    BE->>MCP: Levantar servidor + ClientSession
    BE->>C: messages.create(tools=[...], historial fusionado + mensaje)
    alt Claude pide una tool
        C-->>BE: tool_use (ej. get_collection_stats)
        BE->>MCP: session.call_tool(...)
        MCP-->>BE: resultado real de la colección
        BE->>C: tool_result
        C-->>BE: respuesta final en texto
    else responde directo
        C-->>BE: respuesta final en texto
    end
    BE->>FS: Guardar turno en ese thread_id (sobre el historial ya fusionado)
    BE-->>FE: {reply, history, thread_id, history_persisted}
    FE->>FE: guarda `history` en localStorage (por usuario + thread_id)
```

### Diseño resiliente frente a fallos de Firestore

El chat y Vision están pensados para seguir funcionando aunque el guardado
en Firestore falle (por ejemplo, un problema temporal de permisos de IAM):

- Cualquier fallo de Firestore es **best effort**, nunca tumba la respuesta
  que ya generó el modelo — se entrega igual, marcada con
  `history_persisted: false`.
- El historial real de la conversación no depende solo de Firestore: se
  reconstruye fusionando lo guardado en el servidor con la copia local que
  manda el frontend, así el modelo nunca "olvida" el contexto por un fallo
  puntual de guardado.
- Crear una conversación nueva o identificar una foto son operaciones que no
  tienen nada que perder si el guardado a Firestore falla en ese instante:
  el `thread_id`/`entry_id` se genera igual y la entrada se "autocura" en
  Firestore la próxima vez que se guarde con éxito.
- Cualquier excepción que salga del bloque MCP (`anyio.TaskGroup`) se
  desenvuelve recursivamente antes de loguearla — Python 3.11+ agrupa esas
  excepciones (`ExceptionGroup`) y sin desenvolverlas se pierde el mensaje
  real de la causa.
- Al reenviar el turno del asistente a Claude en cada vuelta del loop de
  tools, cada bloque de contenido se serializa con
  `block.model_dump(exclude_none=True)` en vez de enumerar tipos a mano —
  así cualquier tipo de bloque que la API de Anthropic incluya (texto,
  `tool_use`, `thinking`, o los que agregue después) se reenvía
  correctamente sin tener que anticiparlo.

### Solución de problemas

Si `/ai/chat` o `/ai/vision/identify` responden con un error de Firestore
(`403 Missing or insufficient permissions`), revisa en orden:

1. **¿La revisión desplegada usa la service account correcta?**
   ```bash
   gcloud run services describe pokedex-manager-backend \
     --project=tu-proyecto-gcp --region=us-central1 \
     --format="value(spec.template.spec.serviceAccountName)"
   ```
   Debe imprimir `pokedex-manager-runtime@tu-proyecto-gcp.iam.gserviceaccount.com`.
   Si sale otra cosa, vuelve a correr `./08-deploy-backend.sh` — el script
   siempre pasa `--service-account`.
2. **¿El rol `roles/datastore.user` está asignado?**
   ```bash
   gcloud projects get-iam-policy tu-proyecto-gcp \
     --flatten="bindings[].members" \
     --filter="bindings.role:roles/datastore.user" \
     --format="table(bindings.role,bindings.members)"
   ```
   Si la service account de runtime no aparece, vuelve a correr
   `./02-service-accounts-iam.sh` (es idempotente).
3. **Espera la propagación de IAM** — un `add-iam-policy-binding` reciente
   puede tardar unos minutos en propagarse.
4. **¿Existe la base de Firestore?**
   ```bash
   gcloud firestore databases list --project=tu-proyecto-gcp
   ```
   Debe listar `(default)` con `type: FIRESTORE_NATIVE`. Si no existe, corre
   `./11-setup-firestore.sh`.
5. Si sigue el 403, revisa los logs del backend en Cloud Run (Cloud Console
   → Logging, o `gcloud run services logs read pokedex-manager-backend
   --region=us-central1 --limit=50`) — el traceback completo de
   `google.api_core` queda ahí.

### Por qué Firestore para el historial

Es la opción serverless natural de GCP para este dato: documentos de tamaño
variable, sin necesidad de joins ni transacciones complejas, cero
administración. Un documento por usuario en `mcp_conversations`, con un dict
`threads: {thread_id: {title, messages, created_at, updated_at}}` — una
entrada por conversación. El historial de Vision reutiliza el mismo patrón
en una colección separada, `vision_history` (un documento por usuario con
sus últimas 50 consultas, incluida la foto de cada una). Esto no contradice
la decisión de usar Cloud SQL para los datos core (ver
[`ARCHITECTURE.md`](ARCHITECTURE.md)): son dos tipos de dato distintos —
relacional con relaciones y agregaciones (colección) vs. documentos
semi-estructurados que crecen con el tiempo, sin joins (historial de chat e
identificaciones).

## 3. Insights de colección

`GET /api/v1/ai/insights` (requiere sesión y al menos 1 Pokémon en la
colección).

El análisis se basa en el **equipo efectivo** del usuario (hasta 6 Pokémon,
`app/services/team.py`):

- Si el usuario ya eligió un equipo a mano (`PUT /api/v1/collection/team`,
  botón **"Hacer de mi equipo"** en Mi Colección — solo aparece si tiene más
  de 6), Insights analiza exactamente esos.
- Si no ha elegido ninguno todavía, se usa el comportamiento por defecto:
  los primeros 6 que agregó (por fecha de creación) — así una colección de 6
  o menos nunca necesita elegir nada.

A Gemini 2.5 Flash se le manda ese resumen (nombres, tipos, apodos,
favoritos, niveles) y se le pide, con salida JSON estructurada:

- Un puntaje de 1 a 10 de qué tan bueno es ese equipo, con motivo específico
  — se muestra como una fila de 10 pokébolas, tantas "llenas" como el
  puntaje.
- Fortalezas y debilidades concretas de esos Pokémon (el prompt pide
  mencionarlos por nombre, no generalidades).
- Un equipo ideal de hasta 6, mezclando los que ya se tienen
  (`already_in_collection: true`) con sugerencias nuevas, resaltadas en el
  frontend con la razón de por qué convendrían.
- 2 alternativas por cada puesto del equipo ideal.
- Datos curiosos sobre los Pokémon de la colección.

Los nombres que menciona el modelo se resuelven contra PokéAPI para obtener
su sprite real — mismo principio que Vision: nunca se le pide al modelo una
URL de imagen, solo un nombre. El "equipo analizado" (el equipo efectivo) ni
siquiera se resuelve: sale directo de la colección en la base de datos.

### Elegir el equipo a mano

`PUT /api/v1/collection/team` (body `{"entry_ids": [...]}`, hasta 6 ids de
la propia colección del usuario) reemplaza por completo qué entradas cuentan
como equipo: pone `is_team_member=true` en las que llegan y `false` en el
resto de la colección de ese usuario. Un `entry_ids` vacío quita a todos del
equipo y vuelve al comportamiento por defecto (primeros 6 agregados). El
endpoint valida que ningún id pertenezca a otro usuario (`404` si no) y que
no se manden más de 6 (`422` si sí).

En el frontend (`CollectionPage.tsx`), el botón "Hacer de mi equipo" solo
aparece cuando la colección tiene más de 6 Pokémon — con 6 o menos, el
equipo siempre es toda la colección, así que no hay nada que elegir. Al
guardar un equipo nuevo se invalida también la query de Insights (misma
cuenta), así el próximo análisis usa el equipo recién elegido sin necesidad
de recargar la página.

## Aislamiento entre cuentas

Todas las queries del frontend que dependen de la cuenta con sesión iniciada
(insights, historial de Vision, hilos de chat, colección) escopan su caché
de React Query por `user.id` (`["ai", "insights", user.id]`, etc.), para que
cambiar de cuenta en la misma pestaña del navegador nunca reutilice una
respuesta cacheada de la cuenta anterior. Como defensa adicional,
`AuthContext.tsx` limpia todo el caché de React Query
(`queryClient.clear()`) al cerrar sesión. El backend, por su parte, nunca
mezcla datos entre cuentas — el aislamiento por `user.id` está cubierto con
tests dedicados (`backend/tests/test_ai.py`).

## Configuración

### A. Vertex AI / Gemini (Vision + Insights)

Ya viene listo si se desplegó con los scripts de `infra/gcp/`:
`aiplatform.googleapis.com` y el rol `roles/aiplatform.user` para la service
account de runtime se habilitan en `01-enable-apis.sh` /
`02-service-accounts-iam.sh`. En Cloud Run, el backend resuelve las
credenciales automáticamente (ADC del propio servicio). Para correrlo en
local:

```bash
gcloud auth application-default login
# y en .env:
GOOGLE_CLOUD_PROJECT=tu-proyecto-gcp
```

### B. Firestore (historial del chat y de Vision)

```bash
cd infra/gcp
export PROJECT_ID=tu-proyecto-gcp
./11-setup-firestore.sh
```

Crea la base de datos Firestore en modo Native para el proyecto (es una base
por proyecto, no algo que se despliegue por servicio). Si ya existía, el
script no hace nada.

### C. API key de Anthropic (chat MCP)

El único paso 100% manual de todo el bonus:

1. Crea una cuenta y una API key en
   [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
   (facturación separada de GCP).
2. Guárdala en Secret Manager:
   ```bash
   cd infra/gcp
   export PROJECT_ID=tu-proyecto-gcp
   export ANTHROPIC_API_KEY=sk-ant-...
   ./06-secrets.sh
   ```
3. Vuelve a desplegar el backend (`./08-deploy-backend.sh`, o con CI/CD un
   push a `main` — ver [`CI_CD.md`](CI_CD.md)) para que recoja el secreto.

Sin este paso, el resto de la app (incluidos Vision e Insights) funciona
igual; solo `/ai/chat` responde `503` hasta que exista el secreto.

## Modelos usados

- **Vision e Insights**: `gemini-2.5-flash` (configurable vía
  `GEMINI_MODEL`), facturado por Vertex AI/GCP — no por una API key de
  Gemini (ver más abajo).
- **Chat**: `claude-haiku-4-5-20251001` por defecto (configurable vía
  `ANTHROPIC_MODEL`). Se eligió Haiku 4.5 en vez de Sonnet 5 por costo
  ($1/$5 vs. $2/$10 por millón de tokens de entrada/salida) — soporta tool
  use (MCP) igual de bien para una colección personal de este tamaño, y su
  contexto (200K tokens) sobra para esta app. Cambiar a `claude-sonnet-5` es
  solo cambiar esta variable de entorno, sin tocar código. La lista de
  modelos vigentes y sus precios está en
  [platform.claude.com/docs/en/about-claude/models/model-ids-and-versions](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).

### ¿Dónde se factura Gemini si no hay una API key de Gemini?

Vision e Insights usan **Vertex AI** (Model Garden), no la API pública de
Gemini (la de [aistudio.google.com](https://aistudio.google.com), que usa
una API key tipo `AIzaSy...`). La autenticación es la cuenta de servicio de
Cloud Run (ADC), la misma que usa el backend para todo lo demás, con el rol
`roles/aiplatform.user`. Para ver consumo y costo, en la consola de GCP (no
en "API keys"):

- **Uso/cuota**: APIs & Services → Panel → "Vertex AI API" → pestaña
  Métricas, o Vertex AI → Model Garden → Gemini 2.5 Flash.
- **Costo**: Billing → Reports, filtrado por servicio "Vertex AI API".

## Probar estos endpoints con Postman

Los tres requieren el mismo Bearer token que el resto de la API (ver
[`POSTMAN_GUIDE.md`](POSTMAN_GUIDE.md)). Diferencias a tener en cuenta:

- `POST /ai/vision/identify` — Body → **form-data**, key `file` tipo
  **File**, no JSON.
- `GET /ai/vision/history` — sin body; devuelve un arreglo (vacío si nunca
  se ha usado Vision), más reciente primero.
- `POST /ai/chat` — Body raw JSON `{"message": "¿qué pokémon tengo?"}`.
  Puede tardar varios segundos (dos idas y vueltas: Claude → tool → Claude).
  Si `history_persisted` sale `false`, Claude respondió bien pero no se pudo
  guardar ese turno (ver [Solución de problemas](#solución-de-problemas)).
- `GET /ai/insights` — sin body; requiere al menos un Pokémon en la
  colección o responde `422`. Analiza el equipo efectivo (hasta 6 — ver
  [Elegir el equipo a mano](#elegir-el-equipo-a-mano)).
- `PUT /collection/team` — Body raw JSON `{"entry_ids": [1, 2, 3]}` (hasta 6
  ids, de tu propia colección). `404` si algún id no es tuyo, `422` si son
  más de 6.
