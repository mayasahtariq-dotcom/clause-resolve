import { CheckCircle2, CircleHelp, Flag, MessageSquareText } from "lucide-react";
import type { ComparisonReport } from "../api/types";

const CONFIDENCE: Record<string, string> = {
  high: "bg-lagoon",
  medium: "bg-sun-soft",
  low: "bg-tangerine",
  insufficient: "bg-bubblegum",
};

export function RecommendationPanel({ report }: { report: ComparisonReport }) {
  const rec = report.recommendation;
  const names = new Map(report.vendors.map((v) => [v.id, v.name]));
  const Icon = rec.vendor_id ? CheckCircle2 : CircleHelp;
  return (
    <section className="panel bg-sun p-5 sm:p-6" aria-labelledby="rec-heading">
      <div className="flex items-start gap-4">
        <Icon className="mt-1 h-9 w-9 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-extrabold uppercase">Recommendation</p>
          <h2 id="rec-heading" className="text-2xl uppercase leading-tight sm:text-3xl">{rec.headline}</h2>
          <p className="mt-2">
            <span className={`inline-block border-3 border-ink px-2 py-0.5 text-xs font-extrabold uppercase ${CONFIDENCE[rec.confidence] ?? "bg-white"}`}>
              Confidence: {rec.confidence}
            </span>
          </p>
          <ul className="mt-4 list-disc space-y-1 pl-5 font-semibold">
            {rec.rationale.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3" aria-label="Evidence coverage per vendor">
            {Object.entries(rec.coverage).map(([vid, cov]) => (
              <div key={vid} className="border-3 border-ink bg-white px-3 py-2">
                <div className="flex justify-between text-sm font-extrabold uppercase">
                  <span>{names.get(vid) ?? vid}</span>
                  <span>{Math.round(cov * 100)}% verified</span>
                </div>
                <div className="mt-1 h-3 border-2 border-ink bg-paper" role="presentation">
                  <div className="h-full bg-ink" style={{ width: `${Math.round(cov * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs font-semibold">
            Coverage is the share of your weighted priorities backed by verified quotes. Unknown terms are never assumed
            to be good or bad.
          </p>
        </div>
      </div>
    </section>
  );
}

export function ExplanationPanel({ report }: { report: ComparisonReport }) {
  if (report.explanation_status === "not_requested") return null;
  return (
    <section className="panel bg-white p-5" aria-labelledby="explain-heading">
      <h3 id="explain-heading" className="flex items-center gap-2 text-lg uppercase">
        <MessageSquareText className="h-5 w-5" aria-hidden="true" /> In plain English
      </h3>
      {report.explanation ? (
        <>
          <p className="mt-2 text-lg font-semibold">{report.explanation}</p>
          <p className="mt-2 text-xs font-semibold text-slate">
            Written by a language model from the verified comparison above, and checked to make sure it adds no new numbers.
          </p>
        </>
      ) : (
        <p className="mt-2 font-semibold">
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
    <section className="panel bg-bubblegum p-5" aria-labelledby="risk-heading">
      <h3 id="risk-heading" className="flex items-center gap-2 text-lg uppercase">
        <Flag className="h-5 w-5" aria-hidden="true" /> Risk flags
      </h3>
      {report.contradictions.length ? (
        <div className="mt-3">
          <p className="font-extrabold uppercase">Conflicting sources</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 font-semibold">
            {report.contradictions.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {report.missing.length ? (
        <details className="mt-3" open={report.missing.length <= 6}>
          <summary className="cursor-pointer font-extrabold uppercase">Missing or unverified ({report.missing.length})</summary>
          <ul className="mt-1 list-disc space-y-1 pl-5 font-semibold">
            {report.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
