const TYPE_COLORS: Record<string, string> = {
  normal: "bg-type-normal", fire: "bg-type-fire", water: "bg-type-water",
  electric: "bg-type-electric", grass: "bg-type-grass", ice: "bg-type-ice",
  fighting: "bg-type-fighting", poison: "bg-type-poison", ground: "bg-type-ground",
  flying: "bg-type-flying", psychic: "bg-type-psychic", bug: "bg-type-bug",
  rock: "bg-type-rock", ghost: "bg-type-ghost", dragon: "bg-type-dragon",
  dark: "bg-type-dark", steel: "bg-type-steel", fairy: "bg-type-fairy",
};

/** `type` (slug en inglés, ej. "water") decide siempre el color — es la
 * clave que existe en TYPE_COLORS. `label`, si se pasa, es el texto que se
 * muestra en vez del propio `type` (ej. para mostrar "agua" en español sin
 * perder el color asociado a "water"). */
export function TypeBadge({ type, label }: { type: string; label?: string }) {
  const colorClass = TYPE_COLORS[type] ?? "bg-poke-mist";
  return <span className={`type-badge ${colorClass}`}>{label ?? type}</span>;
}
