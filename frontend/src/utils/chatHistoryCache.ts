import type { ChatMessage } from "@/types";

const STORAGE_PREFIX = "pokedex-manager:chat-history:";

function storageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}

/**
 * Caché local (localStorage) de la conversación del chat MCP, por cuenta de
 * usuario.
 *
 * Por qué existe: el historial de este chat se guarda en Firestore
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
export function loadCachedChatHistory(userId: number): ChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveCachedChatHistory(userId: number, messages: ChatMessage[]): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(messages));
  } catch {
    // localStorage puede fallar (modo incógnito con storage bloqueado, cuota
    // llena, etc.) — no es crítico, el resto del chat sigue funcionando igual.
  }
}

export function clearCachedChatHistory(userId: number): void {
  try {
    localStorage.removeItem(storageKey(userId));
  } catch {
    // ver nota de arriba
  }
}
