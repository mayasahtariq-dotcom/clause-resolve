import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { InvestigationEvent } from "../api/types";

export type Connection = "connecting" | "live" | "polling" | "closed";

function merge(prev: InvestigationEvent[], incoming: InvestigationEvent[]): InvestigationEvent[] {
  if (!incoming.length) return prev;
  const bySeq = new Map(prev.map((e) => [e.seq, e]));
  for (const e of incoming) bySeq.set(e.seq, e);
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
}

/**
 * Streams persisted investigation events over SSE (falls back to polling).
 * Events come from the database, so a page reload or reconnect replays the
 * real history instead of inventing progress.
 */
export function useInvestigationEvents(id: string, terminal: boolean) {
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [connection, setConnection] = useState<Connection>("connecting");
  const queryClient = useQueryClient();
  const cursor = useRef(0);
  const terminalRef = useRef(terminal);
  terminalRef.current = terminal;

  useEffect(() => {
    let disposed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;
    let failures = 0;

    const add = (incoming: InvestigationEvent[]) => {
      if (disposed || !incoming.length) return;
      cursor.current = Math.max(cursor.current, ...incoming.map((e) => e.seq));
      setEvents((prev) => merge(prev, incoming));
    };
    const refresh = () => queryClient.invalidateQueries({ queryKey: ["investigation", id] });

    const poll = async () => {
      try {
        add(await api.events(id, cursor.current));
        await refresh();
        if (terminalRef.current && timer) {
          clearInterval(timer);
          setConnection("closed");
        }
      } catch {
        /* keep polling; the investigation query surfaces API errors */
      }
    };
    const startPolling = () => {
      setConnection("polling");
      void poll();
      timer = setInterval(poll, 2500);
    };

    if (typeof EventSource === "undefined") {
      startPolling();
    } else {
      source = new EventSource(api.eventsUrl(id));
      source.onopen = () => {
        failures = 0;
        setConnection("live");
      };
      source.addEventListener("progress", (e) => add([JSON.parse((e as MessageEvent<string>).data) as InvestigationEvent]));
      source.addEventListener("status", (e) => {
        const status = JSON.parse((e as MessageEvent<string>).data) as { is_terminal: boolean };
        void refresh();
        if (status.is_terminal) {
          source?.close();
          setConnection("closed");
        }
      });
      source.onerror = () => {
        failures += 1;
        if (failures >= 3 && source) {
          source.close();
          source = null;
          startPolling();
        }
      };
    }
    return () => {
      disposed = true;
      source?.close();
      if (timer) clearInterval(timer);
    };
  }, [id, queryClient]);

  return { events, connection };
}
