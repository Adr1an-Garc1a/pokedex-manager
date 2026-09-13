export interface User {
  id: number;
  email: string;
  name: string;
  picture_url: string | null;
  created_at: string;
}

/** Datos de Google usados para autocompletar el formulario de registro,
 * devueltos por el backend cuando detecta que la cuenta aún no existe. */
export interface GoogleProfilePreview {
  name: string;
  email: string;
  picture: string | null;
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

// --- Funcionalidades bonus de IA -----------------------------------------

export interface PokemonVisionResult {
  entry_id: string | null;
  created_at: string | null;
  image_url: string;
  pokemon_name: string;
  description: string;
  confidence: string;
  first_appearance_game: string;
  habitat_zones: string;
  matched_pokemon_id: number | null;
  sprite_url: string | null;
  types: string[];
  strong_against: string[];
  weak_against: string[];
  strong_against_es: string[];
  weak_against_es: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  ts: string;
}

export interface ChatResponse {
  reply: string;
  history: ChatMessage[];
  history_persisted: boolean;
}

export interface AlternativeSuggestion {
  pokemon_name: string;
  reason: string;
  sprite_url: string | null;
}

export interface TeamRecommendation {
  pokemon_name: string;
  reason: string;
  already_in_collection: boolean;
  sprite_url: string | null;
  alternatives: AlternativeSuggestion[];
}

export interface FunFactEntry {
  pokemon_name: string;
  fact: string;
  sprite_url: string | null;
}

export interface AnalyzedTeamMember {
  pokemon_name: string;
  sprite_url: string | null;
  types: string[];
}

export interface CollectionInsights {
  analyzed_team: AnalyzedTeamMember[];
  team_score: number;
  team_score_reason: string;
  ideal_team: TeamRecommendation[];
  strengths: string[];
  weaknesses: string[];
  fun_facts: FunFactEntry[];
}
