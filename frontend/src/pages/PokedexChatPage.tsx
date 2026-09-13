import { getChatHistory, resetChatHistory, sendChatMessage } from "@/api/ai";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import type { ChatMessage } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";

export function PokedexChatPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [localHistory, setLocalHistory] = useState<ChatMessage[] | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: history, isLoading } = useQuery({
    queryKey: ["ai", "chat-history"],
    queryFn: getChatHistory,
  });

  const messages = localHistory ?? history ?? [];

  const sendMutation = useMutation({
    mutationFn: sendChatMessage,
    onSuccess: (response) => setLocalHistory(response.history),
  });

  const resetMutation = useMutation({
    mutationFn: resetChatHistory,
    onSuccess: () => {
      setLocalHistory([]);
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
    sendMutation.mutate(message);
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col px-4 py-8" style={{ minHeight: "70vh" }}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="font-display text-3xl font-extrabold">
            ¿Dudas de tu Pokédex? 💬
          </h1>
          <p className="text-poke-ink-soft">
            Pregúntale a Claude Sonnet 5 sobre tu colección — sabe leerla en tiempo real (vía MCP).
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
        {isLoading ? (
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
