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
      <p className={`${cell.is_best ? "font-extrabold" : "font-semibold"} ${quiet ? "text-slate" : ""}`}>
        {cell.is_best ? <Award className="mr-1 inline h-4 w-4 align-[-2px]" aria-label="Best for this term" /> : null}
        {cell.display}
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        {cell.status !== "found" ? <FieldStatusBadge status={cell.status} /> : null}
        {cell.evidence_ids.length ? (
          <button
            type="button"
            onClick={() => onEvidence({ vendorId: cell.vendor_id, vendorName, field: cell.field, evidenceIds: cell.evidence_ids })}
            className="inline-flex items-center gap-1 border-2 border-ink bg-white px-1.5 py-0.5 text-[11px] font-extrabold uppercase hover:bg-sun"
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
      {/* Desktop / tablet: side-by-side matrix in the style of the deck's comparison slide. */}
      <div className="panel hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Policy comparison by vendor</caption>
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 border-b-4 border-r-4 border-ink bg-sun px-4 py-3 font-display text-base font-extrabold uppercase">
                Feature
              </th>
              {report.vendors.map((v) => (
                <th
                  key={v.id}
                  scope="col"
                  className={`min-w-[12rem] border-b-4 border-r-4 border-ink px-4 py-3 font-display text-base font-extrabold uppercase last:border-r-0 ${v.id === recommended ? "bg-lagoon" : "bg-sun"}`}
                >
                  {v.name}
                  {v.id === recommended ? <span className="ml-1">(Recommended)</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          {FIELD_GROUPS.map((group) => (
            <tbody key={group.title}>
              <tr>
                <th colSpan={report.vendors.length + 1} scope="colgroup" className="border-b-4 border-ink bg-ink px-4 py-1.5 text-left text-xs font-extrabold uppercase tracking-widest text-sun">
                  {group.title}
                </th>
              </tr>
              {group.fields.map((f) => (
                <tr key={f} className="border-b-4 border-ink last:border-b-0">
                  <th scope="row" className="sticky left-0 border-r-4 border-ink bg-white px-4 py-3 align-top font-extrabold">
                    {label(f)}
                  </th>
                  {report.vendors.map((v) => (
                    <td key={v.id} className={`border-r-4 border-ink px-4 py-3 align-top last:border-r-0 ${v.id === recommended ? "bg-lagoon-soft" : "bg-white"}`}>
                      <CellContent cell={cellMap.get(`${v.id}:${f}`)} vendorName={v.name} label={label(f)} onEvidence={onEvidence} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>

      {/* Mobile: one card per policy term, vendors stacked. */}
      <div className="space-y-6 md:hidden">
        {FIELD_GROUPS.map((group) => (
          <section key={group.title} aria-label={group.title}>
            <h3 className="mb-2 inline-block bg-ink px-2 py-0.5 text-sm uppercase tracking-widest text-sun">{group.title}</h3>
            <div className="space-y-3">
              {group.fields.map((f) => (
                <article key={f} className="panel-sm overflow-hidden">
                  <h4 className="border-b-3 border-ink bg-sun px-3 py-2 text-base uppercase">{label(f)}</h4>
                  <dl className="divide-y-2 divide-ink/20">
                    {report.vendors.map((v) => (
                      <div key={v.id} className={`grid grid-cols-[7rem_1fr] gap-2 px-3 py-2 ${v.id === recommended ? "bg-lagoon-soft" : ""}`}>
                        <dt className="font-extrabold uppercase">{v.name}</dt>
                        <dd>
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
