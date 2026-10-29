import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BadgeCheck,
  Columns3,
  EyeOff,
  Flag,
  Link2,
  MessageSquareText,
  Scale,
  Search,
  Sparkles,
  Zap,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { VendorInput } from "../api/types";
import { HeroMock } from "../components/HeroMock";
import { GlowPill, Reveal, Tilt } from "../components/motion";
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

const TERMS = [
  "Refund windows",
  "Cancellation fees",
  "Free-trial traps",
  "Auto-renewals",
  "Restocking fees",
  "Return shipping",
  "Hidden exclusions",
  "Cancellation deadlines",
];

function Hero() {
  const bars = [
    { label: "Refund", h: "h-[70%]", c: "bg-lagoon" },
    { label: "Cancel", h: "h-[45%]", c: "bg-bubblegum" },
    { label: "Trial", h: "h-[85%]", c: "bg-iris" },
    { label: "Returns", h: "h-[55%]", c: "bg-tangerine" },
  ];
  return (
    <section className="grid gap-4 lg:grid-cols-12" aria-labelledby="hero-title">
      <Reveal className="card relative overflow-hidden p-6 sm:p-10 lg:col-span-8 lg:row-span-2">
        <div className="grid items-center gap-6 md:grid-cols-[1.1fr_1fr]">
          <div>
            <span className="eyebrow">
              <Sparkles className="h-3.5 w-3.5 text-iris" aria-hidden="true" /> AI policy investigator
            </span>
            <h1 id="hero-title" className="mt-5 text-5xl leading-[0.95] sm:text-6xl">
              See beyond the <span className="text-gradient">fine print.</span>
            </h1>
            <p className="mt-5 max-w-md text-lg text-slate">
              Compare refund windows, cancellation rules, hidden fees and free-trial traps across vendors, with every
              answer linked to the exact policy text.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href="#compare" className="btn-primary">
                Start comparing <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
              <a href="#how" className="btn-white">
                See how it works
              </a>
            </div>
          </div>
          <HeroMock />
        </div>
      </Reveal>

      <Reveal delay={120} className="lg:col-span-4">
        <Tilt className="h-full">
          <div className="card relative h-full overflow-hidden bg-sun p-6">
            <p className="font-display text-2xl font-extrabold leading-tight">
              Hidden fees?
              <br />
              <span className="text-ink/60">Caught on the record.</span>
            </p>
            <div className="mt-6 flex h-44 items-end gap-3" aria-hidden="true">
              {bars.map((b, i) => (
                <div key={b.label} className="flex h-full flex-1 flex-col justify-end gap-1.5">
                  <div
                    className={`${b.h} ${b.c} origin-bottom animate-grow-y rounded-xl shadow-soft`}
                    style={{ animationDelay: `${400 + i * 120}ms` }}
                  />
                  <span className="text-center text-[11px] font-bold">{b.label}</span>
                </div>
              ))}
            </div>
          </div>
        </Tilt>
      </Reveal>

      <Reveal delay={220} className="lg:col-span-4">
        <Tilt className="h-full">
          <div className="card relative h-full overflow-hidden bg-ink p-6 text-white">
            <span aria-hidden="true" className="absolute -right-10 -top-10 h-40 w-40 animate-drift rounded-full bg-bubblegum/40 blur-2xl" />
            <p className="relative font-display text-2xl font-extrabold leading-tight">
              Free trial <span className="text-bubblegum">auto-converts?</span>
            </p>
            <p className="relative mt-2 text-sm text-white/70">ClauseLens flags it before your card does.</p>
            <div className="relative mt-5 flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3" aria-hidden="true">
              <span className="text-sm font-semibold">Converts to paid</span>
              <span className="flex h-7 w-12 items-center rounded-full bg-bubblegum p-1">
                <span className="ml-auto h-5 w-5 rounded-full bg-white shadow" />
              </span>
            </div>
          </div>
        </Tilt>
      </Reveal>
    </section>
  );
}

