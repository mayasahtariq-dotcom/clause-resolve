import { CheckCircle2, CircleHelp, Flag, MessageSquareText, Sparkles } from "lucide-react";
import type { ComparisonReport } from "../api/types";
import { CountUp } from "./motion";

const CONFIDENCE: Record<string, string> = {
  high: "bg-lagoon text-ink",
  medium: "bg-white text-ink",
  low: "bg-tangerine text-ink",
  insufficient: "bg-bubblegum text-white",
};
const RING_COLORS = ["#00C2CB", "#FF66C4", "#6C5CE7", "#FF8A3D", "#14121F"];

function CoverageRing({ value, color }: { value: number; color: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90" aria-hidden="true">
      <circle cx="32" cy="32" r={r} fill="none" stroke="rgba(20,18,31,0.08)" strokeWidth="8" />
      <circle
        cx="32"
        cy="32"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - value)}
        className="transition-[stroke-dashoffset] duration-1000 ease-out"
      />
    </svg>
  );
}

export function RecommendationPanel({ report }: { report: ComparisonReport }) {
  const rec = report.recommendation;
  const names = new Map(report.vendors.map((v) => [v.id, v.name]));
  const Icon = rec.vendor_id ? CheckCircle2 : CircleHelp;
  return (
    <section className="relative overflow-hidden rounded-5xl bg-sun p-6 shadow-lift sm:p-9" aria-labelledby="rec-heading">
      <span aria-hidden="true" className="absolute -right-16 -top-20 h-72 w-72 animate-drift rounded-full bg-white/35 blur-2xl" />
      <span aria-hidden="true" className="absolute -bottom-24 left-1/3 h-64 w-64 animate-drift-slow rounded-full bg-tangerine/30 blur-3xl" />
      <div className="relative grid gap-8 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-ink px-3 py-1 text-xs font-bold text-sun">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Recommendation
          </span>
          <div className="mt-4 flex items-start gap-3">
            <Icon className="mt-1 h-9 w-9 shrink-0 animate-pop-in" aria-hidden="true" />
            <h2 id="rec-heading" className="text-3xl leading-tight sm:text-4xl">{rec.headline}</h2>
          </div>
          <p className="mt-4">
            <span className={`inline-block rounded-full px-3 py-1 text-xs font-bold shadow-soft ${CONFIDENCE[rec.confidence] ?? "bg-white"}`}>
              Confidence: {rec.confidence}
            </span>
          </p>
          <ul className="mt-5 space-y-2">
            {rec.rationale.map((line) => (
              <li key={line} className="flex gap-2 rounded-2xl bg-white/60 px-4 py-2.5 text-sm font-medium backdrop-blur">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink" aria-hidden="true" />
                {line}
              </li>
            ))}
          </ul>
        </div>
        <div className="glass rounded-4xl p-5" aria-label="Evidence coverage per vendor">
          <p className="text-sm font-bold">Verified coverage</p>
          <ul className="mt-3 space-y-3">
            {Object.entries(rec.coverage).map(([vid, cov], i) => (
              <li key={vid} className="flex items-center gap-3">
                <CoverageRing value={cov} color={RING_COLORS[i % RING_COLORS.length] ?? "#14121F"} />
                <div>
                  <p className="font-display text-lg font-extrabold">{names.get(vid) ?? vid}</p>
                  <p className="text-sm text-slate">
                    <CountUp value={Math.round(cov * 100)} suffix="%" /> verified
                  </p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-slate">
            Share of your weighted priorities backed by verified quotes. Unknown terms are never assumed to be good or bad.
          </p>
        </div>
      </div>
    </section>
  );
}

export function ExplanationPanel({ report }: { report: ComparisonReport }) {
  if (report.explanation_status === "not_requested") return null;
  return (
    <section className="card h-full p-6" aria-labelledby="explain-heading">
      <h3 id="explain-heading" className="flex items-center gap-3 text-lg">
        <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-iris text-white shadow-glow-iris">
          <MessageSquareText className="h-5 w-5" aria-hidden="true" />
        </span>
        In plain English
      </h3>
      {report.explanation ? (
        <>
          <p className="mt-4 text-lg font-medium leading-relaxed">{report.explanation}</p>
          <p className="mt-3 text-xs text-slate">
            Written by a language model from the verified comparison above, and checked to make sure it adds no new numbers.
          </p>
        </>
      ) : (
        <p className="mt-4 font-medium">
          {report.explanation_status === "rejected"
            ? "The AI summary was discarded because it stated facts that are not in the verified comparison."
            : "The AI summary could not be generated. The comparison and reasoning above are unaffected."}
        </p>
      )}
    </section>
  );
}

export function RiskFlags({ report }: { report: ComparisonReport }) {
  if (!report.contradictions.length && !report.missing.length) return null;
  return (
    <section className="relative h-full overflow-hidden rounded-4xl bg-bubblegum p-6 text-ink shadow-glow-pink" aria-labelledby="risk-heading">
      <span aria-hidden="true" className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/25 blur-2xl" />
      <h3 id="risk-heading" className="relative flex items-center gap-3 text-lg">
        <span className="flex h-10 w-10 animate-wiggle items-center justify-center rounded-2xl bg-white shadow-soft">
          <Flag className="h-5 w-5" aria-hidden="true" />
        </span>
        Risk flags
      </h3>
      {report.contradictions.length ? (
        <div className="relative mt-4">
          <p className="text-sm font-bold">Conflicting sources</p>
          <ul className="mt-2 space-y-2">
            {report.contradictions.map((c) => (
              <li key={c} className="rounded-2xl bg-white/90 px-4 py-2.5 text-sm font-medium">{c}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {report.missing.length ? (
        <details className="relative mt-4" open={report.missing.length <= 6}>
          <summary className="cursor-pointer text-sm font-bold">Missing or unverified ({report.missing.length})</summary>
          <ul className="mt-2 space-y-1.5">
            {report.missing.map((m) => (
              <li key={m} className="rounded-2xl bg-white/70 px-4 py-2 text-sm">{m}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
