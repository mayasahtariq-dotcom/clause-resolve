import { ExternalLink, X } from "lucide-react";
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
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/60 p-0 sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby="evidence-title" className="panel max-h-[90vh] w-full max-w-2xl overflow-y-auto bg-paper">
        <div className="sticky top-0 flex items-start justify-between gap-3 border-b-4 border-ink bg-sun px-5 py-4">
          <div>
            <p className="text-xs font-extrabold uppercase">Evidence · {target.vendorName}</p>
            <h2 id="evidence-title" className="text-2xl uppercase">{fieldLabel}</h2>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} className="border-3 border-ink bg-white p-1.5 shadow-brut-sm" aria-label="Close evidence">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="space-y-4 p-5">
          {loading ? <LoadingState label="Loading evidence" /> : null}
          {error ? <ErrorState message={error} /> : null}
          {!loading && !error && items.length === 0 ? <p className="font-semibold">No evidence recorded for this cell.</p> : null}
          {items.map((e) => (
            <article key={e.id} className="panel-sm bg-white p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <VerificationBadge status={e.verification} />
                <span className="border-2 border-ink bg-sun px-1 text-xs font-extrabold">{e.source_key}</span>
              </div>
              <blockquote className="border-l-8 border-bubblegum bg-paper px-4 py-3 text-lg font-semibold">&ldquo;{e.quote}&rdquo;</blockquote>
              {e.verification !== "verified" ? (
                <p className="mt-2 text-sm font-bold">
                  This quote was proposed by the model but could not be matched to the retrieved page, so it is not
                  treated as fact.
                </p>
              ) : null}
              <dl className="mt-3 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[8rem_1fr]">
                <dt className="font-extrabold uppercase">Source</dt>
                <dd className="break-all">
                  {e.source_url ? (
                    <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="font-semibold underline decoration-2 underline-offset-2">
                      {e.source_title ?? e.source_url}
                      <ExternalLink className="ml-1 inline h-3 w-3" aria-hidden="true" />
                    </a>
                  ) : (
                    "Not available"
                  )}
                </dd>
                <dt className="font-extrabold uppercase">Retrieved</dt>
                <dd>{e.retrieved_at ? new Date(e.retrieved_at).toLocaleString() : "Unknown"}</dd>
                <dt className="font-extrabold uppercase">Extracted by</dt>
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
