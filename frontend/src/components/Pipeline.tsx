import { BadgeCheck, Check, Columns3, FileText, Inbox, Search, X, Zap } from "lucide-react";
import type { InvestigationStatus } from "../api/types";

const STEPS = [
  { key: "query", label: "01. Query", sub: "Vendors received", Icon: Inbox },
  { key: "crawl", label: "02. Research", sub: "Crawl policy pages", Icon: Search },
  { key: "extract", label: "03. Extract", sub: "Parse terms", Icon: Zap },
  { key: "validate", label: "04. Validate", sub: "Check quotes", Icon: BadgeCheck },
  { key: "compare", label: "05. Compare", sub: "Align metrics", Icon: Columns3 },
  { key: "report", label: "06. Report", sub: "Clear advice", Icon: FileText },
] as const;

const ACTIVE_INDEX: Record<InvestigationStatus, number> = {
  queued: 0,
  running: 1,
  extracting: 2,
  validating: 3,
  comparing: 4,
  completed: 6,
  partial: 6,
  failed: -1,
};

export function Pipeline({ status, failedAt }: { status: InvestigationStatus; failedAt?: number }) {
  const active = status === "failed" ? (failedAt ?? 1) : ACTIVE_INDEX[status];
  const finished = status === "completed" || status === "partial";
  const pct = finished ? 100 : Math.max(0, (active / (STEPS.length - 1)) * 100);
  return (
    <div className="card relative overflow-hidden p-5 sm:p-7">
      <div className="mb-6 h-2 overflow-hidden rounded-full bg-paper" aria-hidden="true">
        <div
          className={`relative h-full rounded-full transition-all duration-700 ease-out ${status === "failed" ? "bg-bubblegum" : "bg-gradient-to-r from-sun via-tangerine to-lagoon"}`}
          style={{ width: `${pct}%` }}
        >
          {!finished && status !== "failed" ? <span className="shimmer-bar absolute inset-0 rounded-full" /> : null}
        </div>
      </div>
      <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Investigation progress">
        {STEPS.map(({ key, label, sub, Icon }, i) => {
          const done = i < active || (active === 6 && i <= 5);
          const current = i === active && !finished;
          const failed = status === "failed" && i === active;
          const tone = failed
            ? "bg-bubblegum text-white shadow-glow-pink"
            : current
              ? "bg-sun shadow-glow-sun"
              : done
                ? "bg-lagoon-soft"
                : "bg-paper text-slate";
          const StateIcon = failed ? X : done ? Check : Icon;
          return (
            <li key={key}>
              <div
                className={`relative h-full rounded-3xl px-3 py-4 text-center transition duration-500 ${tone}`}
                aria-current={current ? "step" : undefined}
              >
                <span className="relative mx-auto mb-2 flex h-10 w-10 items-center justify-center">
                  {current ? <span aria-hidden="true" className="absolute inset-0 animate-ring rounded-full bg-tangerine" /> : null}
                  <span className={`relative flex h-10 w-10 items-center justify-center rounded-full ${done ? "bg-lagoon text-ink" : "bg-white text-ink"} shadow-soft`}>
                    <StateIcon className="h-5 w-5" aria-hidden="true" />
                  </span>
                </span>
                <p className="font-display text-sm font-extrabold">{label}</p>
                <p className="text-xs font-medium opacity-80">{sub}</p>
                <p className="sr-only">{failed ? "failed" : current ? "in progress" : done ? "done" : "not started"}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
