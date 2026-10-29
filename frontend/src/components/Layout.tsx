import { ArrowUpRight, FileSearch } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useMeta } from "../hooks/useMeta";
import { Backdrop } from "./Backdrop";
import { DemoBanner } from "./ui";

const NAV = [
  { href: "/#how", label: "How it works" },
  { href: "/#compare", label: "Compare" },
  { href: "/#recent", label: "Recent" },
];

function Logo() {
  return (
    <Link to="/" className="group flex items-center gap-2 font-display text-lg font-extrabold" aria-label="ClauseLens home">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-sun transition group-hover:rotate-[-8deg] group-hover:scale-105">
        <FileSearch className="h-5 w-5" aria-hidden="true" />
      </span>
      ClauseLens
    </Link>
  );
}

export function Layout() {
  const meta = useMeta();
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: "smooth" });
    else window.scrollTo({ top: 0 });
  }, [location.pathname, location.hash]);

  return (
    <div className="relative flex min-h-screen flex-col">
      <Backdrop />
      {meta.data?.demo_mode ? <DemoBanner /> : null}
      <header className="sticky top-0 z-40 px-3 pt-3 sm:px-4">
        <nav
          className={`mx-auto flex max-w-6xl items-center justify-between gap-3 rounded-full px-3 py-2 pl-4 transition-all duration-300 ${
            scrolled ? "glass" : "bg-transparent"
          }`}
          aria-label="Main"
        >
          <Logo />
          <ul className="hidden items-center gap-1 rounded-full bg-white/70 p-1 shadow-inset md:flex">
            {NAV.map((item) => (
              <li key={item.href}>
                <NavLink
                  to={item.href}
                  className="rounded-full px-4 py-1.5 text-sm font-semibold text-slate transition hover:bg-paper hover:text-ink"
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <Link to="/#compare" className="btn-primary px-4 py-2 text-sm">
            Start comparing <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </nav>
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-6 sm:pt-10">
        <Outlet />
      </main>

      <footer className="px-3 pb-3 sm:px-4">
        <div className="card mx-auto max-w-6xl overflow-hidden px-6 pb-4 pt-8 sm:px-10">
          <div className="grid gap-8 md:grid-cols-[1.4fr_1fr_1fr]">
            <div>
              <p className="eyebrow">Our promise</p>
              <p className="mt-3 max-w-md font-display text-2xl font-extrabold leading-tight">
                Investigate. Compare. <span className="text-gradient">Understand.</span> Decide.
              </p>
            </div>
            <div className="text-sm">
              <p className="mb-2 font-bold">Built for trust</p>
              <ul className="space-y-1 text-slate">
                <li>Every claim links to its source</li>
                <li>Unknowns stay unknown</li>
                <li>No personal data collected</li>
              </ul>
            </div>
            <div className="text-sm">
              <p className="mb-2 font-bold">Good to know</p>
              <p className="text-slate">
                ClauseLens summarises publicly available policy text. It is not legal advice. Always confirm terms on the
                vendor&apos;s own site.
              </p>
            </div>
          </div>
          <p
            aria-hidden="true"
            className="mt-8 select-none font-display text-[15vw] font-extrabold leading-[0.8] tracking-tighter text-ink sm:text-[9rem]"
          >
            ClauseLens<span className="text-bubblegum">.</span>
          </p>
        </div>
      </footer>
    </div>
  );
}
