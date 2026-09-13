import {
  deleteCollectionEntry,
  getCollectionStats,
  listMyCollection,
  updateCollectionEntry,
} from "@/api/collection";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { TypeBadge } from "@/components/TypeBadge";
import { useAuth } from "@/context/AuthContext";
import type { CollectionEntry } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

export function CollectionPage() {
  const { user } = useAuth();
  const userId = user?.id;
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ nickname: string; level: string; notes: string }>({
    nickname: "",
    level: "",
    notes: "",
  });

  const { data: entries, isLoading } = useQuery({
    queryKey: ["collection", userId],
    queryFn: listMyCollection,
    enabled: !!userId,
  });

  const { data: stats } = useQuery({
    queryKey: ["collection", "stats", userId],
    queryFn: getCollectionStats,
    enabled: !!userId,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCollectionEntry,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collection"] }),
  });

  const favoriteMutation = useMutation({
    mutationFn: ({ id, is_favorite }: { id: number; is_favorite: boolean }) =>
      updateCollectionEntry(id, { is_favorite }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collection"] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<CollectionEntry> }) =>
      updateCollectionEntry(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection"] });
      setEditingId(null);
    },
  });

  function startEditing(entry: CollectionEntry) {
    setEditingId(entry.id);
    setDraft({
      nickname: entry.nickname ?? "",
      level: entry.level ? String(entry.level) : "",
      notes: entry.notes ?? "",
    });
  }

  function saveEditing(id: number) {
    updateMutation.mutate({
      id,
      payload: {
        nickname: draft.nickname || null,
        level: draft.level ? Number(draft.level) : null,
        notes: draft.notes || null,
      },
    });
  }

  if (isLoading) {
    return <PokeballSpinner label="Cargando tu colección..." />;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold">Mi Colección</h1>
          <p className="text-poke-ink-soft">
            ¡Estos son los Pokémon que tienes y sus tipos! Siéntete libre de añadir el
            nivel, un apodo o marcar tus favoritos para tener todo en cuenta.
          </p>
        </div>

        {stats && (
          <div className="flex gap-3">
            <StatPill label="Total" value={stats.total} />
            <StatPill label="Favoritos" value={stats.favorites} />
          </div>
        )}
      </div>

      {stats && Object.keys(stats.by_type).length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {Object.entries(stats.by_type).map(([type, count]) => (
            <div key={type} className="flex items-center gap-1">
              <TypeBadge type={type} />
              <span className="text-xs text-poke-ink-soft">×{count}</span>
            </div>
          ))}
        </div>
      )}

      {entries && entries.length === 0 ? (
        <div className="poke-card mx-auto max-w-md p-8 text-center">
          <p className="mb-3 text-poke-ink-soft">
            Todavía no tienes Pokémon en tu colección.
          </p>
          <a href="/pokedex" className="poke-btn-primary inline-flex">
            Ir a la Pokédex
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {entries?.map((entry) => (
            <div key={entry.id} className="poke-card flex flex-col gap-3 p-4">
              <div className="flex items-center gap-3">
                <img
                  src={entry.custom_image_url ?? entry.sprite_url ?? undefined}
                  alt={entry.pokemon_name}
                  className="h-16 w-16 rounded-full bg-poke-mist object-contain [image-rendering:pixelated]"
                />
                <div className="flex-1">
                  <h3 className="font-display text-lg font-bold capitalize">
                    {entry.nickname || entry.pokemon_name}
                  </h3>
                  {entry.nickname && (
                    <p className="text-xs capitalize text-poke-ink-soft">
                      {entry.pokemon_name}
                    </p>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {entry.types.map((t) => (
                      <TypeBadge key={t} type={t} />
                    ))}
                  </div>
                </div>
                <button
                  aria-label="Marcar favorito"
                  onClick={() =>
                    favoriteMutation.mutate({ id: entry.id, is_favorite: !entry.is_favorite })
                  }
                  className="text-2xl"
                  title={entry.is_favorite ? "Quitar de favoritos" : "Marcar favorito"}
                >
                  {entry.is_favorite ? "⭐" : "☆"}
                </button>
              </div>

              {editingId === entry.id ? (
                <div className="flex flex-col gap-2">
                  <input
                    className="poke-input"
                    placeholder="Apodo"
                    value={draft.nickname}
                    onChange={(e) => setDraft((d) => ({ ...d, nickname: e.target.value }))}
                  />
                  <input
                    className="poke-input"
                    placeholder="Nivel (1-100)"
                    type="number"
                    min={1}
                    max={100}
                    value={draft.level}
                    onChange={(e) => setDraft((d) => ({ ...d, level: e.target.value }))}
                  />
                  <textarea
                    className="poke-input !rounded-2xl"
                    placeholder="Notas"
                    value={draft.notes}
                    onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                  />
                  <div className="flex gap-2">
                    <button
                      className="poke-btn-primary flex-1 !py-1.5 text-sm"
                      onClick={() => saveEditing(entry.id)}
                      disabled={updateMutation.isPending}
                    >
                      Guardar
                    </button>
                    <button
                      className="poke-btn-secondary flex-1 !py-1.5 text-sm"
                      onClick={() => setEditingId(null)}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {entry.level && (
                    <p className="text-sm text-poke-ink-soft">Nivel: {entry.level}</p>
                  )}
                  {entry.notes && <p className="text-sm italic text-poke-ink-soft">"{entry.notes}"</p>}
                  <div className="flex gap-2">
                    <button
                      className="poke-btn-secondary flex-1 !py-1.5 text-sm"
                      onClick={() => startEditing(entry)}
                    >
                      Editar
                    </button>
                    <button
                      className="poke-btn-secondary flex-1 !py-1.5 text-sm !border-poke-coral hover:!bg-poke-coral/20"
                      onClick={() => deleteMutation.mutate(entry.id)}
                      disabled={deleteMutation.isPending}
                    >
                      Quitar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl2 bg-white/80 px-4 py-2 text-center shadow-soft">
      <p className="font-display text-xl font-extrabold text-poke-teal-dark">{value}</p>
      <p className="text-xs text-poke-ink-soft">{label}</p>
    </div>
  );
}
