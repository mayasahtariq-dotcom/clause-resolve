import { AlertTriangle, BadgeCheck, CircleDashed, Quote } from "lucide-react";

/** Illustrative product mock for the hero (sample labels, not real vendors). */
export function HeroMock() {
  const rows = [
    { name: "Vendor A", value: "30 days", tone: "bg-lagoon-soft", badge: <BadgeCheck className="h-4 w-4 text-lagoon" aria-hidden="true" />, best: true },
    { name: "Vendor B", value: "14 vs 30 days", tone: "bg-bubblegum-soft", badge: <AlertTriangle className="h-4 w-4 text-bubblegum" aria-hidden="true" /> },
    { name: "Vendor C", value: "Not stated", tone: "bg-paper", badge: <CircleDashed className="h-4 w-4 text-slate" aria-hidden="true" /> },
  ];
  return (
    <div className="relative mx-auto flex h-[25rem] w-full max-w-[22rem] items-center justify-center" aria-hidden="true">
      {/* concentric rings */}
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="absolute rounded-full border border-iris/15"
          style={{ width: `${14 + i * 7}rem`, height: `${14 + i * 7}rem` }}
        />
      ))}

      {/* phone */}
      <div className="relative z-10 w-56 animate-float-slow rounded-[2.4rem] bg-ink p-2 shadow-lift">
        <div className="overflow-hidden rounded-[2rem] bg-white">
          <div className="flex items-center justify-between bg-sun px-4 pb-3 pt-5">
            <span className="font-display text-sm font-extrabold">Refund window</span>
            <span className="rounded-full bg-ink px-2 py-0.5 text-[10px] font-bold text-sun">LIVE</span>
          </div>
          <ul className="space-y-2 p-3">
            {rows.map((r, i) => (
              <li
                key={r.name}
                className={`flex animate-slide-up items-center justify-between rounded-2xl px-3 py-2.5 ${r.tone}`}
                style={{ animationDelay: `${300 + i * 150}ms` }}
              >
                <span>
                  <span className="block text-[11px] font-semibold text-slate">{r.name}</span>
                  <span className="block font-display text-sm font-extrabold">{r.value}</span>
                </span>
                {r.badge}
              </li>
            ))}
          </ul>
          <div className="mx-3 mb-4 rounded-2xl bg-iris px-3 py-2.5 text-white">
            <p className="text-[10px] font-semibold opacity-80">Recommendation</p>
            <p className="font-display text-xs font-extrabold">Vendor A fits your priorities</p>
          </div>
        </div>
      </div>

      {/* floating chips */}
      <span className="chip absolute -left-6 top-0 z-20 animate-float-alt">
        <BadgeCheck className="h-4 w-4 text-lagoon" /> Quote verified
      </span>
      <span className="chip absolute -right-4 top-[46%] z-20 animate-float [animation-delay:-2s]">
        <AlertTriangle className="h-4 w-4 text-bubblegum" /> Conflict flagged
      </span>
      <span className="chip absolute -left-6 bottom-0 z-20 animate-float [animation-delay:-1s]">
        <Quote className="h-4 w-4 text-iris" /> Linked to source
      </span>
      <span className="absolute right-0 top-6 z-20 flex h-12 w-12 animate-wiggle items-center justify-center rounded-2xl bg-sun font-display text-lg font-extrabold shadow-glow-sun">
        $0
      </span>
    </div>
  );
}
