import { getCollectionInsights } from "@/api/ai";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

export function InsightsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["ai", "insights"],
    queryFn: getCollectionInsights,
    retry: false,
  });

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 text-center">
        <h1 className="font-display text-3xl font-extrabold">
          Insights de tu colección 🧠
        </h1>
        <p className="text-poke-ink-soft">
          Análisis generado con IA (Gemini 2.5 Flash) a partir de tu colección actual.
        </p>
      </div>

      {isLoading && <PokeballSpinner label="Analizando tu colección con IA (puede tardar unos segundos)..." />}

      {error && (
        <div className="poke-card mx-auto max-w-md p-6 text-center">
          <p className="text-poke-coral">{getErrorMessage(error)}</p>
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-6">
          <Section title="🏆 Tu equipo ideal (hasta 6)">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.ideal_team.map((member, i) => (
                <div key={i} className="poke-card p-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-display font-bold capitalize">{member.pokemon_name}</h3>
                    {member.already_in_collection && (
                      <span className="type-badge bg-poke-teal">en tu colección</span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-poke-ink-soft">{member.reason}</p>
                </div>
              ))}
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

          <Section title="💡 Datos curiosos">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.fun_facts.map((f, i) => (
                <div key={i} className="poke-card p-3 text-sm">
                  <span className="font-display font-bold capitalize">{f.pokemon_name}: </span>
                  {f.fact}
                </div>
              ))}
            </div>
          </Section>

          <Section title="✨ Alternativas sugeridas">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.suggested_additions.map((s, i) => (
                <div key={i} className="poke-card p-3 text-sm">
                  <span className="font-display font-bold capitalize">{s.pokemon_name}: </span>
                  {s.reason}
                </div>
              ))}
            </div>
          </Section>
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
