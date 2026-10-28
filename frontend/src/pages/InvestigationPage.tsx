import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, ExternalLink, Globe } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Investigation, SourceView } from "../api/types";
import { EventLog } from "../components/EventLog";
import { Pipeline } from "../components/Pipeline";
import { RunStatusBadge } from "../components/StatusBadge";
import { accentFor, ErrorState, LoadingState, SectionHeader } from "../components/ui";
import { useInvestigationEvents } from "../hooks/useInvestigationEvents";

function VendorProgress({ inv }: { inv: Investigation }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Vendor progress">
      {inv.vendors.map((v, i) => (
        <li key={v.id} className={`panel-sm p-4 ${v.status === "failed" ? "bg-bubblegum-soft" : accentFor(i)}`}>
          <div className="flex items-start justify-between gap-2">
            <p className="font-display text-xl font-extrabold uppercase">{v.name}</p>
            <RunStatusBadge status={v.status} terminal={inv.is_terminal} />
          </div>
          <p className="mt-2 flex items-center gap-1 text-sm font-semibold">
            <Globe className="h-4 w-4 shrink-0" aria-hidden="true" />
            {v.domain ?? "Finding official site…"}
            {v.domain_source === "search" ? <span className="ml-1 text-xs">(found by search, please verify)</span> : null}
          </p>
          <p className="text-sm font-semibold">{v.source_count} policy page{v.source_count === 1 ? "" : "s"} retrieved</p>
          {v.error?.message ? (
            <p className="mt-2 border-2 border-ink bg-white px-2 py-1 text-sm font-bold" role="note">
              {v.error.message}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function SourcesList({ inv }: { inv: Investigation }) {
  if (!inv.sources.length) return null;
  const byVendor = new Map<string, SourceView[]>();
  for (const s of inv.sources) byVendor.set(s.vendor_id, [...(byVendor.get(s.vendor_id) ?? []), s]);
  return (
    <section className="panel p-5" aria-labelledby="sources-heading">
      <h3 id="sources-heading" className="mb-3 text-lg uppercase">Discovered sources</h3>
      <div className="grid gap-4 md:grid-cols-2">
        {inv.vendors
          .filter((v) => byVendor.has(v.id))
          .map((v) => (
            <div key={v.id}>
              <p className="mb-1 font-extrabold uppercase">{v.name}</p>
              <ul className="space-y-1.5 text-sm">
                {(byVendor.get(v.id) ?? []).map((s) => (
                  <li key={s.id} className="flex items-start gap-2">
                    <span className="border-2 border-ink bg-sun px-1 text-xs font-extrabold">{s.source_key}</span>
                    <div className="min-w-0 flex-1">
                      <a href={s.final_url ?? s.url} target="_blank" rel="noopener noreferrer" className="break-words font-semibold underline decoration-2 underline-offset-2">
                        {s.title ?? s.url}
                        <ExternalLink className="ml-1 inline h-3 w-3" aria-hidden="true" />
                      </a>
                      {s.injection_suspected ? (
                        <span title="This page contains text addressed to AI systems. It was treated strictly as data." className="mt-1 flex w-fit items-center gap-1 border-2 border-ink bg-tangerine px-1 text-xs font-extrabold uppercase">
                          <AlertTriangle className="h-3 w-3" aria-hidden="true" /> AI-directed text, treated as data
                        </span>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </div>
    </section>
  );
}

export function InvestigationPage() {
  const { id = "" } = useParams();
  const inv = useQuery({
    queryKey: ["investigation", id],
    queryFn: () => api.investigation(id),
    refetchInterval: (q) => (q.state.data?.is_terminal ? false : 5000),
  });
  const { events, connection } = useInvestigationEvents(id, inv.data?.is_terminal ?? false);

  if (inv.isLoading) return <LoadingState label="Loading investigation" />;
  if (inv.isError || !inv.data) {
    const message = inv.error instanceof ApiError ? inv.error.message : "Investigation not found.";
    return <ErrorState title="Investigation unavailable" message={message} action={<Link to="/" className="btn-white">Back home</Link>} />;
  }
  const data = inv.data;
  const failedStage = data.error?.stage === "queue" ? 0 : data.error?.stage === "comparison" ? 4 : 1;

  return (
    <div className="space-y-8">
      <SectionHeader
        number="03"
        title={data.vendors.map((v) => v.name).join(" vs ")}
        subtitle={`Started ${new Date(data.created_at).toLocaleString()}`}
        aside={<RunStatusBadge status={data.status} terminal={data.is_terminal} />}
      />
      <Pipeline status={data.status} failedAt={failedStage} />

      {data.is_terminal && data.report_id ? (
        <div className={`panel flex flex-col items-start justify-between gap-4 p-5 sm:flex-row sm:items-center ${data.status === "partial" ? "bg-tangerine" : "bg-lagoon"}`}>
          <div>
            <p className="font-display text-2xl font-extrabold uppercase" style={{ fontStretch: "87.5%" }}>Report ready</p>
            {data.status === "partial" ? (
              <p className="font-semibold">{data.error?.message}. Their columns show as unknown.</p>
            ) : (
              <p className="font-semibold">Every vendor was investigated.</p>
            )}
          </div>
          <Link to={`/reports/${data.report_id}`} className="btn-primary">
            View comparison <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Link>
        </div>
      ) : null}
      {data.status === "failed" ? (
        <ErrorState
          title="Investigation failed"
          message={data.error?.message ?? "The investigation could not be completed."}
          action={<Link to="/" className="btn-white">Try again</Link>}
        />
      ) : null}

      <VendorProgress inv={data} />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <EventLog events={events} connection={connection} />
        <SourcesList inv={data} />
      </div>
    </div>
  );
}
