import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listContainers } from "../api/endpoints";
import { PageHeader, Loader, EmptyState, ErrorState } from "../components/common";
import { fmtDate } from "../utils/format";

export default function Containers() {
  const [search, setSearch] = useState("");
  const [extraOnly, setExtraOnly] = useState(false);

  const params: Record<string, any> = {};
  if (search) params.search = search;
  if (extraOnly) params.extra_work_only = true;

  const q = useQuery({
    queryKey: ["containers", params],
    queryFn: () => listContainers(params),
  });

  return (
    <div>
      <PageHeader title="מכולות" subtitle="כל המכולות הפעילות במערכת" />

      <div className="card mb-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="label">חיפוש</label>
          <input className="input" placeholder="מספר מכולה / SHP / ספק"
            value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 mt-7">
          <input type="checkbox" checked={extraOnly} onChange={(e) => setExtraOnly(e.target.checked)} />
          <span className="text-sm">תוספת עבודה בלבד</span>
        </label>
      </div>

      {q.isLoading ? <Loader /> : q.isError ? <ErrorState error={q.error} /> :
        !q.data || q.data.length === 0 ? <EmptyState title="אין מכולות תואמות" /> :
        <div className="card overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs">
                <th className="text-right py-2 px-2">מכולה</th>
                <th className="text-right py-2 px-2">סוג</th>
                <th className="text-right py-2 px-2">SHP</th>
                <th className="text-right py-2 px-2">ספק</th>
                <th className="text-right py-2 px-2">CBM</th>
                <th className="text-right py-2 px-2">קופסאות</th>
                <th className="text-right py-2 px-2">משקל</th>
                <th className="text-right py-2 px-2">ETA לארץ</th>
                <th className="text-right py-2 px-2">ETA נמל</th>
                <th className="text-right py-2 px-2">ETA מחסן</th>
                <th className="text-right py-2 px-2">סטטוס</th>
                <th className="text-right py-2 px-2">עדיפות</th>
                <th className="text-right py-2 px-2">תוספת</th>
                <th className="text-right py-2 px-2">משטחים</th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-2 font-mono">
                    <Link className="text-brand-600" to={`/containers/${c.id}`}>
                      {c.container_number}
                    </Link>
                  </td>
                  <td className="py-2 px-2">{c.container_type || "—"}</td>
                  <td className="py-2 px-2">
                    {c.shipment_shp_id && (
                      <Link className="text-brand-600" to={`/shipments/${c.shipment_id}`}>
                        {c.shipment_shp_id}
                      </Link>
                    )}
                  </td>
                  <td className="py-2 px-2">{c.supplier || "—"}</td>
                  <td className="py-2 px-2">{c.cbm ?? "—"}</td>
                  <td className="py-2 px-2">{c.boxes_total ?? "—"}</td>
                  <td className="py-2 px-2">{c.gross_weight_kg ?? "—"}</td>
                  <td className="py-2 px-2">{fmtDate(c.effective_eta_israel)}</td>
                  <td className="py-2 px-2">{fmtDate(c.eta_port)}</td>
                  <td className="py-2 px-2">{fmtDate(c.effective_eta_warehouse)}</td>
                  <td className="py-2 px-2">{c.container_status || "—"}</td>
                  <td className="py-2 px-2">{c.unloading_priority || "רגיל"}</td>
                  <td className="py-2 px-2">
                    {c.extra_work_required ? <span className="badge-purple">כן</span> : "—"}
                  </td>
                  <td className="py-2 px-2">
                    {c.estimated_pallets_final != null ? (
                      <span className="font-semibold">
                        {c.estimated_pallets_final}
                        {c.recommended_pallet_type && (
                          <span className="text-xs text-slate-500 mr-1">
                            ({c.recommended_pallet_type === "euro" ? "E" : "I"})
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      }
    </div>
  );
}
