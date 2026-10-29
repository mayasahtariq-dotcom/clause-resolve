import { Globe, Plus, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import type { VendorInput } from "../api/types";
import { accentFor, glowFor } from "./ui";
import { validateVendor } from "./vendorValidation";

interface Props {
  vendors: VendorInput[];
  max: number;
  onChange: (vendors: VendorInput[]) => void;
}

export function VendorPicker({ vendors, max, onChange }: Props) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();
  const domainId = useId();
  const errorId = useId();

  function add(event: FormEvent) {
    event.preventDefault();
    const candidate: VendorInput = { name: name.trim(), ...(domain.trim() ? { domain: domain.trim() } : {}) };
    const problem = validateVendor(candidate, vendors, max);
    setError(problem);
    if (problem) return;
    onChange([...vendors, candidate]);
    setName("");
    setDomain("");
  }

  return (
    <div>
      <form
        onSubmit={add}
        className="grid gap-3 rounded-3xl bg-paper/80 p-3 shadow-inset sm:grid-cols-[1.2fr_1fr_auto]"
        aria-describedby={error ? errorId : undefined}
      >
        <div>
          <label htmlFor={nameId} className="mb-1.5 ml-1 block text-sm font-bold">
            Vendor name
          </label>
          <input
            id={nameId}
            className="field bg-white"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Coursera"
            maxLength={120}
            autoComplete="off"
            aria-invalid={Boolean(error)}
          />
        </div>
        <div>
          <label htmlFor={domainId} className="mb-1.5 ml-1 block text-sm font-bold">
            Official site <span className="font-medium text-slate">(optional, recommended)</span>
          </label>
          <input
            id={domainId}
            className="field bg-white"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="coursera.org"
            maxLength={253}
            autoComplete="off"
            inputMode="url"
          />
        </div>
        <div className="flex items-end">
          <button type="submit" className="btn-yellow w-full sm:w-auto" disabled={vendors.length >= max}>
            <Plus className="h-5 w-5" aria-hidden="true" /> Add
          </button>
        </div>
      </form>
      {error ? (
        <p id={errorId} role="alert" className="mt-3 inline-flex animate-pop-in rounded-full bg-bubblegum px-4 py-1.5 text-sm font-bold text-white shadow-glow-pink">
          {error}
        </p>
      ) : null}

      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Selected vendors">
        {vendors.map((v, i) => (
          <li
            key={v.name}
            className={`group relative flex animate-pop-in items-start justify-between gap-3 overflow-hidden rounded-3xl p-5 transition duration-300 hover:-translate-y-1 ${accentFor(i)} ${glowFor(i)}`}
          >
            <span aria-hidden="true" className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-white/25 transition duration-500 group-hover:scale-150" />
            <div className="relative flex min-w-0 items-center gap-3">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/90 font-display text-xl font-extrabold text-ink shadow-soft">
                {v.name.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0">
                <p className="text-xs font-bold opacity-75">Vendor {String(i + 1).padStart(2, "0")}</p>
                <p className="truncate font-display text-xl font-extrabold">{v.name}</p>
                <p className="mt-0.5 flex items-center gap-1 truncate text-sm font-medium opacity-85">
                  <Globe className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {v.domain ?? "Site found automatically"}
                </p>
              </div>
            </div>
            <button
              type="button"
              className="relative rounded-full bg-white/90 p-1.5 text-ink shadow-soft transition hover:rotate-90 hover:bg-white"
              onClick={() => onChange(vendors.filter((_, j) => j !== i))}
              aria-label={`Remove ${v.name}`}
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </li>
        ))}
        {Array.from({ length: Math.max(0, 3 - vendors.length) }).map((_, i) => (
          <li
            key={`empty-${i}`}
            aria-hidden="true"
            className="flex min-h-[104px] items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-ink/15 bg-white/40 p-4 font-display font-bold text-slate/70"
          >
            <Plus className="h-4 w-4" /> Vendor {String(vendors.length + i + 1).padStart(2, "0")}
          </li>
        ))}
      </ul>
    </div>
  );
}
