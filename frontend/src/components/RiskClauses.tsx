import { AlertOctagon, ChevronDown, ExternalLink, ShieldAlert, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import type { RiskClause, RiskLevel, VendorRiskAnalysis } from "../api/types";
import { VerificationBadge } from "./StatusBadge";

const LEVEL: Record<RiskLevel, { label: string; pill: string; bar: string; glow: string }> = {
  high: { label: "High risk", pill: "bg-bubblegum text-white", bar: "bg-bubblegum", glow: "shadow-glow-pink" },
  medium: { label: "Medium risk", pill: "bg-tangerine text-ink", bar: "bg-tangerine", glow: "shadow-soft" },
  low: { label: "Low risk", pill: "bg-lagoon text-ink", bar: "bg-lagoon", glow: "shadow-soft" },
};
const FILTERS: (RiskLevel | "all")[] = ["all", "high", "medium", "low"];

function ClauseCard({ clause, vendor }: { clause: RiskClause; vendor: string }) {
  const [open, setOpen] = useState(false);
  const lvl = LEVEL[clause.risk_level];
  const verified = clause.evidence.verification === "verified";
  return (
    <li className="relative animate-pop-in overflow-hidden rounded-3xl bg-white p-5 shadow-soft transition duration-300 hover:-translate-y-0.5 hover:shadow-lift">
      <span aria-hidden="true" className={`absolute inset-y-0 left-0 w-1.5 ${lvl.bar}`} />
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${lvl.pill}`}>{lvl.label}</span>
        {clause.category ? <span className="rounded-full bg-paper px-2.5 py-0.5 text-xs font-bold text-slate">{clause.category}</span> : null}
        {!verified ? <VerificationBadge status={clause.evidence.verification} /> : null}
      </div>
      <h4 className="mt-2 text-lg leading-snug">{clause.clause}</h4>
      <p className="mt-1 text-sm">{clause.explanation}</p>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`${open ? "Hide" : "Show"} why and evidence for ${vendor}: ${clause.clause}`}
        className="mt-3 inline-flex items-center gap-1 rounded-full bg-iris-soft px-3 py-1 text-xs font-bold text-iris-deep transition hover:bg-iris hover:text-white"
      >
        Why it&apos;s risky &amp; evidence
        <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      {open ? (
        <div className="mt-3 animate-slide-up space-y-3">
          <p className="rounded-2xl bg-bubblegum-soft/60 px-4 py-2.5 text-sm">
            <span className="font-bold">Why it&apos;s risky: </span>
            {clause.reason}
          </p>
          <blockquote className="rounded-2xl border-l-4 border-iris bg-paper px-4 py-3 text-sm font-semibold">
            &ldquo;{clause.evidence.quote}&rdquo;
          </blockquote>
          <p className="flex flex-wrap items-center gap-2 text-xs text-slate">
            {verified ? <VerificationBadge status="verified" /> : null}
            <span className="rounded-full bg-sun px-2 py-0.5 font-bold text-ink">{clause.evidence.source_key}</span>
            {clause.evidence.source_url ? (
              <a href={clause.evidence.source_url} target="_blank" rel="noopener noreferrer" className="break-all font-semibold text-iris-deep underline">
                {clause.evidence.source_title ?? clause.evidence.source_url}
                <ExternalLink className="ml-1 inline h-3 w-3" aria-hidden="true" />
              </a>
            ) : null}
            {clause.evidence.retrieved_at ? <span>· retrieved {new Date(clause.evidence.retrieved_at).toLocaleString()}</span> : null}
          </p>
          {!verified ? (
            <p className="rounded-2xl bg-tangerine-soft px-4 py-2 text-xs font-semibold">
              The AI quoted text that ClauseLens could not find on the page, so treat this clause as unconfirmed.
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function VendorRisks({ analysis, filter }: { analysis: VendorRiskAnalysis; filter: RiskLevel | "all" }) {
  const counts = { high: 0, medium: 0, low: 0 };
  for (const c of analysis.clauses) counts[c.risk_level] += 1;
  const shown = analysis.clauses.filter((c) => filter === "all" || c.risk_level === filter);
  return (
    <article className="card p-5 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ink font-display text-lg font-extrabold text-sun">
            {analysis.vendor_name.charAt(0)}
          </span>
          <div>
            <h3 className="text-xl">{analysis.vendor_name}</h3>
            <p className="text-xs text-slate">
              {analysis.status === "skipped"
                ? "Not scanned"
                : `${analysis.chunks_analyzed} of ${analysis.chunks_total} text section${analysis.chunks_total === 1 ? "" : "s"} analysed`}
            </p>
          </div>
        </div>
        <div className="flex gap-1.5" aria-label={`${analysis.vendor_name} risk counts`}>
          {(["high", "medium", "low"] as const).map((l) => (
            <span key={l} className={`rounded-full px-2.5 py-1 text-xs font-bold ${LEVEL[l].pill}`}>
              {counts[l]} {l}
            </span>
          ))}
        </div>
      </header>

      {analysis.status === "failed" ? (
        <p role="note" className="mt-4 flex items-start gap-2 rounded-2xl bg-bubblegum-soft px-4 py-3 text-sm font-semibold">
          <AlertOctagon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          Risk scan failed: {analysis.error ?? "the AI provider could not analyse these pages."}
        </p>
      ) : null}
      {analysis.status !== "failed" && analysis.clauses.length === 0 ? (
        <p className="mt-4 flex items-center gap-2 rounded-2xl bg-lagoon-soft px-4 py-3 text-sm font-semibold">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          {analysis.status === "skipped" ? "No page text was available to scan." : "No risky clauses were flagged in the retrieved pages."}
        </p>
      ) : null}
      {shown.length ? (
        <ul className="mt-4 space-y-3">
          {shown.map((c) => (
            <ClauseCard key={`${c.evidence.source_key}:${c.clause}`} clause={c} vendor={analysis.vendor_name} />
          ))}
        </ul>
      ) : analysis.clauses.length ? (
        <p className="mt-4 text-sm text-slate">No {filter} risk clauses for this vendor.</p>
      ) : null}
      {analysis.warnings.length ? (
        <details className="mt-4 text-xs text-slate">
          <summary className="cursor-pointer font-bold">Scan notes ({analysis.warnings.length})</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {analysis.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}

export function RiskClauses({ risks }: { risks: VendorRiskAnalysis[] | undefined }) {
  const [filter, setFilter] = useState<RiskLevel | "all">("all");
  const totals = useMemo(() => {
    const t = { high: 0, medium: 0, low: 0 };
    for (const r of risks ?? []) for (const c of r.clauses) t[c.risk_level] += 1;
    return t;
  }, [risks]);
  if (!risks?.length) return null;
  return (
    <section aria-labelledby="risks-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">
            <ShieldAlert className="h-3.5 w-3.5 text-bubblegum" aria-hidden="true" /> AI fine-print scan
          </span>
          <h2 id="risks-heading" className="mt-3 text-3xl sm:text-4xl">
            Risky <span className="text-gradient">clauses</span>
          </h2>
          <p className="mt-1 text-sm text-slate">
            {totals.high} high · {totals.medium} medium · {totals.low} low. Every clause quotes the page it came from.
          </p>
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by risk level">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={`btn px-4 py-1.5 font-body text-sm font-semibold capitalize ${filter === f ? "bg-ink text-white shadow-glow-iris" : "bg-white shadow-soft"}`}
            >
              {f === "all" ? "All risks" : `${f}`}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {risks.map((r) => (
          <VendorRisks key={r.vendor_id} analysis={r} filter={filter} />
        ))}
      </div>
      <p className="text-xs text-slate">
        Risk levels are an AI assessment of the retrieved text to help you spot fine print. They are not legal advice.
      </p>
    </section>
  );
}
