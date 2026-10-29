import { Check } from "lucide-react";
import type { CriterionMeta, Priority } from "../api/types";

const ORDER_WEIGHTS = [3, 2, 1];
const RANK_COLORS = ["bg-iris text-white", "bg-bubblegum text-white", "bg-tangerine text-ink"];
export const MAX_PRIORITIES = ORDER_WEIGHTS.length;

/** Selected criteria in order; the first pick weighs most (3, 2, 1). */
export function toPriorities(selected: string[]): Priority[] {
  return selected.map((criterion, i) => ({ criterion, weight: ORDER_WEIGHTS[i] ?? 1 }));
}

export function PrioritySelector({
  criteria,
  selected,
  onChange,
}: {
  criteria: CriterionMeta[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  function toggle(key: string) {
    if (selected.includes(key)) onChange(selected.filter((k) => k !== key));
    else if (selected.length < MAX_PRIORITIES) onChange([...selected, key]);
  }
  return (
    <fieldset>
      <legend className="sr-only">What matters most to you?</legend>
      <div className="flex flex-wrap gap-2.5">
        {criteria.map((c) => {
          const rank = selected.indexOf(c.key);
          const on = rank >= 0;
          return (
            <button
              key={c.key}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(c.key)}
              disabled={!on && selected.length >= MAX_PRIORITIES}
              className={`btn px-4 py-2 font-body text-sm font-semibold ${
                on ? "bg-ink text-white shadow-glow-iris" : "bg-white text-ink shadow-soft hover:shadow-lift"
              }`}
            >
              {on ? (
                <span
                  className={`flex h-5 w-5 animate-pop-in items-center justify-center rounded-full text-[11px] font-bold ${RANK_COLORS[rank] ?? ""}`}
                  aria-label={`priority ${rank + 1}`}
                >
                  {rank + 1}
                </span>
              ) : null}
              {c.label}
              {on ? <Check className="h-3.5 w-3.5 opacity-70" aria-hidden="true" /> : null}
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-sm text-slate">
        {selected.length === 0
          ? "No priorities picked: ClauseLens uses its documented default scoring (refund window weighs most)."
          : `Your first pick counts most. ${MAX_PRIORITIES - selected.length} more allowed.`}
      </p>
    </fieldset>
  );
}
