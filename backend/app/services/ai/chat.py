"""Bonus 2 — Orquesta el chat "¿Tienes dudas de tu Pokédex?": un modelo de
Claude (Anthropic, configurable vía ANTHROPIC_MODEL — por defecto
claude-haiku-4-5, mucho más barato que Sonnet 5 y con soporte de tool use
igual de bueno para esta app) respondiendo con acceso, vía MCP, a la
colección real del usuario.

Flujo por cada mensaje del usuario:
  1. Se levanta un servidor MCP en memoria (mcp_tools.build_mcp_server),
     ya cerrado sobre ESTE usuario y ESTA sesión de DB.
  2. Se conecta un ClientSession MCP real a ese servidor (mismo protocolo
     JSON-RPC que usaría un cliente MCP contra un servidor remoto).
  3. Se listan las tools del servidor y se traducen al formato de "tools" de
     la API de Claude.
  4. Se llama a Claude con el historial de la conversación (recuperado de
     Firestore) + el mensaje nuevo. Si Claude decide usar una tool
     (stop_reason == "tool_use"), se ejecuta vía el ClientSession MCP (no
     directamente en Python) y su resultado se le devuelve a Claude como
     "tool_result", repitiendo hasta que responda con texto final.
  5. El turno completo (mensaje del usuario + respuesta final) se persiste
     en Firestore, en la conversación (`thread_id`) que se venga usando — el
     usuario puede tener varias conversaciones guardadas a la vez ("Iniciar
     nueva conversación") y retomar cualquiera de ellas más tarde. Si esa
     conversación todavía no tiene un título "real" (una recién creada, o
     una vieja que se quedó pegada en el genérico "Nueva conversación"), se
     le pide uno a Claude Haiku a partir de este primer intercambio real
     (`_generate_thread_title` — modelo fijo y barato, independiente de
     ANTHROPIC_MODEL) en vez de solo truncar el primer mensaje.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from fastapi import HTTPException
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.services.ai.mcp_tools import build_mcp_server
from app.services.firestore_client import DEFAULT_THREAD_TITLE, append_turn, get_thread

settings = get_settings()
logger = logging.getLogger("pokedex_manager.ai.chat")

_MAX_TOOL_ITERATIONS = 5
_MAX_HISTORY_MESSAGES = 20  # últimos N mensajes que se le mandan a Claude como contexto

# Modelo FIJO para generar el título de una conversación (independiente de
# ANTHROPIC_MODEL, el que se use para el chat en sí) — resumir un intercambio
# en <=6 palabras es una tarea trivial que no necesita el modelo "grande" que
# se esté usando para conversar; usar siempre el más barato disponible tiene
# sentido sin importar qué tan bueno (y caro) sea el modelo principal.
_TITLE_MODEL = "claude-haiku-4-5-20251001"
_TITLE_MAX_TOKENS = 20
_TITLE_SYSTEM_PROMPT = (
    "Resume esta conversación de un chat sobre una colección de Pokémon en un título de "
    "MÁXIMO 6 palabras, en español, sin comillas ni punto final. Responde solo con el "
    "título, nada más de texto."
)

_SYSTEM_PROMPT_TEMPLATE = (
    "Eres el asistente de PokéDex Manager, ayudando a {user_name} a explorar y "
    "entender SU colección personal de Pokémon. Tienes herramientas (tools) para "
    "leer su colección real, sus estadísticas, su equipo actual, y consultar datos "
    "oficiales de cualquier Pokémon en la Pokédex — úsalas siempre que la pregunta "
    "lo requiera, en vez de inventar datos. IMPORTANTE: 'colección' y 'equipo' NO "
    "son lo mismo — la colección es TODOS los Pokémon que tiene, el equipo es un "
    "subconjunto de hasta 6 (elegido a mano por el usuario en la app, o por defecto "
    "los primeros 6 que agregó). Cuando pregunte por su equipo (por ejemplo 'mi "
    "equipo', '¿con qué equipo tengo?', 'revisa mi colección, ahí está mi equipo', "
    "'¿puedo pasar el juego con esto?'), usa la tool get_my_team — nunca adivines "
    "el equipo a partir de favoritos, nivel, ni ninguna otra señal de "
    "list_my_collection. Responde siempre en español, en un tono amigable y "
    "entusiasta (como un compañero entrenador Pokémon), y de forma concisa."
)


def _root_cause(exc: BaseException) -> BaseException:
    """`create_connected_server_and_client_session` corre el servidor MCP y el
    cliente dentro de un `anyio.TaskGroup` — desde Python 3.11, CUALQUIER
    excepción que salga del bloque `async with ... as session:` (una API key
    inválida, un timeout de red hacia Anthropic, lo que sea) llega envuelta
    en un `ExceptionGroup("unhandled errors in a TaskGroup", [la_real])`.

    Sin desenvolverla, el mensaje que ve el usuario es siempre el mismo,
    genérico e inútil: "unhandled errors in a TaskGroup (1 sub-exception)" —
    sin importar cuál sea la causa real. Esta función se desenvuelve
    recursivamente hasta encontrar la excepción real de más adentro, para
    poder loguearla y devolverla en el detalle del error.
    """
    seen = exc
    while isinstance(seen, BaseExceptionGroup) and seen.exceptions:
        seen = seen.exceptions[0]
    return seen


def _tool_result_to_text(result) -> str:
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts) if parts else "(sin contenido)"


def _merge_history(*sources: list[dict]) -> list[dict]:
    """Combina varias listas de mensajes (típicamente: lo que Firestore tiene
    guardado + lo que el frontend mandó como su propia copia local) en una
    sola, sin duplicados (por rol+contenido+timestamp) y en orden
    cronológico.

    Por qué existe: si el guardado en Firestore ha estado fallando (el 403
    de permisos reportado), la memoria de la conversación que el backend le
    da a Claude en cada mensaje nuevo sería SIEMPRE vacía, así que Claude
    "olvidaría" todo entre un mensaje y el siguiente aunque el usuario esté
    en la misma conversación — el chat "funciona" pero no mantiene contexto.
    El frontend guarda su propia copia (ver utils/chatHistoryCache.ts) y la
    manda en cada request (`client_history`); aquí se fusiona con lo que
    Firestore sí tenga, así que el contexto real de la conversación sobrevive
    aunque el guardado del lado del servidor esté fallando.
    """
    seen: set[tuple] = set()
    merged: list[dict] = []
    for source in sources:
        for msg in source:
            key = (msg.get("role"), msg.get("content"), msg.get("ts"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(msg)
    merged.sort(key=lambda m: m.get("ts") or "")
    return merged


async def _generate_thread_title(
    anthropic_client: AsyncAnthropic, user_message: str, assistant_reply: str
) -> str | None:
    """Le pide a Claude Haiku (modelo fijo y barato, ver `_TITLE_MODEL`) un
    título corto para la conversación, a partir de un intercambio real
    (mensaje del usuario + respuesta de Claude) — en vez de simplemente
    recortar el mensaje del usuario a 40 caracteres (`firestore_client._make_title`),
    que no resume nada, solo trunca.

    Nunca lanza: si esta llamada falla por lo que sea (red, la API de
    Anthropic caída, lo que sea), el llamador (`run_pokedex_chat`) se cae de
    vuelta al recorte simple — un título para la conversación jamás debe
    tumbar el chat en sí ni dejarla sin ningún título."""
    try:
        response = await anthropic_client.messages.create(
            model=_TITLE_MODEL,
            max_tokens=_TITLE_MAX_TOKENS,
            system=_TITLE_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Usuario: {user_message}\nAsistente: {assistant_reply}",
                }
            ],
        )
        title = "".join(
            getattr(block, "text", "") for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        title = title.strip("\"'.").strip()
        return title[:60] or None
    except Exception:
        logger.warning("No se pudo generar un título con IA para la conversación nueva", exc_info=True)
        return None


async def run_pokedex_chat(
    *,
    db: Session,
    user: User,
    user_message: str,
    client_history: list[dict] | None = None,
    thread_id: str | None = None,
) -> tuple[str, list[dict], bool, str]:
    """`thread_id`: conversación a continuar. Si es None (usuario sin ninguna
    conversación todavía, o el frontend pide explícitamente una nueva sin
    pre-crearla), se genera un ID nuevo aquí mismo — la conversación se crea
    "de facto" en Firestore la primera vez que `append_turn` la guarda (con un
    título generado por IA a partir de este mismo mensaje, ver más abajo)."""
    thread_id = thread_id or uuid.uuid4().hex
    thread = await get_thread(user.id, thread_id)
    history = _merge_history(thread.get("messages", []), client_history or [])
    recent_history = history[-_MAX_HISTORY_MESSAGES:]
    # Si esta conversación todavía no tiene un título "real" (nunca ha tenido
    # ninguno, o se quedó en el genérico que le pone "Iniciar nueva
    # conversación"), se le genera uno con IA una vez que Claude responda —
    # así el título refleja de qué se habló, no solo el primer mensaje
    # truncado. Una vez que tiene un título real, no se le vuelve a pedir uno
    # nuevo en cada mensaje (serían llamadas de más, sin necesidad).
    needs_title = thread.get("title") in (None, DEFAULT_THREAD_TITLE)

    server = build_mcp_server(db=db, user=user)

    try:
        anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        async with create_connected_server_and_client_session(server) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            anthropic_tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                }
                for t in tools_result.tools
            ]

            messages: list[dict] = [
                {"role": m["role"], "content": m["content"]} for m in recent_history
            ]
            messages.append({"role": "user", "content": user_message})

            final_text = ""
            for _ in range(_MAX_TOOL_ITERATIONS):
                response = await anthropic_client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=1024,
                    system=_SYSTEM_PROMPT_TEMPLATE.format(user_name=user.name),
                    messages=messages,
                    tools=anthropic_tools,
                )

                text_blocks = [b.text for b in response.content if b.type == "text"]
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

                if not tool_use_blocks:
                    final_text = "\n".join(text_blocks).strip()
                    break

                # Se re-envía el turno del asistente TAL CUAL (con `model_dump`,
                # no reconstruido a mano) para que Claude mantenga el contexto
                # de qué tool pidió y por qué.
                #
                # Bug real encontrado en producción: antes se reconstruía cada
                # bloque a mano asumiendo que solo existían "text" y
                # "tool_use" — pero Claude Sonnet 5 a veces incluye bloques
                # "thinking" (razonamiento) en su respuesta, y el `else` de
                # esa reconstrucción intentaba leer `b.id` de un
                # `ThinkingBlock`, que no tiene ese atributo
                # ("'ThinkingBlock' object has no attribute 'id'"). Al
                # reventar DENTRO del `async with` de la sesión MCP, ese error
                # llegaba envuelto en el ExceptionGroup de anyio (ver
                # `_root_cause` arriba) — por eso antes solo se veía el
                # mensaje genérico de la TaskGroup, nunca la causa real.
                # `model_dump(exclude_none=True)` serializa cualquier tipo de
                # bloque (texto, tool_use, thinking, y los que Anthropic
                # agregue después) sin tener que enumerarlos a mano.
                messages.append(
                    {
                        "role": "assistant",
                        "content": [block.model_dump(exclude_none=True) for block in response.content],
                    }
                )

                tool_results = []
                for tool_use in tool_use_blocks:
                    result = await session.call_tool(tool_use.name, tool_use.input or {})
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": _tool_result_to_text(result),
                            "is_error": result.isError,
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
            else:
                final_text = (
                    "No pude terminar de procesar tu pregunta (demasiados pasos). "
                    "Intenta reformularla de forma más simple."
                )
    except HTTPException:
        raise
    except Exception as exc:
        root = _root_cause(exc)
        logger.exception(
            "Fallo en el chat MCP (causa real desenvuelta: %r)", root
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "El chat con IA no está disponible ahora mismo. Verifica que "
                f"ANTHROPIC_API_KEY sea válida. Detalle técnico: {root}"
            ),
        ) from exc

    if not final_text:
        final_text = "No obtuve una respuesta del modelo, intenta de nuevo."

    # Título con IA (Claude Haiku, ver `_generate_thread_title`) solo cuando
    # hace falta — evita gastar una llamada extra en cada mensaje una vez que
    # la conversación ya tiene un título real.
    thread_title = await _generate_thread_title(anthropic_client, user_message, final_text) if needs_title else None

    # Guardar el turno en Firestore es "best effort" desde la perspectiva del
    # usuario: si falla (permisos, Firestore no disponible, etc.), Claude ya
    # respondió correctamente y esa respuesta se le entrega igual — solo no
    # queda guardada para la próxima vez. Antes, un fallo acá tumbaba TODA la
    # respuesta con un 503 aunque el chat sí hubiera funcionado.
    try:
        # `base_history=history` (el ya fusionado con lo que mandó el
        # frontend) en vez de dejar que append_turn relea Firestore por su
        # cuenta: así, si Firestore se había quedado corto por fallos
        # anteriores, este guardado "autocura" el documento con la versión
        # más completa que se tenga, en vez de perpetuar el hueco.
        updated_history = await append_turn(
            user.id,
            thread_id,
            user_message=user_message,
            assistant_reply=final_text,
            base_history=history,
            title=thread_title,
        )
        persisted = True
    except HTTPException as exc:
        logger.warning(
            "El chat funcionó pero no se pudo guardar el turno en Firestore: %s", exc.detail
        )
        now = datetime.now(timezone.utc).isoformat()
        updated_history = history + [
            {"role": "user", "content": user_message, "ts": now},
            {"role": "assistant", "content": final_text, "ts": now},
        ]
        persisted = False

    return final_text, updated_history, persisted, thread_id
