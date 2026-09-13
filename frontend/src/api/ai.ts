import { apiClient } from "@/api/client";
import type {
  ChatMessage,
  ChatResponse,
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

// --- 2. Chat MCP con Claude Sonnet 5 ---------------------------------------

export async function getChatHistory(): Promise<ChatMessage[]> {
  const { data } = await apiClient.get<ChatMessage[]>("/ai/chat/history");
  return data;
}

/**
 * `clientHistory`: la copia local (localStorage) de la conversación — se
 * manda siempre que se tenga, para que el backend pueda fusionarla con lo
 * que Firestore tenga guardado y así el contexto de la conversación
 * sobreviva aunque ese guardado esté fallando (ver chatHistoryCache.ts).
 */
export async function sendChatMessage(
  message: string,
  clientHistory: ChatMessage[] = []
): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/ai/chat", {
    message,
    client_history: clientHistory,
  });
  return data;
}

export async function resetChatHistory(): Promise<void> {
  await apiClient.delete("/ai/chat/history");
}

// --- 3. Insights de colección -----------------------------------------------

export async function getCollectionInsights(): Promise<CollectionInsights> {
  const { data } = await apiClient.get<CollectionInsights>("/ai/insights");
  return data;
}
