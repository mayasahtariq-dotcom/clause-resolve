import { AlertTriangle, Info, XCircle } from "lucide-react";
import type { InvestigationEvent } from "../api/types";
import type { Connection } from "../hooks/useInvestigationEvents";

const LEVEL = {
  info: { Icon: Info, dot: "bg-lagoon", row: "" },
  warning: { Icon: AlertTriangle, dot: "bg-tangerine", row: "bg-tangerine-soft/70" },
  error: { Icon: XCircle, dot: "bg-bubblegum", row: "bg-bubblegum-soft/80" },
} as const;

const CONNECTION_LABEL: Record<Connection, string> = {
  connecting: "Connecting…",
  live: "Live",
  polling: "Updating every few seconds",
  closed: "Finished",
};

export function EventLog({ events, connection }: { events: InvestigationEvent[]; connection: Connection }) {
  return (
    <section className="card overflow-hidden" aria-labelledby="log-heading">
      <div className="flex items-center justify-between bg-ink px-5 py-3.5 text-white">
        <h3 id="log-heading" className="text-lg">Activity log</h3>
        <span className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-bold">
          <span className="relative flex h-2 w-2">
            {connection === "live" ? <span className="absolute inset-0 animate-ring rounded-full bg-lagoon" /> : null}
            <span className={`relative h-2 w-2 rounded-full ${connection === "closed" ? "bg-white/50" : "bg-lagoon"}`} />
          </span>
          <span>{CONNECTION_LABEL[connection]}</span>
        </span>
      </div>
      {events.length === 0 ? (
        <p className="p-5 text-slate">Waiting for the first update…</p>
      ) : (
        <ol className="relative max-h-[30rem] overflow-y-auto px-3 py-3" aria-live="polite">
          {events.map((e) => {
            const { Icon, dot, row } = LEVEL[e.level] ?? LEVEL.info;
            return (
              <li key={e.seq} className={`relative flex animate-slide-up gap-3 rounded-2xl px-3 py-2.5 text-sm ${row}`}>
                <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${dot} text-ink`}>
                  <Icon className="h-3.5 w-3.5" aria-label={e.level} />
                </span>
                <div className="min-w-0">
                  <p className="font-medium">
                    {e.vendor_name ? (
                      <span className="mr-2 rounded-full bg-sun px-2 py-0.5 text-[11px] font-bold">{e.vendor_name}</span>
                    ) : null}
                    <span className="break-words">{e.message}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-slate">
                    {new Date(e.created_at).toLocaleTimeString()} · {e.stage}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
