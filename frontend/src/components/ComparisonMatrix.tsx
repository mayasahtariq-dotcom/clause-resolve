import { Award, Quote } from "lucide-react";
import type { ComparisonCell, ComparisonReport } from "../api/types";
import { FieldStatusBadge } from "./StatusBadge";
import { FIELD_GROUPS } from "./fieldGroups";

export interface EvidenceTarget {
  vendorId: string;
  vendorName: string;
  field: string;
  evidenceIds: string[];
}

interface Props {
  report: ComparisonReport;
  labels: Record<string, string>;
  onEvidence: (target: EvidenceTarget) => void;
}

const GROUP_TONES = ["bg-sun", "bg-bubblegum", "bg-lagoon", "bg-tangerine", "bg-iris"];

function CellContent({
  cell,
  vendorName,
  label,
  onEvidence,
}: {
  cell: ComparisonCell | undefined;
  vendorName: string;
  label: string;
  onEvidence: Props["onEvidence"];
}) {
  if (!cell) return <span className="text-slate">-</span>;
  const quiet = cell.status === "not_found" || cell.status === "unknown";
  return (
    <div className="space-y-1.5">
      <p className={`${cell.is_best ? "font-bold" : "font-medium"} ${quiet ? "text-slate" : ""}`}>
        {cell.is_best ? (
          <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-sun align-[-3px] shadow-glow-sun">
            <Award className="h-3 w-3" aria-label="Best for this term" />
          </span>
        ) : null}
        {cell.display}
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        {cell.status !== "found" ? <FieldStatusBadge status={cell.status} /> : null}
        {cell.evidence_ids.length ? (
          <button
            type="button"
            onClick={() => onEvidence({ vendorId: cell.vendor_id, vendorName, field: cell.field, evidenceIds: cell.evidence_ids })}
            className="inline-flex items-center gap-1 rounded-full bg-iris-soft px-2 py-0.5 text-[11px] font-bold text-iris-deep transition hover:-translate-y-0.5 hover:bg-iris hover:text-white"
            aria-label={`Show evidence for ${vendorName} ${label}`}
          >
            <Quote className="h-3 w-3" aria-hidden="true" />
            Evidence ({cell.evidence_ids.length})
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function ComparisonMatrix({ report, labels, onEvidence }: Props) {
  const cellMap = new Map(report.cells.map((c) => [`${c.vendor_id}:${c.field}`, c]));
  const recommended = report.recommendation.vendor_id;
  const label = (f: string) => labels[f] ?? f;

  return (
    <>
      <div className="card hidden overflow-hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-left text-sm">
            <caption className="sr-only">Policy comparison by vendor</caption>
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 bg-white px-5 py-4 text-xs font-bold uppercase tracking-wider text-slate">
                  Feature
                </th>
                {report.vendors.map((v, i) => (
                  <th key={v.id} scope="col" className="min-w-[12rem] px-3 py-3">
                    <span
                      className={`flex items-center gap-2 rounded-2xl px-3 py-2.5 font-display text-base font-extrabold ${
                        v.id === recommended ? "bg-lagoon shadow-glow-lagoon" : "bg-paper"
                      }`}
                    >
                      <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${["bg-sun", "bg-bubblegum", "bg-tangerine", "bg-iris text-white", "bg-lagoon"][i % 5]}`}>
                        {v.name.charAt(0)}
                      </span>
                      {v.name}
                      {v.id === recommended ? <span className="ml-auto rounded-full bg-white px-2 py-0.5 text-[10px]">(Recommended)</span> : null}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            {FIELD_GROUPS.map((group, gi) => (
              <tbody key={group.title}>
                <tr>
                  <th colSpan={report.vendors.length + 1} scope="colgroup" className="px-5 pb-2 pt-5 text-left">
                    <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate">
                      <span className={`h-2.5 w-2.5 rounded-full ${GROUP_TONES[gi % GROUP_TONES.length]}`} />
                      {group.title}
                    </span>
                  </th>
                </tr>
                {group.fields.map((f) => (
                  <tr key={f} className="group transition-colors hover:bg-paper/80">
                    <th scope="row" className="sticky left-0 z-10 border-t border-ink/5 bg-white px-5 py-3.5 align-top font-semibold group-hover:bg-paper">
                      {label(f)}
                    </th>
                    {report.vendors.map((v) => {
                      const cell = cellMap.get(`${v.id}:${f}`);
                      return (
                        <td
                          key={v.id}
                          className={`border-t border-ink/5 px-5 py-3.5 align-top ${v.id === recommended ? "bg-lagoon-soft/60" : ""} ${cell?.is_best ? "shadow-[inset_3px_0_0_#F5C800]" : ""}`}
                        >
                          <CellContent cell={cell} vendorName={v.name} label={label(f)} onEvidence={onEvidence} />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      </div>

      <div className="space-y-6 md:hidden">
        {FIELD_GROUPS.map((group, gi) => (
          <section key={group.title} aria-label={group.title}>
            <h3 className="mb-2 inline-flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate">
              <span className={`h-2.5 w-2.5 rounded-full ${GROUP_TONES[gi % GROUP_TONES.length]}`} />
              {group.title}
            </h3>
            <div className="space-y-3">
              {group.fields.map((f) => (
                <article key={f} className="card overflow-hidden">
                  <h4 className="bg-paper px-4 py-2.5 text-base">{label(f)}</h4>
                  <dl className="divide-y divide-ink/5">
                    {report.vendors.map((v) => (
                      <div key={v.id} className={`grid grid-cols-[6.5rem_1fr] gap-2 px-4 py-2.5 ${v.id === recommended ? "bg-lagoon-soft/60" : ""}`}>
                        <dt className="text-sm font-bold">{v.name}</dt>
                        <dd className="text-sm">
                          <CellContent cell={cellMap.get(`${v.id}:${f}`)} vendorName={v.name} label={label(f)} onEvidence={onEvidence} />
                        </dd>
                      </div>
                    ))}
                  </dl>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
