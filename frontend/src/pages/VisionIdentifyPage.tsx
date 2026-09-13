import { getVisionHistory, identifyPokemonImage } from "@/api/ai";
import { addToCollection, listMyCollection } from "@/api/collection";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { TypeBadge } from "@/components/TypeBadge";
import type { PokemonVisionResult } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type ChangeEvent } from "react";

export function VisionIdentifyPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const { data: myCollection } = useQuery({
    queryKey: ["collection", "ids-only"],
    queryFn: listMyCollection,
  });
  const ownedIds = new Set((myCollection ?? []).map((entry) => entry.pokemon_id));

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["ai", "vision-history"],
    queryFn: getVisionHistory,
  });

  const identifyMutation = useMutation({
    mutationFn: identifyPokemonImage,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai", "vision-history"] }),
  });

  const addMutation = useMutation({
    mutationFn: (pokemonId: number) => addToCollection({ pokemon_id: pokemonId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collection"] }),
  });

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    identifyMutation.reset();
  }

  function handleIdentify() {
    if (selectedFile) {
      identifyMutation.mutate(selectedFile);
    }
  }

  const result = identifyMutation.data;
  const alreadyOwned = result?.matched_pokemon_id
    ? ownedIds.has(result.matched_pokemon_id)
    : false;

  // La consulta recién hecha ya viene incluida en `history` (se invalida la
  // query al identificar), así que la tabla se arma solo con el historial —
  // evita mostrar el mismo resultado duplicado dos veces.
  const rows: PokemonVisionResult[] = history ?? [];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 text-center">
        <h1 className="font-display text-3xl font-extrabold">
          ¿No sabes qué Pokémon tienes? 📸
        </h1>
        <p className="text-poke-ink-soft">
          Sube una foto (una carta, un peluche, una captura de pantalla...) y
          averigüémoslo con IA — Gemini 2.5 Flash identifica el Pokémon por ti.
        </p>
      </div>

      <div className="poke-card flex flex-col items-center gap-4 p-6">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />

        {previewUrl ? (
          <img
            src={previewUrl}
            alt="Foto seleccionada"
            className="h-48 w-48 rounded-2xl border-2 border-poke-teal object-cover"
          />
        ) : (
          <div className="flex h-48 w-48 items-center justify-center rounded-2xl border-2 border-dashed border-poke-mist text-4xl">
            🐾
          </div>
        )}

        <div className="flex flex-wrap justify-center gap-2">
          <button
            type="button"
            className="poke-btn-secondary"
            onClick={() => fileInputRef.current?.click()}
          >
            {selectedFile ? "Cambiar foto" : "Elegir foto"}
          </button>
          <button
            type="button"
            className="poke-btn-primary"
            disabled={!selectedFile || identifyMutation.isPending}
            onClick={handleIdentify}
          >
            {identifyMutation.isPending ? "Identificando..." : "Identificar"}
          </button>
        </div>

        {identifyMutation.isPending && <PokeballSpinner label="Analizando la imagen con IA..." />}

        {identifyMutation.isError && (
          <p className="text-sm text-poke-coral">{getErrorMessage(identifyMutation.error)}</p>
        )}
      </div>

      {result && (
        <div className="poke-card mt-6 flex flex-col gap-3 p-6">
          <h2 className="font-display text-xl font-bold">✅ ¡Listo! Esto encontré:</h2>
          {result.matched_pokemon_id ? (
            <button
              className="poke-btn-primary self-start"
              disabled={alreadyOwned || addMutation.isPending}
              onClick={() => addMutation.mutate(result.matched_pokemon_id!)}
            >
              {alreadyOwned
                ? "Ya está en tu colección"
                : addMutation.isPending
                ? "Agregando..."
                : `Agregar ${result.pokemon_name} a mi colección`}
            </button>
          ) : (
            <p className="text-sm text-poke-ink-soft">
              No se pudo confirmar este Pokémon contra la Pokédex oficial, así que no se puede
              agregar directamente a tu colección — pero la identificación de abajo es la del
              modelo de todas formas.
            </p>
          )}
        </div>
      )}

      <div className="mt-8">
        <h2 className="mb-3 font-display text-xl font-bold">🕓 Historial de identificaciones</h2>
        {historyLoading ? (
          <PokeballSpinner label="Cargando tu historial..." />
        ) : rows.length === 0 ? (
          <p className="poke-card p-4 text-center text-sm text-poke-ink-soft">
            Todavía no has identificado ningún Pokémon — sube una foto arriba para empezar.
          </p>
        ) : (
          <VisionHistoryTable rows={rows} />
        )}
      </div>
    </div>
  );
}

function VisionHistoryTable({ rows }: { rows: PokemonVisionResult[] }) {
  return (
    <div className="poke-card overflow-x-auto p-2">
      <table className="w-full min-w-[820px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b-2 border-poke-mist text-xs uppercase tracking-wide text-poke-ink-soft">
            <th className="p-3">Foto</th>
            <th className="p-3">Nombre del Pokémon</th>
            <th className="p-3">Tipo</th>
            <th className="p-3">Descripción</th>
            <th className="p-3">Juego de primera aparición</th>
            <th className="p-3">Zonas donde es fácil encontrarlo</th>
            <th className="p-3">Fuerte contra</th>
            <th className="p-3">Débil contra</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.entry_id ?? row.image_url} className="border-b border-poke-mist/70 align-top">
              <td className="p-3">
                <img
                  src={row.sprite_url ?? row.image_url}
                  alt={row.pokemon_name}
                  className="h-14 w-14 rounded-xl bg-poke-mist object-contain [image-rendering:pixelated]"
                />
              </td>
              <td className="p-3">
                <p className="font-display font-bold capitalize">{row.pokemon_name}</p>
                <p className="text-xs text-poke-ink-soft">Confianza: {row.confidence}</p>
              </td>
              <td className="p-3">
                <div className="flex flex-wrap gap-1">
                  {row.types.length > 0 ? (
                    row.types.map((t) => <TypeBadge key={t} type={t} />)
                  ) : (
                    <span className="text-xs text-poke-ink-soft">—</span>
                  )}
                </div>
              </td>
              <td className="p-3 max-w-[220px] text-poke-ink">{row.description}</td>
              <td className="p-3 max-w-[180px] text-poke-ink">{row.first_appearance_game}</td>
              <td className="p-3 max-w-[180px] text-poke-ink">{row.habitat_zones}</td>
              <td className="p-3">
                <div className="flex flex-wrap gap-1">
                  {row.strong_against.map((t, i) => (
                    <TypeBadge key={t} type={t} label={row.strong_against_es[i] ?? t} />
                  ))}
                </div>
              </td>
              <td className="p-3">
                <div className="flex flex-wrap gap-1">
                  {row.weak_against.map((t, i) => (
                    <TypeBadge key={t} type={t} label={row.weak_against_es[i] ?? t} />
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
