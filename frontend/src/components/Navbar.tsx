import { useAuth } from "@/context/AuthContext";
import { NavLink } from "react-router-dom";

function navLinkClass({ isActive }: { isActive: boolean }) {
  return `poke-nav-link rounded-full px-3 py-1.5 text-sm font-display font-semibold transition-colors sm:px-4 sm:py-2 sm:text-base ${
    isActive ? "bg-poke-blue-dark text-white shadow-soft" : "text-poke-ink hover:bg-poke-mist"
  }`;
}

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-white/60 bg-white/70 backdrop-blur-md">
      {/*
        Mobile (por defecto): dos filas —
          fila 1: logo (izquierda) + acciones de usuario (derecha)
          fila 2: nav de Pokédex/Mi Colección, ancho completo, centrado
        Desde `sm`: una sola fila — logo | nav centrado | acciones de usuario
        (igual que el diseño original de escritorio).
      */}
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3 sm:flex-nowrap">
        <div className="flex min-w-0 items-center gap-2">
          <img src="/pokeball.svg" alt="PokéDex Manager" className="h-8 w-8 shrink-0" />
          <span className="truncate font-display text-lg font-bold text-poke-ink sm:text-xl">
            PokéDex <span className="text-poke-teal-dark">Manager</span>
          </span>
        </div>

        <div className="order-2 flex shrink-0 items-center gap-2 sm:order-3 sm:gap-3">
          {user && (
            <>
              <div className="flex items-center gap-2">
                {user.picture_url && (
                  <img
                    src={user.picture_url}
                    alt={user.name}
                    className="h-8 w-8 rounded-full border-2 border-poke-teal"
                  />
                )}
                <span className="hidden text-sm font-semibold text-poke-ink sm:inline">
                  {user.name}
                </span>
              </div>
              <button onClick={logout} className="poke-btn-secondary !px-3 !py-1.5 text-sm sm:!px-4">
                Salir
              </button>
            </>
          )}
        </div>

        <nav className="order-3 flex w-full items-center justify-center gap-2 sm:order-2 sm:w-auto sm:flex-1">
          <NavLink to="/pokedex" className={navLinkClass}>
            Pokédex
          </NavLink>
          <NavLink to="/collection" className={navLinkClass}>
            Mi Colección
          </NavLink>
        </nav>
      </div>
    </header>
  );
}
