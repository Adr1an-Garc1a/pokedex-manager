import { TypeBadge } from "@/components/TypeBadge";
import type { PokemonSummary } from "@/types";

interface Props {
  pokemon: PokemonSummary;
  onAdd?: (pokemon: PokemonSummary) => void;
  isAdding?: boolean;
  alreadyInCollection?: boolean;
}

export function PokemonCard({ pokemon, onAdd, isAdding, alreadyInCollection }: Props) {
  return (
    <div className="poke-card flex flex-col items-center gap-2 p-4 text-center">
      <span className="text-xs font-semibold text-poke-ink-soft">
        #{String(pokemon.id).padStart(3, "0")}
      </span>
      <div className="flex h-24 w-24 items-center justify-center rounded-full bg-poke-mist">
        {pokemon.sprite_url ? (
          <img
            src={pokemon.sprite_url}
            alt={pokemon.name}
            className="h-20 w-20 object-contain [image-rendering:pixelated]"
            loading="lazy"
          />
        ) : (
          <span className="text-3xl">?</span>
        )}
      </div>
      <h3 className="font-display text-lg font-bold capitalize text-poke-ink">
        {pokemon.name}
      </h3>
      <div className="flex flex-wrap justify-center gap-1">
        {pokemon.types.map((type) => (
          <TypeBadge key={type} type={type} />
        ))}
      </div>
      {onAdd && (
        <button
          onClick={() => onAdd(pokemon)}
          disabled={isAdding || alreadyInCollection}
          className="poke-btn-primary mt-2 !px-4 !py-1.5 text-sm"
        >
          {alreadyInCollection ? "En tu colección" : isAdding ? "Agregando..." : "+ Agregar"}
        </button>
      )}
    </div>
  );
}
