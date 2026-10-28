import { FileSearch } from "lucide-react";
import { Link, Outlet } from "react-router-dom";
import { useMeta } from "../hooks/useMeta";
import { DemoBanner } from "./ui";

export function Layout() {
  const meta = useMeta();
  return (
    <div className="flex min-h-screen flex-col">
      {meta.data?.demo_mode ? <DemoBanner /> : null}
      <header className="border-b-4 border-ink bg-paper">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4">
          <Link to="/" className="label-tag bg-bubblegum text-base normal-case" aria-label="ClauseLens home">
            <FileSearch className="h-5 w-5" aria-hidden="true" />
            ClauseLens
          </Link>
          <span className="label-tag hidden bg-iris text-white sm:inline-flex">Policy investigation agent</span>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:py-10">
        <Outlet />
      </main>
      <footer className="border-t-4 border-ink bg-sun">
        <div className="mx-auto max-w-6xl px-4 py-5 text-sm font-semibold">
          <p className="font-display text-lg font-extrabold uppercase" style={{ fontStretch: "87.5%" }}>
            Investigate. Compare. Understand. Decide.
          </p>
          <p className="mt-1">
            ClauseLens summarises publicly available policy text and links every claim to its source. It is not legal
            advice. Always confirm terms on the vendor&apos;s own site.
          </p>
        </div>
      </footer>
    </div>
  );
}
