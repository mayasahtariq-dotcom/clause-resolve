import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { ComparisonMatrix, type EvidenceTarget } from "../components/ComparisonMatrix";
import { EvidenceDialog } from "../components/EvidenceDialog";
import { FALLBACK_LABELS } from "../components/fieldGroups";
import { PrioritySelector, toPriorities } from "../components/PrioritySelector";
import { ExplanationPanel, RecommendationPanel, RiskFlags } from "../components/RecommendationPanel";
import { Reveal } from "../components/motion";
import { ErrorState, LoadingState } from "../components/ui";
import { useMeta } from "../hooks/useMeta";

export function ReportPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const meta = useMeta();
  const report = useQuery({ queryKey: ["report", id], queryFn: () => api.report(id) });
  const [target, setTarget] = useState<EvidenceTarget | null>(null);
  const evidence = useQuery({ queryKey: ["evidence", id], queryFn: () => api.evidence(id), enabled: target !== null });
  const [priorities, setPriorities] = useState<string[]>([]);

  const labels = useMemo(
    () => ({ ...FALLBACK_LABELS, ...Object.fromEntries((meta.data?.fields ?? []).map((f) => [f.key, f.label])) }),
    [meta.data],
  );
  const recompare = useMutation({
    mutationFn: () => api.recompare(report.data?.vendors.map((v) => v.id) ?? [], toPriorities(priorities)),
    onSuccess: (r) => navigate(`/reports/${r.id}`),
  });
  const closeEvidence = useCallback(() => setTarget(null), []);

  if (report.isLoading) return <LoadingState label="Loading report" />;
  if (report.isError || !report.data) {
    return (
      <ErrorState
        title="Report unavailable"
        message={report.error instanceof ApiError ? report.error.message : "Report not found."}
        action={<Link to="/" className="btn-white">Back home</Link>}
      />
    );
  }
  const data = report.data;

  return (
    <div className="space-y-6">
      <Reveal>
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="eyebrow">
              Report · {data.vendors.length} vendors · generated {new Date(data.created_at).toLocaleString()}
            </span>
            <h1 className="mt-3 text-4xl leading-tight sm:text-5xl">
              Side-by-side <span className="text-gradient">comparison</span>
            </h1>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.is_demo ? <span className="label-tag bg-iris text-white shadow-glow-iris">Demo data</span> : null}
            {data.investigation_id ? (
              <Link to={`/investigations/${data.investigation_id}`} className="btn-white px-4 py-2 text-sm">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Investigation
              </Link>
            ) : null}
          </div>
        </header>
      </Reveal>

      <Reveal delay={80}>
        <RecommendationPanel report={data} />
      </Reveal>
      <Reveal delay={140}>
        <ComparisonMatrix report={data} labels={labels} onEvidence={setTarget} />
      </Reveal>
      <div className="grid gap-6 lg:grid-cols-2">
        <Reveal>
          <RiskFlags report={data} />
        </Reveal>
        <Reveal delay={100}>
          <ExplanationPanel report={data} />
        </Reveal>
      </div>

      <Reveal>
        <details className="card group p-6">
          <summary className="flex cursor-pointer list-none items-center justify-between font-display text-lg font-extrabold">
            How the scoring works
            <span className="rounded-full bg-paper px-3 py-1 text-xs font-bold transition group-open:bg-sun">Details</span>
          </summary>
          <ul className="mt-4 space-y-2 text-sm">
            {data.criteria.map((c) => (
              <li key={c.criterion} className="rounded-2xl bg-paper px-4 py-2.5">{c.explanation}</li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-slate">
            Scores come from deterministic rules applied to verified values only. The language model extracts quotes and
            writes the plain-English summary; it never sets scores or picks the winner.
          </p>
        </details>
      </Reveal>

      <Reveal>
        <section className="card relative overflow-hidden p-6 sm:p-8" aria-labelledby="reprioritise-heading">
          <span aria-hidden="true" className="absolute -right-20 -top-20 h-56 w-56 rounded-full bg-lagoon/25 blur-3xl" />
          <h3 id="reprioritise-heading" className="relative text-2xl">Change your priorities</h3>
          <p className="relative mb-5 mt-1 text-sm text-slate">Re-scores the same verified evidence instantly. No websites are re-read.</p>
          <div className="relative">
            <PrioritySelector criteria={meta.data?.criteria ?? []} selected={priorities} onChange={setPriorities} />
          </div>
          <button
            type="button"
            className="btn-iris relative mt-5"
            disabled={!priorities.length || recompare.isPending}
            onClick={() => recompare.mutate()}
          >
            <RefreshCw className={`h-4 w-4 ${recompare.isPending ? "animate-spin" : ""}`} aria-hidden="true" />{" "}
            {recompare.isPending ? "Re-scoring…" : "Re-score"}
          </button>
          {recompare.isError ? (
            <p role="alert" className="relative mt-3 font-semibold">
              {recompare.error instanceof ApiError ? recompare.error.message : "Could not re-score."}
            </p>
          ) : null}
        </section>
      </Reveal>

      <p className="rounded-3xl bg-white/70 px-5 py-3 text-sm text-slate shadow-inset">{data.disclaimer}</p>

      {target ? (
        <EvidenceDialog
          target={target}
          fieldLabel={labels[target.field] ?? target.field}
          evidence={evidence.data?.items}
          loading={evidence.isLoading}
          error={evidence.isError ? "Could not load evidence." : null}
          onClose={closeEvidence}
        />
      ) : null}
    </div>
  );
}
