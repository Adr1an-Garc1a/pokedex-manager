import { addToCollection, listMyCollection } from "@/api/collection";
import { listPokemon } from "@/api/pokemon";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { PokemonCard } from "@/components/PokemonCard";
import type { PokemonSummary } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

const PAGE_SIZE = 24;

export function PokedexPage() {
  const [search, setSearch] = useState("");
  const [committedSearch, setCommittedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const queryClient = useQueryClient();

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["pokemon-list", offset, committedSearch],
    queryFn: () =>
      listPokemon({
        limit: PAGE_SIZE,
        offset,
        search: committedSearch || undefined,
      }),
    placeholderData: (previous) => previous,
  });

  const { data: myCollection } = useQuery({
    queryKey: ["collection", "ids-only"],
    queryFn: listMyCollection,
  });
  const ownedIds = new Set((myCollection ?? []).map((entry) => entry.pokemon_id));

  const addMutation = useMutation({
    mutationFn: (pokemon: PokemonSummary) => addToCollection({ pokemon_id: pokemon.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection"] });
    },
  });

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault();
    setOffset(0);
    setCommittedSearch(search.trim());
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-extrabold">Pokédex</h1>
          <p className="text-poke-ink-soft">
            Explora el catálogo (vía PokéAPI) y agrega Pokémon a tu colección.
          </p>
        </div>
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre (ej. pikachu)"
            className="poke-input"
          />
          <button type="submit" className="poke-btn-primary">
            Buscar
          </button>
        </form>
      </div>

      {error && (
        <p className="rounded-xl2 bg-poke-coral/20 p-4 text-poke-ink">
          No se pudo cargar la Pokédex. Verifica que el backend esté corriendo.
        </p>
      )}

      {isLoading ? (
        <PokeballSpinner label="Cargando Pokédex..." />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {data?.results.map((pokemon) => (
              <PokemonCard
                key={pokemon.id}
                pokemon={pokemon}
                onAdd={(p) => addMutation.mutate(p)}
                isAdding={addMutation.isPending && addMutation.variables?.id === pokemon.id}
                alreadyInCollection={ownedIds.has(pokemon.id)}
              />
            ))}
          </div>

          {data?.results.length === 0 && (
            <p className="py-12 text-center text-poke-ink-soft">
              No se encontraron Pokémon con ese nombre.
            </p>
          )}

          {!committedSearch && (
            <div className="mt-8 flex items-center justify-center gap-4">
              <button
                className="poke-btn-secondary"
                disabled={offset === 0}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                ← Anterior
              </button>
              <span className="font-display text-poke-ink-soft">
                {offset + 1}–{offset + (data?.results.length ?? 0)} de {data?.count ?? "…"}
              </span>
              <button
                className="poke-btn-secondary"
                disabled={isFetching || (data ? offset + PAGE_SIZE >= data.count : true)}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
