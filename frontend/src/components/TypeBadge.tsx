const TYPE_COLORS: Record<string, string> = {
  normal: "bg-type-normal", fire: "bg-type-fire", water: "bg-type-water",
  electric: "bg-type-electric", grass: "bg-type-grass", ice: "bg-type-ice",
  fighting: "bg-type-fighting", poison: "bg-type-poison", ground: "bg-type-ground",
  flying: "bg-type-flying", psychic: "bg-type-psychic", bug: "bg-type-bug",
  rock: "bg-type-rock", ghost: "bg-type-ghost", dragon: "bg-type-dragon",
  dark: "bg-type-dark", steel: "bg-type-steel", fairy: "bg-type-fairy",
};

export function TypeBadge({ type }: { type: string }) {
  const colorClass = TYPE_COLORS[type] ?? "bg-poke-mist";
  return <span className={`type-badge ${colorClass}`}>{type}</span>;
}
