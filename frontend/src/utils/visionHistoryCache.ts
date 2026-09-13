import type { PokemonVisionResult } from "@/types";

const STORAGE_PREFIX = "pokedex-manager:vision-history:";
const MAX_CACHED_ENTRIES = 50;

function storageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}

/**
 * Caché local (localStorage) del historial de identificaciones de Vision,
 * por cuenta de usuario.
 *
 * Por qué existe: antes, lo identificado en la sesión solo vivía en el
 * estado de `VisionIdentifyPage` — en cuanto el usuario navegaba a otra
 * sección de la app (o recargaba la página), ese estado se perdía. El
 * backend SÍ guarda cada consulta en Firestore, pero eso puede tardar en
 * reflejarse o (si el guardado falla, ver docs/BONUS_FEATURES.md) nunca
 * llegar — este caché hace que el usuario nunca deje de ver lo que
 * identificó, sin depender de que Firestore haya podido guardar cada una.
 * El backend sigue siendo la fuente de verdad cuando responde bien; esto es
 * un respaldo que se fusiona con lo que llegue de ahí, nunca al revés.
 */
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
    // llena, etc.) — no es crítico: el usuario solo pierde el respaldo
    // local, el resto de la app sigue funcionando igual.
  }
}
