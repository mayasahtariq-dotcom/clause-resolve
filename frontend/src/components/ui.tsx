import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, Sparkles } from "lucide-react";

export const ACCENTS = ["bg-sun", "bg-tangerine", "bg-bubblegum", "bg-lagoon", "bg-iris text-white"] as const;
const GLOWS = ["shadow-glow-sun", "shadow-soft", "shadow-glow-pink", "shadow-glow-lagoon", "shadow-glow-iris"] as const;

export function accentFor(index: number): string {
  return ACCENTS[index % ACCENTS.length] ?? "bg-sun";
}

export function glowFor(index: number): string {
  return GLOWS[index % GLOWS.length] ?? "shadow-soft";
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
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="flex items-start gap-4">
        <span className="section-number" aria-hidden="true">
          {number}
        </span>
        <div>
          <h2 className="text-3xl leading-tight sm:text-4xl">{title}</h2>
          {subtitle ? <p className="mt-1 text-base text-slate">{subtitle}</p> : null}
        </div>
      </div>
      {aside}
    </header>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="card flex items-center gap-3 p-6 font-semibold">
      <span className="relative flex h-9 w-9 items-center justify-center rounded-2xl bg-sun">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      </span>
      {label}…
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", message, action }: { title?: string; message: string; action?: ReactNode }) {
  return (
    <div role="alert" className="card animate-pop-in overflow-hidden border-bubblegum/30 bg-bubblegum-soft p-6">
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-bubblegum text-white shadow-glow-pink">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h3 className="text-xl">{title}</h3>
          <p className="mt-1 font-medium">{message}</p>
          {action ? <div className="mt-4">{action}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="card border-dashed p-10 text-center">
      <span className="mx-auto flex h-14 w-14 animate-float items-center justify-center rounded-3xl bg-sun shadow-glow-sun">
        <Inbox className="h-7 w-7" aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-2xl">{title}</h3>
      <p className="mt-1 text-slate">{message}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function DemoBanner() {
  return (
    <div role="note" className="bg-gradient-to-r from-iris via-bubblegum to-tangerine px-4 py-2 text-center text-sm font-semibold text-white">
      <Sparkles className="mr-1.5 inline h-4 w-4 align-[-3px]" aria-hidden="true" />
      Demo data: fictional vendors from built-in fixtures. No real websites were investigated.
    </div>
  );
}
