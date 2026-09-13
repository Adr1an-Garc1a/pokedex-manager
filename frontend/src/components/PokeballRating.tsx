/** Fila de 10 pokébolas — se "pintan" (a color) tantas como indique `score`
 * (1-10) y el resto quedan en gris, para visualizar de un vistazo qué tan
 * bueno es un equipo sin tener que leer el número. */
export function PokeballRating({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(10, Math.round(score)));

  return (
    <div className="flex flex-col items-center gap-2 sm:items-start">
      <div className="flex flex-wrap gap-1">
        {Array.from({ length: 10 }, (_, i) => i < clamped).map((filled, i) => (
          <img
            key={i}
            src="/pokeball.svg"
            alt={filled ? "Pokébola llena" : "Pokébola vacía"}
            className="h-7 w-7 transition-all"
            style={filled ? undefined : { filter: "grayscale(1)", opacity: 0.3 }}
          />
        ))}
      </div>
      <p className="font-display text-lg font-extrabold text-poke-ink">
        {clamped}
        <span className="text-sm font-normal text-poke-ink-soft"> / 10</span>
      </p>
    </div>
  );
}
