import { AlertTriangle, Check, CircleDashed, CircleHelp, Loader2, ShieldAlert, X } from "lucide-react";
import type { FieldStatus, InvestigationStatus, Verification, VendorRunStatus } from "../api/types";

const FIELD: Record<FieldStatus, { label: string; cls: string; Icon: typeof Check; hint: string }> = {
  found: { label: "Verified", cls: "bg-lagoon", Icon: Check, hint: "Quote matched the retrieved policy page" },
  unverified: { label: "Unverified", cls: "bg-tangerine", Icon: ShieldAlert, hint: "Quote could not be found in the page" },
  ambiguous: { label: "Ambiguous", cls: "bg-iris-soft", Icon: CircleHelp, hint: "Clause exists but does not state a clear value" },
  contradictory: { label: "Conflicting", cls: "bg-bubblegum", Icon: AlertTriangle, hint: "Sources disagree" },
  not_found: { label: "Not stated", cls: "bg-white border-dashed", Icon: CircleDashed, hint: "Not stated in any retrieved page" },
  unknown: { label: "Unknown", cls: "bg-slate-soft", Icon: CircleHelp, hint: "Could not be analysed" },
};

export function FieldStatusBadge({ status }: { status: FieldStatus }) {
  const { label, cls, Icon, hint } = FIELD[status];
  return (
    <span
      title={hint}
      className={`inline-flex items-center gap-1 border-2 border-ink px-1.5 py-0.5 text-[11px] font-extrabold uppercase tracking-wide ${cls}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  );
}

const VERIFICATION: Record<Verification, { label: string; cls: string }> = {
  verified: { label: "Quote verified", cls: "bg-lagoon" },
  not_in_source: { label: "Quote not found in page", cls: "bg-tangerine" },
  source_missing: { label: "Cited source missing", cls: "bg-bubblegum" },
};

export function VerificationBadge({ status }: { status: Verification }) {
  const { label, cls } = VERIFICATION[status];
  return <span className={`border-2 border-ink px-2 py-0.5 text-xs font-extrabold uppercase ${cls}`}>{label}</span>;
}

const RUN: Record<InvestigationStatus | VendorRunStatus, { label: string; cls: string }> = {
  queued: { label: "Queued", cls: "bg-white" },
  pending: { label: "Waiting", cls: "bg-white" },
  running: { label: "Researching", cls: "bg-sun" },
  researching: { label: "Researching", cls: "bg-sun" },
  extracting: { label: "Extracting", cls: "bg-tangerine" },
  validating: { label: "Validating", cls: "bg-iris text-white" },
  comparing: { label: "Comparing", cls: "bg-iris text-white" },
  completed: { label: "Completed", cls: "bg-lagoon" },
  partial: { label: "Partial", cls: "bg-tangerine" },
  failed: { label: "Failed", cls: "bg-bubblegum" },
};

export function RunStatusBadge({ status, terminal }: { status: InvestigationStatus | VendorRunStatus; terminal?: boolean }) {
  const { label, cls } = RUN[status];
  const active = !terminal && !["completed", "partial", "failed", "pending", "queued"].includes(status);
  const Icon = status === "failed" ? X : status === "completed" ? Check : active ? Loader2 : null;
  return (
    <span className={`inline-flex items-center gap-1.5 border-3 border-ink px-2.5 py-1 text-xs font-extrabold uppercase tracking-wide shadow-brut-sm ${cls}`}>
      {Icon ? <Icon className={`h-3.5 w-3.5 ${active ? "animate-spin" : ""}`} aria-hidden="true" /> : null}
      {label}
    </span>
  );
}
