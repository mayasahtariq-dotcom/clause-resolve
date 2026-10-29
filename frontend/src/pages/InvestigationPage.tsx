import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, ExternalLink, Globe, PartyPopper } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Investigation, SourceView } from "../api/types";
import { EventLog } from "../components/EventLog";
import { Reveal } from "../components/motion";
import { Pipeline } from "../components/Pipeline";
import { RunStatusBadge } from "../components/StatusBadge";
import { accentFor, ErrorState, LoadingState } from "../components/ui";
import { useInvestigationEvents } from "../hooks/useInvestigationEvents";

function VendorProgress({ inv }: { inv: Investigation }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Vendor progress">
      {inv.vendors.map((v, i) => {
        const working = !inv.is_terminal && (v.status === "researching" || v.status === "extracting");
        return (
          <li
            key={v.id}
            className={`relative animate-pop-in overflow-hidden rounded-3xl p-5 shadow-soft transition duration-300 hover:-translate-y-1 hover:shadow-lift ${
              v.status === "failed" ? "bg-bubblegum-soft" : accentFor(i)
            }`}
            style={{ animationDelay: `${i * 80}ms` }}
          >
            {working ? <span aria-hidden="true" className="shimmer-bar absolute inset-0 opacity-60" /> : null}
            <div className="relative flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/90 font-display text-lg font-extrabold text-ink shadow-soft">
                  {v.name.charAt(0).toUpperCase()}
                </span>
                <p className="truncate font-display text-xl font-extrabold">{v.name}</p>
              </div>
              <RunStatusBadge status={v.status} terminal={inv.is_terminal} />
            </div>
            <p className="relative mt-3 flex items-center gap-1.5 text-sm font-medium">
              <Globe className="h-4 w-4 shrink-0" aria-hidden="true" />
              {v.domain ?? "Finding official site…"}
              {v.domain_source === "search" ? <span className="text-xs opacity-80">(found by search, please verify)</span> : null}
            </p>
            <p className="relative text-sm font-medium opacity-85">
              {v.source_count} policy page{v.source_count === 1 ? "" : "s"} retrieved
            </p>
            {v.error?.message ? (
              <p className="relative mt-3 rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-ink shadow-soft" role="note">
                {v.error.message}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function SourcesList({ inv }: { inv: Investigation }) {
  if (!inv.sources.length) return null;
  const byVendor = new Map<string, SourceView[]>();
  for (const s of inv.sources) byVendor.set(s.vendor_id, [...(byVendor.get(s.vendor_id) ?? []), s]);
  return (
    <section className="card p-6" aria-labelledby="sources-heading">
      <h3 id="sources-heading" className="mb-4 text-lg">Discovered sources</h3>
      <div className="grid gap-5 md:grid-cols-2">
        {inv.vendors
          .filter((v) => byVendor.has(v.id))
          .map((v) => (
            <div key={v.id}>
              <p className="mb-2 text-sm font-bold">{v.name}</p>
              <ul className="space-y-2 text-sm">
                {(byVendor.get(v.id) ?? []).map((s) => (
                  <li key={s.id} className="flex items-start gap-2 rounded-2xl bg-paper px-3 py-2">
                    <span className="rounded-full bg-sun px-2 py-0.5 text-[11px] font-bold">{s.source_key}</span>
                    <div className="min-w-0 flex-1">
                      <a href={s.final_url ?? s.url} target="_blank" rel="noopener noreferrer" className="break-words font-semibold underline decoration-iris/40 decoration-2 underline-offset-2 hover:decoration-iris">
                        {s.title ?? s.url}
                        <ExternalLink className="ml-1 inline h-3 w-3" aria-hidden="true" />
                      </a>
                      {s.injection_suspected ? (
                        <span title="This page contains text addressed to AI systems. It was treated strictly as data." className="mt-1 flex w-fit items-center gap-1 rounded-full bg-tangerine px-2 py-0.5 text-[11px] font-bold">
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
    <div className="space-y-6">
      <Reveal>
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="eyebrow">Investigation · started {new Date(data.created_at).toLocaleString()}</span>
            <h1 className="mt-3 text-4xl leading-tight sm:text-5xl">{data.vendors.map((v) => v.name).join(" vs ")}</h1>
          </div>
          <RunStatusBadge status={data.status} terminal={data.is_terminal} />
        </header>
      </Reveal>

      <Pipeline status={data.status} failedAt={failedStage} />

      {data.is_terminal && data.report_id ? (
        <div
          className={`relative flex animate-pop-in flex-col items-start justify-between gap-4 overflow-hidden rounded-4xl p-6 shadow-lift sm:flex-row sm:items-center ${
            data.status === "partial" ? "bg-tangerine" : "bg-lagoon"
          }`}
        >
          <span aria-hidden="true" className="absolute -right-10 -top-16 h-48 w-48 rounded-full bg-white/25 blur-2xl" />
          <div className="relative flex items-center gap-4">
            <span className="flex h-12 w-12 animate-wiggle items-center justify-center rounded-2xl bg-white shadow-soft">
              <PartyPopper className="h-6 w-6" aria-hidden="true" />
            </span>
            <div>
              <p className="font-display text-2xl font-extrabold">Report ready</p>
              {data.status === "partial" ? (
                <p className="font-medium">{data.error?.message}. Their columns show as unknown.</p>
              ) : (
                <p className="font-medium">Every vendor was investigated.</p>
              )}
            </div>
          </div>
          <Link to={`/reports/${data.report_id}`} className="btn-primary relative">
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
