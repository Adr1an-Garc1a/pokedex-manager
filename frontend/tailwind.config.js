/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta pastel azul / verde-azulado (teal) — pedida explícitamente
        // para dar una identidad "Pokémon" suave y amigable.
        poke: {
          sky: "#EAF6FF",     // fondo general
          mist: "#DCEFFF",    // fondo de tarjetas
          blue: "#8ECDF0",    // acento primario
          "blue-dark": "#4FA8D8",
          teal: "#7FD8C6",    // acento secundario (verde azulado pastel)
          "teal-dark": "#3FB39B",
          sun: "#FFE08A",     // acento cálido (fichas/estrellas favorito)
          coral: "#FFB4A2",   // errores / alertas suaves
          orange: "#FFD8A8",    // naranja pastel — resalta en Insights los Pokémon del equipo ideal que el usuario aún no tiene
          "orange-dark": "#E8A85C",
          ink: "#31465F",     // texto principal
          "ink-soft": "#6B84A0",
        },
        type: {
          normal: "#B8B9A6", fire: "#F5AC78", water: "#9DB7F5", electric: "#FAE078",
          grass: "#A7DB8D", ice: "#BCE6E6", fighting: "#D3A5A5", poison: "#C293C2",
          ground: "#EBD69D", flying: "#C6B7F5", psychic: "#FA92B2", bug: "#C6D16E",
          rock: "#D1C17D", ghost: "#A292BC", dragon: "#A27DFA", dark: "#A29288",
          steel: "#D1D1E0", fairy: "#F4BDC9",
        },
      },
      fontFamily: {
        display: ["'Baloo 2'", "cursive"],
        body: ["'Nunito'", "sans-serif"],
      },
      boxShadow: {
        soft: "0 8px 24px -8px rgba(79, 168, 216, 0.35)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
};
