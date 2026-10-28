import type { CriterionMeta, Priority } from "../api/types";

const ORDER_WEIGHTS = [3, 2, 1];
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
      <div className="flex flex-wrap gap-3">
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
              className={`btn px-3 py-2 text-sm normal-case ${on ? "bg-lagoon" : "bg-white"}`}
            >
              {on ? (
                <span className="flex h-5 w-5 items-center justify-center bg-ink text-xs text-sun" aria-label={`priority ${rank + 1}`}>
                  {rank + 1}
                </span>
              ) : null}
              {c.label}
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-sm font-semibold">
        {selected.length === 0
          ? "No priorities picked: ClauseLens uses its documented default scoring (refund window weighs most)."
          : `Your first pick counts most. ${MAX_PRIORITIES - selected.length} more allowed.`}
      </p>
    </fieldset>
  );
}
