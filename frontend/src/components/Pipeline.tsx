import { ArrowRight } from "lucide-react";
import type { InvestigationStatus } from "../api/types";

const STEPS = [
  { key: "query", label: "01. Query", sub: "Vendors received" },
  { key: "crawl", label: "02. Research", sub: "Crawl policy pages" },
  { key: "extract", label: "03. Extract", sub: "Parse terms" },
  { key: "validate", label: "04. Validate", sub: "Check quotes" },
  { key: "compare", label: "05. Compare", sub: "Align metrics" },
  { key: "report", label: "06. Report", sub: "Clear advice" },
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
  return (
    <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Investigation progress">
      {STEPS.map((step, i) => {
        const done = i < active || (active === 6 && i <= 5);
        const current = i === active && status !== "completed" && status !== "partial";
        const failed = status === "failed" && i === active;
        const cls = failed ? "bg-bubblegum" : current ? "bg-sun" : done ? "bg-lagoon" : "bg-white";
        return (
          <li key={step.key} className="relative">
            <div
              className={`panel-sm h-full px-3 py-3 text-center ${cls}`}
              aria-current={current ? "step" : undefined}
            >
              <p className="font-display text-sm font-extrabold uppercase" style={{ fontStretch: "87.5%" }}>{step.label}</p>
              <p className="text-sm font-semibold">{step.sub}</p>
              <p className="sr-only">{failed ? "failed" : current ? "in progress" : done ? "done" : "not started"}</p>
            </div>
            {i < STEPS.length - 1 ? (
              <ArrowRight className="absolute -right-3 top-1/2 hidden h-4 w-4 -translate-y-1/2 lg:block" aria-hidden="true" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
