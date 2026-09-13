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
