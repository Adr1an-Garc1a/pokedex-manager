export interface User {
  id: number;
  email: string;
  name: string;
  picture_url: string | null;
  created_at: string;
}

export interface PokemonSummary {
  id: number;
  name: string;
  sprite_url: string | null;
  types: string[];
}

export interface PokemonListResponse {
  count: number;
  limit: number;
  offset: number;
  results: PokemonSummary[];
}

export interface PokemonStat {
  name: string;
  base_stat: number;
}

export interface PokemonDetail {
  id: number;
  name: string;
  height: number;
  weight: number;
  sprite_url: string | null;
  artwork_url: string | null;
  types: string[];
  abilities: string[];
  stats: PokemonStat[];
}

export interface CollectionEntry {
  id: number;
  pokemon_id: number;
  pokemon_name: string;
  sprite_url: string | null;
  types: string[];
  nickname: string | null;
  level: number | null;
  is_favorite: boolean;
  notes: string | null;
  custom_image_url: string | null;
  caught_at: string;
  created_at: string;
  updated_at: string;
}

export interface CollectionEntryInput {
  pokemon_id: number;
  nickname?: string | null;
  level?: number | null;
  notes?: string | null;
  is_favorite?: boolean;
}

export interface CollectionStats {
  total: number;
  by_type: Record<string, number>;
  favorites: number;
}
