import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardForecast, listContainers } from "../api/endpoints";
import { PageHeader, Loader, ErrorState } from "../components/common";
import { fmtDate, fmtNumber, loadStatusColor } from "../utils/format";
import { Link } from "react-router-dom";

export default function Forecast() {
  const q = useQuery({ queryKey: ["forecast"], queryFn: dashboardForecast });
  const containers = useQuery({ queryKey: ["containers"], queryFn: () => listContainers() });
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div>
      <PageHeader title="תחזית הגעה — 8 שבועות" subtitle="כמה מכולות מגיעות, מתי, ובאיזה עומס" />

      {q.isLoading ? <Loader /> : q.isError ? <ErrorState error={q.error} /> : q.data && (
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs">
                <th className="text-right py-2 px-2">שבוע</th>
                <th className="text-right py-2 px-2">תאריכים</th>
                <th className="text-right py-2 px-2">לארץ</th>
                <th className="text-right py-2 px-2">לנמל</th>
                <th className="text-right py-2 px-2">למחסן</th>
                <th className="text-right py-2 px-2">CBM</th>
                <th className="text-right py-2 px-2">משקל</th>
                <th className="text-right py-2 px-2">קופסאות</th>
                <th className="text-right py-2 px-2">ספקים</th>
                <th className="text-right py-2 px-2">עומס</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((w) => (
                <Fragment key={w.week_index}>
                  <tr className="border-t border-slate-100">
                    <td className="py-2 px-2 font-medium">{w.week_label}</td>
                    <td className="py-2 px-2">{fmtDate(w.week_start)} – {fmtDate(w.week_end)}</td>
                    <td className="py-2 px-2">{fmtNumber(w.containers_arriving_israel)}</td>
                    <td className="py-2 px-2">{fmtNumber(w.containers_arriving_port)}</td>
                    <td className="py-2 px-2">{fmtNumber(w.containers_arriving_warehouse)}</td>
                    <td className="py-2 px-2">{fmtNumber(w.cbm_total, 1)}</td>
                    <td className="py-2 px-2">{fmtNumber(w.weight_total_kg)}</td>
                    <td className="py-2 px-2">{fmtNumber(w.boxes_total)}</td>
                    <td className="py-2 px-2 text-xs">{w.suppliers.join(", ") || "—"}</td>
                    <td className="py-2 px-2"><span className={loadStatusColor(w.load_status)}>{w.load_status}</span></td>
                    <td className="py-2 px-2 text-left">
                      {w.container_ids.length > 0 && (
                        <button
                          className="text-brand-600 text-xs"
                          onClick={() => setOpen(open === w.week_index ? null : w.week_index)}
                        >
                          {open === w.week_index ? "סגור" : "פרטים"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {open === w.week_index && (
                    <tr className="bg-slate-50">
                      <td colSpan={11} className="p-3">
                        <div className="text-xs text-slate-500 mb-2">מכולות בשבוע:</div>
                        <ul className="grid grid-cols-1 md:grid-cols-2 gap-1">
                          {containers.data?.filter((c) => w.container_ids.includes(c.id)).map((c) => (
                            <li key={c.id} className="flex items-center justify-between text-sm">
                              <span className="font-mono">{c.container_number}</span>
                              <span className="text-slate-500">
                                {c.shipment_shp_id} • {c.supplier} • {fmtDate(c.effective_eta_israel)}
                              </span>
                              <Link to={`/shipments/${c.shipment_id}`} className="text-brand-600 text-xs">
                                למשלוח →
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
