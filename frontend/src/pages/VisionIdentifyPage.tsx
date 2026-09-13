import { identifyPokemonImage } from "@/api/ai";
import { addToCollection, listMyCollection } from "@/api/collection";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { TypeBadge } from "@/components/TypeBadge";
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

  const identifyMutation = useMutation({ mutationFn: identifyPokemonImage });

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

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
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
        <div className="poke-card mt-6 flex flex-col gap-4 p-6">
          <div className="flex items-center gap-4">
            {result.sprite_url && (
              <img
                src={result.sprite_url}
                alt={result.pokemon_name}
                className="h-20 w-20 rounded-full bg-poke-mist object-contain [image-rendering:pixelated]"
              />
            )}
            <div>
              <h2 className="font-display text-2xl font-bold capitalize">
                {result.pokemon_name}
              </h2>
              <p className="text-xs uppercase tracking-wide text-poke-ink-soft">
                Confianza del modelo: {result.confidence}
              </p>
            </div>
          </div>

          {result.types.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {result.types.map((t) => (
                <TypeBadge key={t} type={t} />
              ))}
            </div>
          )}

          <p className="text-poke-ink">{result.description}</p>
          <p className="rounded-xl2 bg-poke-mist/60 p-3 text-sm italic text-poke-ink-soft">
            💡 {result.fun_fact}
          </p>

          {(result.strong_against.length > 0 || result.weak_against.length > 0) && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {result.strong_against.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold text-poke-ink-soft">Fuerte contra</p>
                  <div className="flex flex-wrap gap-1">
                    {result.strong_against.map((t) => (
                      <TypeBadge key={t} type={t} />
                    ))}
                  </div>
                </div>
              )}
              {result.weak_against.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold text-poke-ink-soft">Débil contra</p>
                  <div className="flex flex-wrap gap-1">
                    {result.weak_against.map((t) => (
                      <TypeBadge key={t} type={t} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {result.matched_pokemon_id ? (
            <button
              className="poke-btn-primary"
              disabled={alreadyOwned || addMutation.isPending}
              onClick={() => addMutation.mutate(result.matched_pokemon_id!)}
            >
              {alreadyOwned
                ? "Ya está en tu colección"
                : addMutation.isPending
                ? "Agregando..."
                : "Agregar a mi colección"}
            </button>
          ) : (
            <p className="text-sm text-poke-ink-soft">
              No se pudo confirmar este Pokémon contra la Pokédex oficial, así que no se puede
              agregar directamente a tu colección — pero la identificación de arriba es la del
              modelo de todas formas.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
