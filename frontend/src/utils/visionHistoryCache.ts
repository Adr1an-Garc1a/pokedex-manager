import type { PokemonVisionResult } from "@/types";

const STORAGE_PREFIX = "pokedex-manager:vision-history:";
const MAX_CACHED_ENTRIES = 50;

function storageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}


export function loadCachedVisionHistory(userId: number): PokemonVisionResult[] {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveCachedVisionHistory(userId: number, entries: PokemonVisionResult[]): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(entries.slice(0, MAX_CACHED_ENTRIES)));
  } catch {
    // localStorage puede fallar (modo incógnito con storage bloqueado, cuota

  }
}
