import { getChatHistory, resetChatHistory, sendChatMessage } from "@/api/ai";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { useAuth } from "@/context/AuthContext";
import type { ChatMessage } from "@/types";
import {
  clearCachedChatHistory,
  loadCachedChatHistory,
  saveCachedChatHistory,
} from "@/utils/chatHistoryCache";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

/** Combina la copia local (localStorage) con lo que devuelve el backend, sin
 * duplicar mensajes (por rol+contenido+timestamp) y en orden cronológico —
 * mismo patrón que el historial de Vision. */
function mergeMessages(local: ChatMessage[], server: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const merged: ChatMessage[] = [];
  for (const m of [...local, ...server]) {
    const key = `${m.role}|${m.content}|${m.ts}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(m);
  }
  merged.sort((a, b) => (a.ts ?? "").localeCompare(b.ts ?? ""));
  return merged;
}

export function PokedexChatPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [lastPersistWarning, setLastPersistWarning] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Arranca ya con lo que quedó en localStorage de una visita anterior —
  // así la conversación se ve completa desde el primer render, y sobrevive
  // a navegar a otra sección de la app o recargar la página aunque el
  // guardado en Firestore esté fallando (ver utils/chatHistoryCache.ts).
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    user ? loadCachedChatHistory(user.id) : []
  );

  const { data: serverHistory, isLoading } = useQuery({
    queryKey: ["ai", "chat-history"],
    queryFn: getChatHistory,
  });

  // Cuando llega (o cambia) el historial del backend, se fusiona con el
  // caché local y se vuelve a guardar — el caché se "autocura" con lo que
  // Firestore sí pudo confirmar.
  useEffect(() => {
    if (!user || !serverHistory) return;
    setMessages((prev) => {
      const merged = mergeMessages(prev, serverHistory);
      saveCachedChatHistory(user.id, merged);
      return merged;
    });
  }, [serverHistory, user]);

  const sendMutation = useMutation({
    mutationFn: (vars: { message: string; clientHistory: ChatMessage[] }) =>
      sendChatMessage(vars.message, vars.clientHistory),
    onSuccess: (response) => {
      setMessages(response.history);
      if (user) saveCachedChatHistory(user.id, response.history);
      setLastPersistWarning(!response.history_persisted);
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetChatHistory,
    onSuccess: () => {
      setMessages([]);
      setLastPersistWarning(false);
      if (user) clearCachedChatHistory(user.id);
      queryClient.invalidateQueries({ queryKey: ["ai", "chat-history"] });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sendMutation.isPending]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || sendMutation.isPending) return;
    setDraft("");
    // Se manda la conversación que ya se tiene (fusión de caché local +
    // backend) como `clientHistory` — así Claude mantiene el contexto de la
    // conversación aunque el guardado en Firestore esté fallando.
    sendMutation.mutate({ message, clientHistory: messages });
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col px-4 py-8" style={{ minHeight: "70vh" }}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="font-display text-3xl font-extrabold">
            ¿Dudas de tu Pokédex? 💬
          </h1>
          <p className="text-poke-ink-soft">
            Pregúntale a la IA sobre tu colección — sabe leerla en tiempo real (vía MCP).
          </p>
        </div>
        <button
          type="button"
          className="poke-btn-secondary !py-1.5 text-sm"
          onClick={() => resetMutation.mutate()}
          disabled={resetMutation.isPending || messages.length === 0}
        >
          Reiniciar conversación
        </button>
      </div>

      <div className="poke-card flex flex-1 flex-col gap-3 overflow-y-auto p-4" style={{ minHeight: "45vh", maxHeight: "55vh" }}>
        {isLoading && messages.length === 0 ? (
          <PokeballSpinner label="Cargando conversación..." />
        ) : messages.length === 0 ? (
          <p className="m-auto text-center text-poke-ink-soft">
            Todavía no has chateado. Prueba con "¿qué Pokémon tengo?" o
            "¿cuál sería mi equipo ideal?".
          </p>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                m.role === "user"
                  ? "self-end bg-poke-blue-dark text-white"
                  : "self-start bg-poke-mist text-poke-ink"
              }`}
            >
              {m.content}
            </div>
          ))
        )}
        {sendMutation.isPending && (
          <div className="self-start rounded-2xl bg-poke-mist px-4 py-2 text-sm text-poke-ink-soft">
            Pensando...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {sendMutation.isError && (
        <p className="mt-2 text-sm text-poke-coral">{getErrorMessage(sendMutation.error)}</p>
      )}

      {lastPersistWarning && !sendMutation.isPending && (
        <p className="mt-2 text-xs text-poke-ink-soft">
          ⚠️ La IA respondió, pero no se pudo guardar este mensaje en Firestore (problema
          temporal con el almacenamiento) — tu conversación sigue completa localmente y puedes
          seguir chateando normalmente.
        </p>
      )}

      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <input
          className="poke-input"
          placeholder="Escribe tu pregunta..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={sendMutation.isPending}
        />
        <button
          type="submit"
          className="poke-btn-primary"
          disabled={sendMutation.isPending || !draft.trim()}
        >
          Enviar
        </button>
      </form>
    </div>
  );
}
