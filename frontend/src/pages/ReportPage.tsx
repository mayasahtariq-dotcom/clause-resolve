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
import { ErrorState, LoadingState, SectionHeader } from "../components/ui";
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
    <div className="space-y-8">
      <SectionHeader
        number="04"
        title="Side-by-side comparison"
        subtitle={`${data.vendors.map((v) => v.name).join(" · ")} · generated ${new Date(data.created_at).toLocaleString()}`}
        aside={
          <div className="flex flex-wrap gap-2">
            {data.is_demo ? <span className="label-tag bg-iris text-white">Demo data</span> : null}
            {data.investigation_id ? (
              <Link to={`/investigations/${data.investigation_id}`} className="btn-white text-sm">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Investigation
              </Link>
            ) : null}
          </div>
        }
      />

      <RecommendationPanel report={data} />
      <ComparisonMatrix report={data} labels={labels} onEvidence={setTarget} />
      <div className="grid gap-6 lg:grid-cols-2">
        <RiskFlags report={data} />
        <ExplanationPanel report={data} />
      </div>

      <details className="panel-sm bg-white p-4">
        <summary className="cursor-pointer font-display text-lg font-extrabold uppercase">How the scoring works</summary>
        <ul className="mt-3 space-y-2 text-sm font-semibold">
          {data.criteria.map((c) => (
            <li key={c.criterion}>{c.explanation}</li>
          ))}
        </ul>
        <p className="mt-3 text-sm">
          Scores come from deterministic rules applied to verified values only. The language model extracts quotes and
          writes the plain-English summary; it never sets scores or picks the winner.
        </p>
      </details>

      <section className="panel bg-white p-5" aria-labelledby="reprioritise-heading">
        <h3 id="reprioritise-heading" className="mb-3 text-lg uppercase">Change your priorities</h3>
        <p className="mb-4 text-sm font-semibold">Re-scores the same verified evidence instantly. No websites are re-read.</p>
        <PrioritySelector criteria={meta.data?.criteria ?? []} selected={priorities} onChange={setPriorities} />
        <button
          type="button"
          className="btn-primary mt-4"
          disabled={!priorities.length || recompare.isPending}
          onClick={() => recompare.mutate()}
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> {recompare.isPending ? "Re-scoring…" : "Re-score"}
        </button>
        {recompare.isError ? (
          <p role="alert" className="mt-3 font-bold">
            {recompare.error instanceof ApiError ? recompare.error.message : "Could not re-score."}
          </p>
        ) : null}
      </section>

      <p className="border-l-8 border-ink bg-white px-4 py-3 text-sm font-semibold">{data.disclaimer}</p>

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