function Marquee() {
  return (
    <div className="relative -mx-4 my-10 overflow-hidden py-2 [mask-image:linear-gradient(90deg,transparent,black_8%,black_92%,transparent)]" aria-hidden="true">
      <div className="flex w-max animate-marquee gap-3">
        {[...TERMS, ...TERMS].map((t, i) => (
          <span key={i} className="chip whitespace-nowrap px-5 py-2 text-base">
            <span className={`h-2 w-2 rounded-full ${["bg-sun", "bg-bubblegum", "bg-lagoon", "bg-iris", "bg-tangerine"][i % 5]}`} />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

const STEPS = [
  { Icon: Search, title: "Investigate", text: "TinyFish finds each vendor's official refund, cancellation and terms pages.", color: "bg-sun" },
  { Icon: Zap, title: "Extract", text: "An AI model pulls out the key terms, each with a verbatim quote.", color: "bg-tangerine" },
  { Icon: BadgeCheck, title: "Verify", text: "Every quote is matched against the real page. Made-up quotes are flagged.", color: "bg-lagoon" },
  { Icon: Columns3, title: "Compare", text: "A transparent scoring engine ranks vendors on your priorities.", color: "bg-bubblegum" },
];

function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-28" aria-labelledby="how-title">
      <Reveal className="mb-8 text-center">
        <h2 id="how-title" className="flex flex-wrap items-center justify-center gap-3 text-4xl sm:text-5xl">
          How it <GlowPill className="bg-iris text-white">works</GlowPill>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-slate">Four steps from scattered fine print to a clear, evidence-backed answer.</p>
      </Reveal>
      <ol className="relative grid gap-4 md:grid-cols-4">
        <span aria-hidden="true" className="absolute left-[12%] right-[12%] top-12 hidden border-t-2 border-dashed border-ink/15 md:block" />
        {STEPS.map(({ Icon, title, text, color }, i) => (
          <Reveal as="li" key={title} delay={i * 110}>
            <Tilt className="h-full">
              <div className="card card-hover relative h-full p-6">
                <span className={`relative flex h-14 w-14 items-center justify-center rounded-2xl ${color} shadow-soft`}>
                  <Icon className="h-6 w-6" aria-hidden="true" />
                  <span className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
                    {i + 1}
                  </span>
                </span>
                <h3 className="mt-5 text-xl">{title}</h3>
                <p className="mt-1.5 text-sm text-slate">{text}</p>
              </div>
            </Tilt>
          </Reveal>
        ))}
      </ol>
    </section>
  );
}

function Benefit({ icon, title, children, className = "", delay = 0 }: { icon: ReactNode; title: string; children: ReactNode; className?: string; delay?: number }) {
  return (
    <Reveal delay={delay} className={className}>
      <div className="card card-hover h-full p-6">
        {icon}
        <h3 className="mt-4 text-xl">{title}</h3>
        <div className="mt-1.5 text-sm text-slate">{children}</div>
      </div>
    </Reveal>
  );
}

function Benefits() {
  return (
    <section className="mt-20" aria-labelledby="benefits-title">
      <Reveal className="mb-8">
        <h2 id="benefits-title" className="text-4xl sm:text-5xl">
          One simple lens.
          <br />
          <span className="text-slate/60">Many </span>
          <span className="text-gradient">worry-free</span>
          <span className="text-slate/60"> decisions.</span>
        </h2>
      </Reveal>
      <div className="grid gap-4 md:grid-cols-6">
        <Reveal className="md:col-span-3">
          <div className="card relative h-full overflow-hidden bg-lagoon p-6">
            <Link2 className="h-7 w-7" aria-hidden="true" />
            <h3 className="mt-4 text-2xl">Evidence you can click</h3>
            <figure className="mt-4 rounded-3xl bg-white p-5 shadow-soft">
              <blockquote className="text-lg font-semibold leading-snug">
                &ldquo;You may request a full refund within the stated window for any individual course.&rdquo;
              </blockquote>
              <figcaption className="mt-3 flex items-center gap-2 text-xs font-bold text-slate">
                <BadgeCheck className="h-4 w-4 text-lagoon" aria-hidden="true" /> Quote verified · example
              </figcaption>
            </figure>
          </div>
        </Reveal>
        <Benefit
          delay={100}
          className="md:col-span-3"
          icon={<span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-bubblegum text-white shadow-glow-pink"><Flag className="h-6 w-6" aria-hidden="true" /></span>}
          title="Risk flags, not guesses"
        >
          When two pages disagree, or a fee isn&apos;t mentioned at all, you see it plainly. A missing fee is never
          treated as $0.
        </Benefit>
        <Benefit
          delay={0}
          className="md:col-span-2"
          icon={<span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sun shadow-glow-sun"><MessageSquareText className="h-6 w-6" aria-hidden="true" /></span>}
          title="Plain English"
        >
          Legalese becomes one-line answers you can act on.
        </Benefit>
        <Benefit
          delay={100}
          className="md:col-span-2"
          icon={<span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-iris text-white shadow-glow-iris"><Scale className="h-6 w-6" aria-hidden="true" /></span>}
          title="Fair, explainable scoring"
        >
          Rules you can read decide the ranking, not the AI.
        </Benefit>
        <Benefit
          delay={200}
          className="md:col-span-2"
          icon={<span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-tangerine shadow-soft"><EyeOff className="h-6 w-6" aria-hidden="true" /></span>}
          title="Zero personal data"
        >
          You only type vendor names. Nothing about you is collected.
        </Benefit>
      </div>
    </section>
  );
}

function RecentInvestigations() {
  const recent = useQuery({ queryKey: ["investigations"], queryFn: () => api.investigations(6) });
  if (recent.isLoading || recent.isError || !recent.data?.items.length) return null;
  return (
    <section id="recent" className="mt-20 scroll-mt-28" aria-labelledby="recent-heading">
      <Reveal>
        <h2 id="recent-heading" className="mb-5 text-3xl">Recent investigations</h2>
      </Reveal>
      <ul className="grid gap-3 md:grid-cols-2">
        {recent.data.items.map((inv, i) => (
          <Reveal as="li" key={inv.id} delay={i * 60}>
            <Link
              to={inv.report_id ? `/reports/${inv.report_id}` : `/investigations/${inv.id}`}
              className="panel-sm card-hover flex items-center justify-between gap-3 p-4"
            >
              <span className="flex min-w-0 items-center gap-3">
                <span className="flex -space-x-2" aria-hidden="true">
                  {inv.vendor_names.slice(0, 3).map((n, j) => (
                    <span key={n} className={`flex h-9 w-9 items-center justify-center rounded-full border-2 border-white font-display text-sm font-extrabold ${["bg-sun", "bg-bubblegum", "bg-lagoon"][j]}`}>
                      {n.charAt(0)}
                    </span>
                  ))}
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-display text-lg font-extrabold">{inv.vendor_names.join(" vs ")}</span>
                  <span className="text-sm text-slate">
                    {new Date(inv.created_at).toLocaleString()} {inv.is_demo ? "· demo" : ""}
                  </span>
                </span>
              </span>
              <RunStatusBadge status={inv.status} terminal />
            </Link>
          </Reveal>
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
  const progress = Math.min(1, vendors.length / 2);

  return (
    <>
      <Hero />
      <Marquee />
      <HowItWorks />
      <Benefits />

      <section id="compare" className="mt-20 scroll-mt-28" aria-labelledby="compare-title">
        <Reveal className="mb-8 text-center">
          <span className="eyebrow">Your comparison</span>
          <h2 id="compare-title" className="mt-4 text-4xl sm:text-5xl">
            Build your <span className="text-gradient">lineup</span>
          </h2>
        </Reveal>

        {meta.isError ? (
          <div className="mb-6">
            <ErrorState
              title="API unavailable"
              message={meta.error instanceof ApiError ? meta.error.message : "The ClauseLens API could not be reached."}
            />
          </div>
        ) : null}

        <div className="card relative overflow-hidden p-5 sm:p-8">
          <span aria-hidden="true" className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-sun/30 blur-3xl" />
          <section aria-labelledby="vendors-heading" className="relative mb-12">
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
                    <Sparkles className="h-4 w-4 text-iris" aria-hidden="true" /> Load demo vendors
                  </button>
                ) : null
              }
            />
            <h3 id="vendors-heading" className="sr-only">Vendors</h3>
            <VendorPicker vendors={vendors} max={max} onChange={setVendors} />
          </section>

          <section aria-labelledby="priorities-heading" className="relative mb-10">
            <SectionHeader number="02" title="What matters most?" subtitle="Optional. Pick up to three, in order." />
            <h3 id="priorities-heading" className="sr-only">Priorities</h3>
            {meta.isLoading ? (
              <LoadingState label="Loading criteria" />
            ) : (
              <PrioritySelector criteria={meta.data?.criteria ?? []} selected={priorities} onChange={setPriorities} />
            )}
          </section>

          <div className="relative overflow-hidden rounded-4xl bg-ink p-6 text-white sm:p-7">
            <span aria-hidden="true" className="absolute -left-10 -top-16 h-48 w-48 animate-drift rounded-full bg-iris/50 blur-3xl" />
            <span aria-hidden="true" className="absolute -bottom-20 right-10 h-48 w-48 animate-drift-slow rounded-full bg-bubblegum/40 blur-3xl" />
            <div className="relative flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center">
              <div>
                <p className="font-display text-2xl font-extrabold">
                  {vendors.length < 2 ? `Add ${2 - vendors.length} more vendor${vendors.length === 1 ? "" : "s"}` : "Ready to investigate"}
                </p>
                <p className="mt-1 text-sm text-white/70">
                  ClauseLens reads each vendor&apos;s official policy pages. This usually takes a minute or two.
                </p>
                <div className="mt-3 h-1.5 w-56 overflow-hidden rounded-full bg-white/15" aria-hidden="true">
                  <div className="h-full rounded-full bg-gradient-to-r from-sun via-bubblegum to-lagoon transition-all duration-500" style={{ width: `${progress * 100}%` }} />
                </div>
              </div>
              <button
                type="button"
                className={`btn bg-sun px-7 py-3.5 text-lg text-ink ${canStart ? "shadow-glow-sun" : ""}`}
                disabled={!canStart}
                onClick={() => create.mutate()}
              >
                {create.isPending ? "Starting…" : "Investigate"} <ArrowRight className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          </div>
          {create.isError ? (
            <div className="relative mt-6">
              <ErrorState
                title="Could not start the investigation"
                message={create.error instanceof ApiError ? create.error.message : "Unexpected error."}
              />
            </div>
          ) : null}
        </div>
      </section>

      <RecentInvestigations />
    </>
  );
}
