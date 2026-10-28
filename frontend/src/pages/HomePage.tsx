import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Columns3, FileSearch, Search, Sparkles, Zap } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { VendorInput } from "../api/types";
import { PrioritySelector, toPriorities } from "../components/PrioritySelector";
import { RunStatusBadge } from "../components/StatusBadge";
import { ErrorState, LoadingState, SectionHeader } from "../components/ui";
import { VendorPicker } from "../components/VendorPicker";
import { useMeta } from "../hooks/useMeta";

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function Hero() {
  return (
    <section className="relative left-1/2 -mt-8 mb-12 w-screen -translate-x-1/2 border-b-4 border-ink bg-sun px-4 pb-12 pt-10 sm:-mt-10 sm:pt-14">
      <div className="mx-auto max-w-4xl text-center">
        <div className="panel mx-auto inline-block px-6 py-8 shadow-brut-lg sm:px-14 sm:py-10">
          <h1 className="text-5xl uppercase leading-none sm:text-7xl md:text-8xl">ClauseLens</h1>
          <p className="mx-auto mt-5 inline-block border-4 border-ink bg-bubblegum px-4 py-2 font-display text-lg font-extrabold uppercase shadow-brut-sm sm:text-2xl" style={{ fontStretch: "87.5%" }}>
            See beyond the fine print
          </p>
        </div>
        <p className="panel-sm mx-auto mt-8 max-w-2xl px-5 py-4 text-lg font-bold">
          Compare refund windows, cancellation rules, hidden fees and free-trial traps across vendors, with a link to the
          exact policy text behind every answer.
        </p>
        <ul className="mt-8 flex flex-wrap justify-center gap-4" aria-label="How it works">
          {[
            { Icon: Search, label: "Investigate" },
            { Icon: Zap, label: "Extract" },
            { Icon: Columns3, label: "Compare" },
          ].map(({ Icon, label }) => (
            <li key={label} className="label-tag bg-white px-4 py-2 text-base">
              <Icon className="h-5 w-5" aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function RecentInvestigations() {
  const recent = useQuery({ queryKey: ["investigations"], queryFn: () => api.investigations(6) });
  if (recent.isLoading || recent.isError || !recent.data?.items.length) return null;
  return (
    <section className="mt-14" aria-labelledby="recent-heading">
      <h2 id="recent-heading" className="mb-4 text-2xl uppercase">Recent investigations</h2>
      <ul className="grid gap-3 md:grid-cols-2">
        {recent.data.items.map((inv) => (
          <li key={inv.id}>
            <Link
              to={inv.report_id ? `/reports/${inv.report_id}` : `/investigations/${inv.id}`}
              className="panel-sm flex items-center justify-between gap-3 p-4 hover:bg-sun-soft"
            >
              <span className="min-w-0">
                <span className="block truncate font-display text-lg font-extrabold uppercase">{inv.vendor_names.join(" vs ")}</span>
                <span className="text-sm font-semibold text-slate">
                  {new Date(inv.created_at).toLocaleString()} {inv.is_demo ? "· demo" : ""}
                </span>
              </span>
              <RunStatusBadge status={inv.status} terminal />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function HomePage() {
  const meta = useMeta();
  const navigate = useNavigate();
  const [vendors, setVendors] = useState<VendorInput[]>([]);
  const [priorities, setPriorities] = useState<string[]>([]);
  const submitKey = useRef(newKey());

  const create = useMutation({
    mutationFn: () => api.createInvestigation(vendors, toPriorities(priorities), submitKey.current),
    onSuccess: (inv) => {
      submitKey.current = newKey();
      navigate(`/investigations/${inv.id}`);
    },
    onError: () => {
      submitKey.current = newKey();
    },
  });

  const max = meta.data?.max_vendors ?? 5;
  const canStart = vendors.length >= 2 && !create.isPending;

  return (
    <>
      <Hero />

      {meta.isError ? (
        <ErrorState
          title="API unavailable"
          message={meta.error instanceof ApiError ? meta.error.message : "The ClauseLens API could not be reached."}
        />
      ) : null}

      <section aria-labelledby="vendors-heading" className="mb-12">
        <SectionHeader
          number="01"
          title="Pick your vendors"
          subtitle="Add two to five services you are choosing between."
          aside={
            meta.data?.demo_mode ? (
              <button
                type="button"
                className="btn-white text-sm"
                onClick={() => setVendors(meta.data.demo_vendors.slice(0, 3).map((v) => ({ name: v.name, domain: v.domain })))}
              >
                <Sparkles className="h-4 w-4" aria-hidden="true" /> Load demo vendors
              </button>
            ) : null
          }
        />
        <h2 id="vendors-heading" className="sr-only">Vendors</h2>
        <VendorPicker vendors={vendors} max={max} onChange={setVendors} />
      </section>

      <section aria-labelledby="priorities-heading" className="mb-12">
        <SectionHeader number="02" title="What matters most?" subtitle="Optional. Pick up to three, in order." />
        <h2 id="priorities-heading" className="sr-only">Priorities</h2>
        {meta.isLoading ? (
          <LoadingState label="Loading criteria" />
        ) : (
          <PrioritySelector criteria={meta.data?.criteria ?? []} selected={priorities} onChange={setPriorities} />
        )}
      </section>

      <section className="panel flex flex-col items-start justify-between gap-4 bg-lagoon p-6 sm:flex-row sm:items-center">
        <div className="flex items-start gap-3">
          <FileSearch className="mt-1 h-7 w-7 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-display text-2xl font-extrabold uppercase" style={{ fontStretch: "87.5%" }}>
              {vendors.length < 2 ? `Add ${2 - vendors.length} more vendor${vendors.length === 1 ? "" : "s"}` : "Ready to investigate"}
            </p>
            <p className="font-semibold">
              ClauseLens reads each vendor&apos;s official policy pages. This usually takes a minute or two.
            </p>
          </div>
        </div>
        <button type="button" className="btn-primary text-lg" disabled={!canStart} onClick={() => create.mutate()}>
          {create.isPending ? "Starting…" : "Investigate"} <ArrowRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </section>
      {create.isError ? (
        <div className="mt-6">
          <ErrorState
            title="Could not start the investigation"
            message={create.error instanceof ApiError ? create.error.message : "Unexpected error."}
          />
        </div>
      ) : null}

      <RecentInvestigations />
    </>
  );
}
