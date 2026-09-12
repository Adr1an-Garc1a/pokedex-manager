import { apiClient } from "@/api/client";
import type { CollectionEntry, CollectionEntryInput, CollectionStats } from "@/types";

export async function listMyCollection(): Promise<CollectionEntry[]> {
  const { data } = await apiClient.get<CollectionEntry[]>("/collection");
  return data;
}

export async function getCollectionStats(): Promise<CollectionStats> {
  const { data } = await apiClient.get<CollectionStats>("/collection/stats");
  return data;
}

export async function addToCollection(
  payload: CollectionEntryInput
): Promise<CollectionEntry> {
  const { data } = await apiClient.post<CollectionEntry>("/collection", payload);
  return data;
}

export async function updateCollectionEntry(
  id: number,
  payload: Partial<CollectionEntryInput>
): Promise<CollectionEntry> {
  const { data } = await apiClient.put<CollectionEntry>(`/collection/${id}`, payload);
  return data;
}

export async function deleteCollectionEntry(id: number): Promise<void> {
  await apiClient.delete(`/collection/${id}`);
}

export async function uploadEntryImage(id: number, file: File): Promise<CollectionEntry> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post<CollectionEntry>(
    `/collection/${id}/image`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}
