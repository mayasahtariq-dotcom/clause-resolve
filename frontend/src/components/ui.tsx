import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export const ACCENTS = ["bg-sun", "bg-tangerine", "bg-bubblegum", "bg-lagoon", "bg-iris text-white"] as const;

export function accentFor(index: number): string {
  return ACCENTS[index % ACCENTS.length] ?? "bg-sun";
}

export function SectionHeader({
  number,
  title,
  subtitle,
  aside,
}: {
  number: string | number;
  title: string;
  subtitle?: string;
  aside?: ReactNode;
}) {
  return (
    <header className="mb-6 border-b-4 border-ink pb-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <span className="section-number" aria-hidden="true">
            {number}
          </span>
          <div>
            <h2 className="text-2xl uppercase leading-tight sm:text-3xl">{title}</h2>
            {subtitle ? <p className="mt-1 font-semibold">{subtitle}</p> : null}
          </div>
        </div>
        {aside}
      </div>
    </header>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="panel-sm flex items-center gap-3 bg-sun-soft p-5 font-bold">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      {label}…
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div role="alert" className="panel bg-bubblegum p-6">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-1 h-6 w-6 shrink-0" aria-hidden="true" />
        <div>
          <h3 className="text-xl uppercase">{title}</h3>
          <p className="mt-1 font-semibold">{message}</p>
          {action ? <div className="mt-4">{action}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="border-4 border-dashed border-ink bg-white p-8 text-center rounded-brut">
      <Inbox className="mx-auto h-8 w-8" aria-hidden="true" />
      <h3 className="mt-3 text-xl uppercase">{title}</h3>
      <p className="mt-1 font-semibold text-slate">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function DemoBanner() {
  return (
    <div role="note" className="border-b-4 border-ink bg-iris px-4 py-2 text-center font-display font-extrabold uppercase tracking-wide text-white">
      Demo data: fictional vendors from built-in fixtures. No real websites were investigated.
    </div>
  );
}
