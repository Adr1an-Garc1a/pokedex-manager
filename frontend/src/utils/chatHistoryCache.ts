import type { ChatMessage, ChatThreadSummary } from "@/types";

const MESSAGES_PREFIX = "pokedex-manager:chat-history:";
const ACTIVE_THREAD_PREFIX = "pokedex-manager:chat-active-thread:";
const THREADS_PREFIX = "pokedex-manager:chat-threads:";

function messagesKey(userId: number, threadId: string): string {
  return `${MESSAGES_PREFIX}${userId}:${threadId}`;
}

function activeThreadKey(userId: number): string {
  return `${ACTIVE_THREAD_PREFIX}${userId}`;
}

function threadsKey(userId: number): string {
  return `${THREADS_PREFIX}${userId}`;
}

/**
 * Caché local (localStorage) del chat MCP, por cuenta de usuario Y por
 * conversación ("Iniciar nueva conversación" agrega conversaciones nuevas,
 * cada una con su propio historial — antes solo había UNA conversación por
 * usuario, ahora cada una necesita su propia entrada de caché).
 *
 * Por qué existe: el historial de cada conversación se guarda en Firestore
 * (`docs/BONUS_FEATURES.md`), pero si ese guardado está fallando (el 403 de
 * permisos ya reportado), sin este caché la conversación se vería vacía cada
 * vez que el usuario recarga la página o vuelve de otra sección — y peor,
 * Claude "olvidaría" todo el contexto anterior en cada mensaje nuevo, porque
 * el backend arma la memoria de la conversación a partir de Firestore. Por
 * eso el frontend manda esta copia local como `client_history` en cada
 * mensaje (`api/ai.ts`) — el backend la fusiona con lo que Firestore sí
 * tenga (`chat.py`, `_merge_history`) para que el contexto real de la
 * conversación sobreviva sin importar el estado de Firestore. Firestore
 * sigue siendo la fuente de verdad cuando responde bien; esto es un
 * respaldo que se fusiona con ella, nunca al revés.
 */
export function loadCachedChatHistory(userId: number, threadId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(messagesKey(userId, threadId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveCachedChatHistory(userId: number, threadId: string, messages: ChatMessage[]): void {
  try {
    localStorage.setItem(messagesKey(userId, threadId), JSON.stringify(messages));
  } catch {
    // localStorage puede fallar (modo incógnito con storage bloqueado, cuota
    // llena, etc.) — no es crítico, el resto del chat sigue funcionando igual.
  }
}

export function clearCachedChatHistory(userId: number, threadId: string): void {
  try {
    localStorage.removeItem(messagesKey(userId, threadId));
  } catch {
    // ver nota de arriba
  }
}

/** Qué conversación tenía abierta este usuario la última vez — para que al
 * volver a la sección de chat se reabra la misma, no siempre "ninguna". */
export function loadCachedActiveThreadId(userId: number): string | null {
  try {
    return localStorage.getItem(activeThreadKey(userId));
  } catch {
    return null;
  }
}

export function saveCachedActiveThreadId(userId: number, threadId: string | null): void {
  try {
    if (threadId) {
      localStorage.setItem(activeThreadKey(userId), threadId);
    } else {
      localStorage.removeItem(activeThreadKey(userId));
    }
  } catch {
    // ver nota de arriba
  }
}

/** Caché de la LISTA de conversaciones (títulos/fechas, sin mensajes) —
 * mismo motivo que el resto: que la lista se siga viendo si Firestore tarda
 * o falla momentáneamente. Firestore manda siempre la versión más reciente
 * cuando responde bien (ver PokedexChatPage: el servidor pisa al caché local
 * en caso de conflicto, nunca al revés). */
export function loadCachedThreadList(userId: number): ChatThreadSummary[] {
  try {
    const raw = localStorage.getItem(threadsKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveCachedThreadList(userId: number, threads: ChatThreadSummary[]): void {
  try {
    localStorage.setItem(threadsKey(userId), JSON.stringify(threads));
  } catch {
    // ver nota de arriba
  }
}
