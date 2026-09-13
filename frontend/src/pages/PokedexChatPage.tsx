import {
  createChatThread,
  deleteChatThread,
  getChatThreadMessages,
  listChatThreads,
  sendChatMessage,
} from "@/api/ai";
import { getErrorMessage } from "@/api/errors";
import { PokeballSpinner } from "@/components/PokeballSpinner";
import { useAuth } from "@/context/AuthContext";
import type { ChatMessage, ChatThreadSummary } from "@/types";
import {
  clearCachedChatHistory,
  loadCachedActiveThreadId,
  loadCachedChatHistory,
  loadCachedThreadList,
  saveCachedActiveThreadId,
  saveCachedChatHistory,
  saveCachedThreadList,
} from "@/utils/chatHistoryCache";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";


function mergeMessages(preferred: ChatMessage[], fallback: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const merged: ChatMessage[] = [];
  for (const m of [...preferred, ...fallback]) {
    const key = `${m.role}|${m.content}|${m.ts}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(m);
  }
  merged.sort((a, b) => (a.ts ?? "").localeCompare(b.ts ?? ""));
  return merged;
}

/** Mismo patrón para la LISTA de conversaciones: el servidor manda cuando
 * ambos tienen la misma conversación (por id). */
function mergeThreads(preferred: ChatThreadSummary[], fallback: ChatThreadSummary[]): ChatThreadSummary[] {
  const byId = new Map<string, ChatThreadSummary>();
  for (const t of [...fallback, ...preferred]) {
    byId.set(t.id, t);
  }
  return Array.from(byId.values()).sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
}

function formatWhen(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return "";
  }
}

export function PokedexChatPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const userId = user?.id;
  const [draft, setDraft] = useState("");
  const [lastPersistWarning, setLastPersistWarning] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const [activeThreadId, setActiveThreadId] = useState<string | null>(() =>
    userId ? loadCachedActiveThreadId(userId) : null
  );

  const [threads, setThreads] = useState<ChatThreadSummary[]>(() =>
    userId ? loadCachedThreadList(userId) : []
  );

  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    userId && activeThreadId ? loadCachedChatHistory(userId, activeThreadId) : []
  );

  const { data: serverThreads, isLoading: threadsLoading } = useQuery({
    queryKey: ["ai", "chat-threads", userId],
    queryFn: listChatThreads,
    enabled: !!userId,
  });

  // Cuando llega (o cambia) la lista del backend, se fusiona con el caché
  // local y se guarda de nuevo — el caché se "autocura" con lo que Firestore
  // sí pudo confirmar.
  useEffect(() => {
    if (!userId || !serverThreads) return;
    setThreads((prev) => {
      const merged = mergeThreads(serverThreads, prev);
      saveCachedThreadList(userId, merged);
      return merged;
    });
  }, [serverThreads, userId]);

  // Si todavía no hay ninguna conversación activa (primera visita, o la
  // activa se borró) pero sí hay conversaciones guardadas, se abre la más
  // reciente en vez de dejar la vista vacía.
  useEffect(() => {
    if (!activeThreadId && threads.length > 0) {
      setActiveThreadId(threads[0].id);
      if (userId) saveCachedActiveThreadId(userId, threads[0].id);
    }
  }, [threads, activeThreadId, userId]);

  // Al cambiar de conversación activa, arrancar con lo que haya en caché
  // para ESA conversación (no arrastrar los mensajes de la anterior).
  useEffect(() => {
    if (!userId || !activeThreadId) {
      setMessages([]);
      return;
    }
    setMessages(loadCachedChatHistory(userId, activeThreadId));
  }, [userId, activeThreadId]);

  const { data: serverHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["ai", "chat-thread-messages", userId, activeThreadId],
    queryFn: () => getChatThreadMessages(activeThreadId as string),
    enabled: !!userId && !!activeThreadId,
  });

  useEffect(() => {
    if (!userId || !activeThreadId || !serverHistory) return;
    setMessages((prev) => {
      const merged = mergeMessages(serverHistory, prev);
      saveCachedChatHistory(userId, activeThreadId, merged);
      return merged;
    });
  }, [serverHistory, userId, activeThreadId]);

  const newThreadMutation = useMutation({
    mutationFn: createChatThread,
    onSuccess: (thread) => {
      if (userId) {
        const merged = mergeThreads([thread], threads);
        setThreads(merged);
        saveCachedThreadList(userId, merged);
        saveCachedActiveThreadId(userId, thread.id);
      }
      setActiveThreadId(thread.id);
      setMessages([]);
      setLastPersistWarning(false);
      queryClient.invalidateQueries({ queryKey: ["ai", "chat-threads", userId] });
    },
  });

  const deleteThreadMutation = useMutation({
    mutationFn: deleteChatThread,
    onSuccess: (_data, deletedThreadId) => {
      if (!userId) return;
      clearCachedChatHistory(userId, deletedThreadId);
      const remaining = threads.filter((t) => t.id !== deletedThreadId);
      setThreads(remaining);
      saveCachedThreadList(userId, remaining);
      if (activeThreadId === deletedThreadId) {
        const next = remaining[0]?.id ?? null;
        setActiveThreadId(next);
        saveCachedActiveThreadId(userId, next);
      }
      queryClient.invalidateQueries({ queryKey: ["ai", "chat-threads", userId] });
    },
  });

  const sendMutation = useMutation({
    mutationFn: (vars: { message: string; clientHistory: ChatMessage[] }) =>
      sendChatMessage(vars.message, activeThreadId, vars.clientHistory),
    onSuccess: (response) => {
      if (!userId) return;
      setActiveThreadId(response.thread_id);
      saveCachedActiveThreadId(userId, response.thread_id);
      setMessages(response.history);
      saveCachedChatHistory(userId, response.thread_id, response.history);
      setLastPersistWarning(!response.history_persisted);

      // Refresca el título/fecha de esta conversación en la lista sin
      // esperar al refetch completo — así se ve de inmediato en el selector.
      const now = new Date().toISOString();
      setThreads((prev) => {
        const existing = prev.find((t) => t.id === response.thread_id);
        const updated: ChatThreadSummary = existing
          ? { ...existing, updated_at: now, message_count: response.history.length }
          : {
              id: response.thread_id,
              title: titleFromHistory(response.history),
              created_at: now,
              updated_at: now,
              message_count: response.history.length,
            };
        const merged = mergeThreads([updated], prev);
        saveCachedThreadList(userId, merged);
        return merged;
      });
      queryClient.invalidateQueries({ queryKey: ["ai", "chat-threads", userId] });
    },
  });

  function titleFromHistory(history: ChatMessage[]): string {
    const firstUser = history.find((m) => m.role === "user");
    if (!firstUser) return "Nueva conversación";
    const text = firstUser.content.trim();
    return text.length <= 40 ? text : `${text.slice(0, 39).trimEnd()}…`;
  }

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

  const activeThread = threads.find((t) => t.id === activeThreadId) ?? null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-8 md:flex-row" style={{ minHeight: "70vh" }}>
      <aside className="flex shrink-0 flex-col gap-3 md:w-64">
        <div>
          <h1 className="font-display text-2xl font-extrabold">¿Dudas de tu Pokédex? 💬</h1>
          <p className="text-sm text-poke-ink-soft">
            ¡Este es un chat abierto con Claude Haiku 5! Pregúntame lo que quieras sobre tus Pokémon.
          </p>
        </div>

        <button
          type="button"
          className="poke-btn-primary w-full"
          onClick={() => newThreadMutation.mutate()}
          disabled={newThreadMutation.isPending}
        >
          {newThreadMutation.isPending ? "Creando..." : "➕ Iniciar nueva conversación"}
        </button>
        {newThreadMutation.isError && (
          <p className="text-xs text-poke-coral">
            No se pudo crear la conversación: {getErrorMessage(newThreadMutation.error)}
          </p>
        )}
        {deleteThreadMutation.isError && (
          <p className="text-xs text-poke-coral">
            No se pudo eliminar la conversación: {getErrorMessage(deleteThreadMutation.error)}
          </p>
        )}

        <div className="poke-card flex max-h-[50vh] flex-col gap-1 overflow-y-auto p-2 md:max-h-[55vh]">
          <p className="px-2 pb-1 pt-1 text-xs font-semibold uppercase tracking-wide text-poke-ink-soft">
            Tus conversaciones
          </p>
          {threadsLoading && threads.length === 0 && (
            <p className="px-2 py-2 text-xs text-poke-ink-soft">Cargando...</p>
          )}
          {!threadsLoading && threads.length === 0 && (
            <p className="px-2 py-2 text-xs text-poke-ink-soft">
              Todavía no tienes ninguna — dale a "Iniciar nueva conversación" para empezar.
            </p>
          )}
          {threads.map((t) => (
            <div
              key={t.id}
              className={`group flex items-center gap-1 rounded-xl px-2 py-2 text-left text-sm transition-colors ${
                t.id === activeThreadId ? "bg-poke-blue-dark text-white" : "hover:bg-poke-mist"
              }`}
            >
              <button
                type="button"
                className="min-w-0 flex-1 text-left"
                onClick={() => {
                  setActiveThreadId(t.id);
                  if (userId) saveCachedActiveThreadId(userId, t.id);
                }}
              >
                <p className="truncate font-semibold">{t.title}</p>
                <p
                  className={`truncate text-xs ${
                    t.id === activeThreadId ? "text-white/80" : "text-poke-ink-soft"
                  }`}
                >
                  {t.message_count} mensaje{t.message_count === 1 ? "" : "s"}
                  {t.updated_at ? ` · ${formatWhen(t.updated_at)}` : ""}
                </p>
              </button>
              <button
                type="button"
                title="Eliminar esta conversación"
                className={`shrink-0 rounded-full px-1.5 py-0.5 text-xs opacity-0 transition-opacity group-hover:opacity-100 ${
                  t.id === activeThreadId ? "hover:bg-white/20" : "hover:bg-poke-coral/20"
                }`}
                onClick={() => deleteThreadMutation.mutate(t.id)}
                disabled={deleteThreadMutation.isPending}
              >
                🗑️
              </button>
            </div>
          ))}
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        {activeThread && (
          <p className="mb-2 truncate text-sm font-semibold text-poke-ink-soft">
            {activeThread.title}
          </p>
        )}

        <div
          className="poke-card flex flex-1 flex-col gap-3 overflow-y-auto p-4"
          style={{ minHeight: "45vh", maxHeight: "55vh" }}
        >
          {historyLoading && messages.length === 0 ? (
            <PokeballSpinner label="Cargando conversación..." />
          ) : messages.length === 0 ? (
            <div className="m-auto flex max-w-md flex-col items-center gap-3 text-center text-poke-ink-soft">
              <p>
                Este es un chat abierto para preguntarle a la IA cualquier cosa que quieras
                sobre Pokémon — sabe leer tu colección real en tiempo real. Puedes hacer
                consultas como por ejemplo:
              </p>
              <ul className="flex flex-col gap-1 text-sm italic">
                <li>"De mi colección, ¿qué Pokémon es el que tiene más nivel?"</li>
                <li>"De todos los Pokémon que tengo, ¿cómo armarías un equipo de combate?"</li>
                <li>"¿Quién es el Pokémon más débil de mi colección?"</li>
              </ul>
            </div>
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
    </div>
  );
}
