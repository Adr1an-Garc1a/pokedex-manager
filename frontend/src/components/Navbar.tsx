import { useAuth } from "@/context/AuthContext";
import { NavLink } from "react-router-dom";

function navLinkClass({ isActive }: { isActive: boolean }) {
  return `poke-nav-link px-4 py-2 rounded-full font-display font-semibold transition-colors ${
    isActive ? "bg-poke-blue-dark text-white shadow-soft" : "text-poke-ink hover:bg-poke-mist"
  }`;
}

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-20 border-b border-white/60 bg-white/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-2">
          <img src="/pokeball.svg" alt="PokéDex Manager" className="h-8 w-8" />
          <span className="font-display text-xl font-bold text-poke-ink">
            PokéDex <span className="text-poke-teal-dark">Manager</span>
          </span>
        </div>

        <nav className="flex items-center gap-2">
          <NavLink to="/pokedex" className={navLinkClass}>
            Pokédex
          </NavLink>
          <NavLink to="/collection" className={navLinkClass}>
            Mi Colección
          </NavLink>
        </nav>

        <div className="flex items-center gap-3">
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
              <button onClick={logout} className="poke-btn-secondary !px-4 !py-1.5 text-sm">
                Salir
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
