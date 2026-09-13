import { apiClient } from "@/api/client";
import type {
  ChatMessage,
  ChatResponse,
  ChatThreadSummary,
  CollectionInsights,
  PokemonVisionResult,
} from "@/types";

// --- 1. Vision: identificar un Pokémon por foto ---------------------------

export async function identifyPokemonImage(file: File): Promise<PokemonVisionResult> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<PokemonVisionResult>(
    "/ai/vision/identify",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

export async function getVisionHistory(): Promise<PokemonVisionResult[]> {
  const { data } = await apiClient.get<PokemonVisionResult[]>("/ai/vision/history");
  return data;
}

// --- 2. Chat MCP con Claude (modelo configurable en el backend) -----------
//
// El chat soporta varias conversaciones ("hilos") por usuario: la lista de
// TODAS las conversaciones (sin mensajes) se pide con `listChatThreads`,
// "Iniciar nueva conversación" con `createChatThread`, los mensajes de una en
// particular con `getChatThreadMessages`, y `sendChatMessage` manda un
// mensaje dentro de una conversación (o inicia una nueva de facto si se le
// manda `threadId: null`).

export async function listChatThreads(): Promise<ChatThreadSummary[]> {
  const { data } = await apiClient.get<ChatThreadSummary[]>("/ai/chat/threads");
  return data;
}

export async function createChatThread(): Promise<ChatThreadSummary> {
  const { data } = await apiClient.post<ChatThreadSummary>("/ai/chat/threads");
  return data;
}

export async function getChatThreadMessages(threadId: string): Promise<ChatMessage[]> {
  const { data } = await apiClient.get<ChatMessage[]>(`/ai/chat/threads/${threadId}`);
  return data;
}

export async function deleteChatThread(threadId: string): Promise<void> {
  await apiClient.delete(`/ai/chat/threads/${threadId}`);
}

/**
 * `threadId`: la conversación a continuar (null si todavía no existe
 * ninguna — el backend crea una nueva y su id vuelve en la respuesta).
 * `clientHistory`: la copia local (localStorage) de ESA conversación — se
 * manda siempre que se tenga, para que el backend pueda fusionarla con lo
 * que Firestore tenga guardado y así el contexto de la conversación
 * sobreviva aunque ese guardado esté fallando (ver chatHistoryCache.ts).
 */
export async function sendChatMessage(
  message: string,
  threadId: string | null,
  clientHistory: ChatMessage[] = []
): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/ai/chat", {
    message,
    thread_id: threadId,
    client_history: clientHistory,
  });
  return data;
}

// --- 3. Insights de colección -----------------------------------------------

export async function getCollectionInsights(): Promise<CollectionInsights> {
  const { data } = await apiClient.get<CollectionInsights>("/ai/insights");
  return data;
}
