import { getCollectionInsights } from "@/api/ai";
import { getErrorMessage } from "@/api/errors";
import { PokeballRating } from "@/components/PokeballRating";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { TypeBadge } from "@/components/TypeBadge";
import { useAuth } from "@/context/AuthContext";
import type { AlternativeSuggestion, TeamRecommendation } from "@/types";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

function PokemonSprite({
  name,
  spriteUrl,
  size = "h-14 w-14",
}: {
  name: string;
  spriteUrl: string | null;
  size?: string;
}) {
  return spriteUrl ? (
    <img
      src={spriteUrl}
      alt={name}
      className={`${size} shrink-0 rounded-full bg-poke-mist object-contain [image-rendering:pixelated]`}
    />
  ) : (
    <div
      className={`${size} flex shrink-0 items-center justify-center rounded-full bg-poke-mist text-xl`}
      aria-hidden
    >
      ❓
    </div>
  );
}

export function InsightsPage() {
  const { user } = useAuth();

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["ai", "insights", user?.id],
    queryFn: getCollectionInsights,
    enabled: !!user,
    retry: false,
  });

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 text-center">
        <h1 className="font-display text-3xl font-extrabold">
          Insights de tu colección 🧠
        </h1>
        <p className="text-poke-ink-soft">
          ¡Este apartado te da insights importantes a considerar con tu equipo actual!
          Te dice fortalezas, debilidades y recomendaciones para que seas aún más
          poderoso — basado en tu equipo actual (hasta 6 Pokémon). Si tienes más de 6
          en tu colección, puedes elegir cuáles forman tu equipo desde{" "}
          <Link to="/collection" className="font-semibold underline">
            Mi Colección
          </Link>{" "}
          (análisis generado con IA, Gemini 2.5 Flash).
        </p>
      </div>

      {!isLoading && (
        <div className="mb-6 flex flex-col items-center gap-1">
          <button
            className="poke-btn-secondary text-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? "Actualizando insights..." : "🔄 Actualizar insights"}
          </button>
          <p className="text-xs text-poke-ink-soft">
            ¿Cambiaste tu equipo en Mi Colección? Dale aquí para recalcular el análisis.
          </p>
        </div>
      )}

      {isLoading && (
        <PokeballSpinner label="Espera un momento, entrenador/a... entendiendo tu equipo de Pokémon, ¡ya casi los cazas a todos! 🎯" />
      )}

      {error && (
        <div className="poke-card mx-auto max-w-md p-6 text-center">
          <p className="text-poke-coral">{getErrorMessage(error)}</p>
        </div>
      )}

      {data && (
        <div className={`flex flex-col gap-6 transition-opacity ${isFetching ? "opacity-50" : ""}`}>
          <Section title="🐾 Tu equipo analizado">
            <div className="flex flex-wrap gap-3">
              {data.analyzed_team.map((member, i) => (
                <div key={i} className="poke-card flex flex-col items-center gap-1 p-3">
                  <PokemonSprite name={member.pokemon_name} spriteUrl={member.sprite_url} />
                  <p className="text-center text-xs font-semibold capitalize">{member.pokemon_name}</p>
                  <div className="flex flex-wrap justify-center gap-1">
                    {member.types.map((t) => (
                      <TypeBadge key={t} type={t} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Section>

          <Section title="⭐ Calificación de tu equipo">
            <div className="poke-card flex flex-col items-center gap-3 p-5 text-center sm:flex-row sm:text-left">
              <PokeballRating score={data.team_score} />
              <p className="text-sm text-poke-ink">{data.team_score_reason}</p>
            </div>
          </Section>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <Section title="💪 Fortalezas">
              <ul className="flex flex-col gap-2">
                {data.strengths.map((s, i) => (
                  <li key={i} className="poke-card p-3 text-sm">
                    {s}
                  </li>
                ))}
              </ul>
            </Section>

            <Section title="⚠️ Debilidades">
              <ul className="flex flex-col gap-2">
                {data.weaknesses.map((w, i) => (
                  <li key={i} className="poke-card p-3 text-sm">
                    {w}
                  </li>
                ))}
              </ul>
            </Section>
          </div>

          <Section title="🏆 Equipo ideal (hasta 6)">
            <p className="mb-3 text-xs text-poke-ink-soft">
              Los recuadros en{" "}
              <span className="rounded bg-poke-orange px-1.5 py-0.5 font-semibold text-poke-ink">
                naranja
              </span>{" "}
              son Pokémon que todavía no tienes — la razón explica qué le aportarían a tu equipo.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.ideal_team.map((member, i) => (
                <IdealTeamCard key={i} member={member} />
              ))}
            </div>
          </Section>

          <Section title="💡 Datos curiosos de tu colección">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.fun_facts.map((f, i) => (
                <div key={i} className="poke-card flex items-center gap-3 p-3 text-sm">
                  <PokemonSprite name={f.pokemon_name} spriteUrl={f.sprite_url} size="h-10 w-10" />
                  <div>
                    <span className="font-display font-bold capitalize">{f.pokemon_name}: </span>
                    {f.fact}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}

function IdealTeamCard({ member }: { member: TeamRecommendation }) {
  const isMissing = !member.already_in_collection;
  return (
    <div
      className={`poke-card p-4 ${
        isMissing ? "border-2 border-poke-orange-dark bg-poke-orange/40" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <PokemonSprite name={member.pokemon_name} spriteUrl={member.sprite_url} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-1">
            <h3 className="font-display font-bold capitalize">{member.pokemon_name}</h3>
            {member.already_in_collection ? (
              <span className="type-badge bg-poke-teal">ya lo tienes</span>
            ) : (
              <span className="type-badge bg-poke-orange-dark text-poke-ink">te falta</span>
            )}
          </div>
          <p className="mt-1 text-sm text-poke-ink-soft">{member.reason}</p>
        </div>
      </div>

      {member.alternatives.length > 0 && (
        <div className="mt-3 border-t border-poke-mist pt-2">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-poke-ink-soft">
            ✨ Alternativas para este puesto
          </p>
          <div className="flex flex-col gap-2">
            {member.alternatives.map((alt: AlternativeSuggestion, i: number) => (
              <div key={i} className="flex items-center gap-2 rounded-xl bg-poke-mist/50 p-2">
                <PokemonSprite name={alt.pokemon_name} spriteUrl={alt.sprite_url} size="h-9 w-9" />
                <div className="min-w-0">
                  <p className="text-xs font-bold capitalize">{alt.pokemon_name}</p>
                  <p className="text-xs text-poke-ink-soft">{alt.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 font-display text-xl font-bold">{title}</h2>
      {children}
    </section>
  );
}
