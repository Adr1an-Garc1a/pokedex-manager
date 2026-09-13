"""Bonus 2 — Orquesta el chat "¿Tienes dudas de tu Pokédex?": Claude Sonnet 5
(Anthropic) respondiendo con acceso, vía MCP, a la colección real del
usuario.

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
     en Firestore.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from fastapi import HTTPException
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.services.ai.mcp_tools import build_mcp_server
from app.services.firestore_client import append_turn, get_conversation

settings = get_settings()
logger = logging.getLogger("pokedex_manager.ai.chat")

_MAX_TOOL_ITERATIONS = 5
_MAX_HISTORY_MESSAGES = 20  # últimos N mensajes que se le mandan a Claude como contexto

_SYSTEM_PROMPT_TEMPLATE = (
    "Eres el asistente de PokéDex Manager, ayudando a {user_name} a explorar y "
    "entender SU colección personal de Pokémon. Tienes herramientas (tools) para "
    "leer su colección real, sus estadísticas, y consultar datos oficiales de "
    "cualquier Pokémon en la Pokédex — úsalas siempre que la pregunta lo requiera, "
    "en vez de inventar datos. Responde siempre en español, en un tono amigable y "
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


async def run_pokedex_chat(
    *, db: Session, user: User, user_message: str
) -> tuple[str, list[dict], bool]:
    history = await get_conversation(user.id)
    recent_history = history[-_MAX_HISTORY_MESSAGES:]

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

                # Se re-envía el turno del asistente tal cual (texto + tool_use)
                # para que Claude mantenga el contexto de qué tool pidió y por qué.
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": b.text}
                            if b.type == "text"
                            else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                            for b in response.content
                        ],
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
            "Fallo en el chat MCP con Claude Sonnet 5 (causa real desenvuelta: %r)", root
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

    # Guardar el turno en Firestore es "best effort" desde la perspectiva del
    # usuario: si falla (permisos, Firestore no disponible, etc.), Claude ya
    # respondió correctamente y esa respuesta se le entrega igual — solo no
    # queda guardada para la próxima vez. Antes, un fallo acá tumbaba TODA la
    # respuesta con un 503 aunque el chat sí hubiera funcionado.
    try:
        updated_history = await append_turn(
            user.id, user_message=user_message, assistant_reply=final_text
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

    return final_text, updated_history, persisted
