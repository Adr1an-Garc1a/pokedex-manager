export function PokeballSpinner({ label = "Cargando..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-poke-ink-soft">
      <img src="/pokeball.svg" alt="Cargando" className="h-12 w-12 pokeball-spin" />
      <p className="font-display">{label}</p>
    </div>
  );
}
