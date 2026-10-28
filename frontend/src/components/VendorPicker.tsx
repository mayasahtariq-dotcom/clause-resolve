import { Globe, Plus, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import type { VendorInput } from "../api/types";
import { accentFor } from "./ui";
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
      <form onSubmit={add} className="grid gap-3 sm:grid-cols-[1.2fr_1fr_auto]" aria-describedby={error ? errorId : undefined}>
        <div>
          <label htmlFor={nameId} className="mb-1 block text-sm font-extrabold uppercase">
            Vendor name
          </label>
          <input
            id={nameId}
            className="field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Coursera"
            maxLength={120}
            autoComplete="off"
            aria-invalid={Boolean(error)}
          />
        </div>
        <div>
          <label htmlFor={domainId} className="mb-1 block text-sm font-extrabold uppercase">
            Official site <span className="font-semibold normal-case text-slate">(optional, recommended)</span>
          </label>
          <input
            id={domainId}
            className="field"
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
        <p id={errorId} role="alert" className="mt-3 inline-block border-3 border-ink bg-bubblegum px-3 py-1 font-bold">
          {error}
        </p>
      ) : null}

      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Selected vendors">
        {vendors.map((v, i) => (
          <li key={v.name} className={`panel-sm flex items-start justify-between gap-3 p-4 ${accentFor(i)}`}>
            <div className="min-w-0">
              <p className="font-display text-xs font-extrabold uppercase opacity-80">Vendor {String(i + 1).padStart(2, "0")}</p>
              <p className="truncate font-display text-xl font-extrabold uppercase">{v.name}</p>
              <p className="mt-1 flex items-center gap-1 truncate text-sm font-semibold">
                <Globe className="h-4 w-4 shrink-0" aria-hidden="true" />
                {v.domain ?? "Site found automatically"}
              </p>
            </div>
            <button
              type="button"
              className="border-3 border-ink bg-white p-1.5 shadow-brut-sm hover:bg-sun"
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
            className="flex min-h-[104px] items-center justify-center border-4 border-dashed border-ink/40 p-4 font-display font-extrabold uppercase text-ink/40"
          >
            Vendor {String(vendors.length + i + 1).padStart(2, "0")}
          </li>
        ))}
      </ul>
    </div>
  );
}
