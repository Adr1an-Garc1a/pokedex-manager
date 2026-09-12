import { apiClient } from "@/api/client";
import type { PokemonDetail, PokemonListResponse } from "@/types";

export async function listPokemon(params: {
  limit?: number;
  offset?: number;
  search?: string;
}): Promise<PokemonListResponse> {
  const { data } = await apiClient.get<PokemonListResponse>("/pokemon", { params });
  return data;
}

export async function getPokemonDetail(idOrName: string | number): Promise<PokemonDetail> {
  const { data } = await apiClient.get<PokemonDetail>(`/pokemon/${idOrName}`);
  return data;
}
