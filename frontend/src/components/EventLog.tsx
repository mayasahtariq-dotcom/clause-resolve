import { AlertTriangle, Info, XCircle } from "lucide-react";
import type { InvestigationEvent } from "../api/types";
import type { Connection } from "../hooks/useInvestigationEvents";

const LEVEL = {
  info: { Icon: Info, cls: "bg-white" },
  warning: { Icon: AlertTriangle, cls: "bg-tangerine-soft" },
  error: { Icon: XCircle, cls: "bg-bubblegum-soft" },
} as const;

const CONNECTION_LABEL: Record<Connection, string> = {
  connecting: "Connecting…",
  live: "Live",
  polling: "Updating every few seconds",
  closed: "Finished",
};

export function EventLog({ events, connection }: { events: InvestigationEvent[]; connection: Connection }) {
  return (
    <section className="panel overflow-hidden" aria-labelledby="log-heading">
      <div className="flex items-center justify-between border-b-4 border-ink bg-ink px-4 py-2 text-sun">
        <h3 id="log-heading" className="text-lg uppercase">Activity log</h3>
        <span className="text-xs font-extrabold uppercase">{CONNECTION_LABEL[connection]}</span>
      </div>
      {events.length === 0 ? (
        <p className="p-4 font-semibold">Waiting for the first update…</p>
      ) : (
        <ol className="max-h-[28rem] divide-y-2 divide-ink/15 overflow-y-auto" aria-live="polite">
          {events.map((e) => {
            const { Icon, cls } = LEVEL[e.level] ?? LEVEL.info;
            return (
              <li key={e.seq} className={`flex gap-3 px-4 py-2.5 text-sm ${cls}`}>
                <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-label={e.level} />
                <div className="min-w-0">
                  <p className="font-semibold">
                    {e.vendor_name ? <span className="mr-2 border-2 border-ink bg-sun px-1 text-xs font-extrabold uppercase">{e.vendor_name}</span> : null}
                    <span className="break-words">{e.message}</span>
                  </p>
                  <p className="text-xs text-slate">
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
