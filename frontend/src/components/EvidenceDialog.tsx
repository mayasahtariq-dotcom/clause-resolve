import { ExternalLink, Quote, X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Evidence } from "../api/types";
import type { EvidenceTarget } from "./ComparisonMatrix";
import { VerificationBadge } from "./StatusBadge";
import { ErrorState, LoadingState } from "./ui";

interface Props {
  target: EvidenceTarget;
  fieldLabel: string;
  evidence: Evidence[] | undefined;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export function EvidenceDialog({ target, fieldLabel, evidence, loading, error, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const items = (evidence ?? []).filter((e) => target.evidenceIds.includes(e.id));

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-end justify-center bg-ink/40 p-0 backdrop-blur-sm sm:items-center sm:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        className="max-h-[88vh] w-full max-w-2xl animate-slide-up overflow-y-auto rounded-t-5xl bg-paper shadow-lift sm:rounded-5xl"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 bg-paper/90 px-6 pb-4 pt-6 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-iris text-white shadow-glow-iris">
              <Quote className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-slate">Evidence · {target.vendorName}</p>
              <h2 id="evidence-title" className="text-2xl">{fieldLabel}</h2>
            </div>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} className="rounded-full bg-white p-2 shadow-soft transition hover:rotate-90" aria-label="Close evidence">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="space-y-4 px-6 pb-6">
          {loading ? <LoadingState label="Loading evidence" /> : null}
          {error ? <ErrorState message={error} /> : null}
          {!loading && !error && items.length === 0 ? <p>No evidence recorded for this cell.</p> : null}
          {items.map((e, i) => (
            <article key={e.id} className="card animate-slide-up p-5" style={{ animationDelay: `${i * 90}ms` }}>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <VerificationBadge status={e.verification} />
                <span className="rounded-full bg-sun px-2 py-0.5 text-xs font-bold">{e.source_key}</span>
              </div>
              <blockquote className="rounded-3xl border-l-4 border-bubblegum bg-paper px-5 py-4 text-lg font-semibold leading-snug">
                &ldquo;{e.quote}&rdquo;
              </blockquote>
              {e.verification !== "verified" ? (
                <p className="mt-3 rounded-2xl bg-tangerine-soft px-4 py-2 text-sm font-semibold">
                  This quote was proposed by the model but could not be matched to the retrieved page, so it is not
                  treated as fact.
                </p>
              ) : null}
              <dl className="mt-4 grid gap-x-4 gap-y-1.5 text-sm sm:grid-cols-[7rem_1fr]">
                <dt className="font-bold text-slate">Source</dt>
                <dd className="break-all">
                  {e.source_url ? (
                    <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="font-semibold text-iris-deep underline decoration-2 underline-offset-2">
                      {e.source_title ?? e.source_url}
                      <ExternalLink className="ml-1 inline h-3 w-3" aria-hidden="true" />
                    </a>
                  ) : (
                    "Not available"
                  )}
                </dd>
                <dt className="font-bold text-slate">Retrieved</dt>
                <dd>{e.retrieved_at ? new Date(e.retrieved_at).toLocaleString() : "Unknown"}</dd>
                <dt className="font-bold text-slate">Extracted by</dt>
                <dd>
                  {[e.extraction.provider, e.extraction.model].filter(Boolean).join(" · ") || "Unknown"}
                  {e.match_method ? ` (match: ${e.match_method})` : ""}
                </dd>
              </dl>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
