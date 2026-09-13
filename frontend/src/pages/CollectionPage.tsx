import {
  deleteCollectionEntry,
  getCollectionStats,
  listMyCollection,
  updateCollectionEntry,
  updateMyTeam,
} from "@/api/collection";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { TypeBadge } from "@/components/TypeBadge";
import { useAuth } from "@/context/AuthContext";
import type { CollectionEntry } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const MAX_TEAM_SIZE = 6;

/** El "equipo efectivo" que Insights va a analizar ahora mismo — misma
 * lógica que `app/services/team.py` en el backend: si el usuario ya eligió
 * un equipo a mano (algún `is_team_member`), esos son; si no, y tiene 6 o
 * menos, es toda su colección; si no, son los primeros 6 que agregó (por
 * fecha de creación — el backend devuelve la lista más reciente primero,
 * así que aquí se reordena ascendente para replicar "los primeros"). */
function getEffectiveTeamIds(entries: CollectionEntry[]): Set<number> {
  const chosen = entries.filter((e) => e.is_team_member);
  if (chosen.length > 0) {
    return new Set(chosen.map((e) => e.id));
  }
  if (entries.length <= MAX_TEAM_SIZE) {
    return new Set(entries.map((e) => e.id));
  }
  const byCreatedAsc = [...entries].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  return new Set(byCreatedAsc.slice(0, MAX_TEAM_SIZE).map((e) => e.id));
}

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
  const [isEditingTeam, setIsEditingTeam] = useState(false);
  const [draftTeamIds, setDraftTeamIds] = useState<Set<number>>(new Set());

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

  const effectiveTeamIds = useMemo(() => getEffectiveTeamIds(entries ?? []), [entries]);
  const hasChosenTeam = (entries ?? []).some((e) => e.is_team_member);

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

  // Elegir equipo afecta directamente lo que analiza Insights, así que al
  // guardar se invalida también su query (scopeada por usuario, ver
  // InsightsPage.tsx) para que el próximo análisis refleje el equipo nuevo.
  const teamMutation = useMutation({
    mutationFn: updateMyTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collection", userId] });
      queryClient.invalidateQueries({ queryKey: ["ai", "insights", userId] });
      setIsEditingTeam(false);
    },
  });

  function startEditingTeam() {
    setDraftTeamIds(new Set(effectiveTeamIds));
    setIsEditingTeam(true);
  }

  function cancelEditingTeam() {
    setIsEditingTeam(false);
    teamMutation.reset();
  }

  function toggleDraftTeamMember(id: number) {
    setDraftTeamIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < MAX_TEAM_SIZE) {
        next.add(id);
      }
      return next;
    });
  }

  function saveTeam() {
    teamMutation.mutate(Array.from(draftTeamIds));
  }

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

      {entries && entries.length > 0 && (
        <div className="poke-card mb-6 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-lg font-bold">
              🛡️ Tu equipo{" "}
              {entries.length > MAX_TEAM_SIZE && (
                <span className="font-body text-sm font-normal text-poke-ink-soft">
                  (hasta {MAX_TEAM_SIZE})
                </span>
              )}
            </h2>

            {entries.length > MAX_TEAM_SIZE &&
              (isEditingTeam ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-poke-ink-soft">
                    {draftTeamIds.size}/{MAX_TEAM_SIZE} seleccionados
                  </span>
                  <button
                    className="poke-btn-primary !py-1.5 text-sm"
                    onClick={saveTeam}
                    disabled={teamMutation.isPending}
                  >
                    {teamMutation.isPending ? "Guardando..." : "Guardar equipo"}
                  </button>
                  <button
                    className="poke-btn-secondary !py-1.5 text-sm"
                    onClick={cancelEditingTeam}
                    disabled={teamMutation.isPending}
                  >
                    Cancelar
                  </button>
                </div>
              ) : (
                <button className="poke-btn-primary !py-1.5 text-sm" onClick={startEditingTeam}>
                  Hacer de mi equipo
                </button>
              ))}
          </div>

          {teamMutation.isError && (
            <p className="mb-2 text-sm text-poke-coral">{getErrorMessage(teamMutation.error)}</p>
          )}

          <div className="flex flex-wrap gap-3">
            {entries
              .filter((e) => (isEditingTeam ? draftTeamIds.has(e.id) : effectiveTeamIds.has(e.id)))
              .map((e) => (
                <div
                  key={e.id}
                  className="flex w-20 flex-col items-center gap-1 rounded-xl bg-poke-mist/50 p-2"
                >
                  <img
                    src={e.custom_image_url ?? e.sprite_url ?? undefined}
                    alt={e.pokemon_name}
                    className="h-10 w-10 rounded-full bg-white object-contain [image-rendering:pixelated]"
                  />
                  <p className="text-center text-[11px] font-semibold capitalize leading-tight">
                    {e.nickname || e.pokemon_name}
                  </p>
                </div>
              ))}
            {isEditingTeam && draftTeamIds.size === 0 && (
              <p className="self-center text-sm text-poke-ink-soft">
                Elige hasta {MAX_TEAM_SIZE} Pokémon de la lista de abajo.
              </p>
            )}
          </div>

          {entries.length <= MAX_TEAM_SIZE ? (
            <p className="mt-3 text-xs text-poke-ink-soft">
              Como tienes {MAX_TEAM_SIZE} o menos Pokémon, tu equipo es toda tu colección —
              Insights ya los analiza a todos.
            </p>
          ) : (
            !isEditingTeam && (
              <p className="mt-3 text-xs text-poke-ink-soft">
                {hasChosenTeam
                  ? "Este es el equipo que elegiste — Insights lo analiza a él."
                  : `Todavía no elegiste equipo, así que Insights está analizando los primeros ${MAX_TEAM_SIZE} Pokémon que agregaste. Puedes cambiarlo cuando quieras.`}
              </p>
            )
          )}
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
          {entries?.map((entry) => {
            const isInDraftTeam = draftTeamIds.has(entry.id);
            const isInEffectiveTeam = effectiveTeamIds.has(entry.id);
            return (
            <div
              key={entry.id}
              className={`poke-card flex flex-col gap-3 p-4 ${
                isEditingTeam
                  ? isInDraftTeam
                    ? "ring-2 ring-poke-teal"
                    : ""
                  : isInEffectiveTeam
                    ? "ring-2 ring-poke-teal/40"
                    : ""
              }`}
            >
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
                  <div className="mt-1 flex flex-wrap items-center gap-1">
                    {entry.types.map((t) => (
                      <TypeBadge key={t} type={t} />
                    ))}
                    {!isEditingTeam && isInEffectiveTeam && (
                      <span className="rounded-full bg-poke-teal/20 px-2 py-0.5 text-[10px] font-semibold text-poke-teal-dark">
                        🛡️ En tu equipo
                      </span>
                    )}
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

              {isEditingTeam ? (
                <button
                  className={`w-full !py-1.5 text-sm ${
                    isInDraftTeam ? "poke-btn-primary" : "poke-btn-secondary"
                  }`}
                  onClick={() => toggleDraftTeamMember(entry.id)}
                  disabled={!isInDraftTeam && draftTeamIds.size >= MAX_TEAM_SIZE}
                >
                  {isInDraftTeam ? "✓ En el equipo" : "Añadir al equipo"}
                </button>
              ) : editingId === entry.id ? (
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
            );
          })}
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
