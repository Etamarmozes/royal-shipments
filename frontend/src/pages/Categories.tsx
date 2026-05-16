import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listContainers, listCategories } from "../api/endpoints";
import { PageHeader, Loader, EmptyState } from "../components/common";
import { fmtDate, fmtNumber } from "../utils/format";
import type { Container } from "../types";
import clsx from "clsx";

/**
 * Category Forecast — group containers by category, show totals + nearest ETA.
 * Click a category to drill into its containers.
 */
export default function Categories() {
  const [drill, setDrill] = useState<string | null>(null);
  const containers = useQuery({ queryKey: ["containers"], queryFn: () => listContainers() });
  const cats = useQuery({ queryKey: ["categories"], queryFn: listCategories });

  const inTransit = useMemo(
    () => (containers.data || []).filter((c) => !c.actual_arrival_warehouse),
    [containers.data]
  );

  const grouped = useMemo(() => {
    const map: Record<string, {
      category: string;
      containers: Container[];
      shipments: Set<number>;
      pallets: number;
      nearestEta: string | null;
      missingDataCount: number;
    }> = {};
    for (const c of inTransit) {
      const cat = c.effective_category || "אחר";
      const e = (map[cat] ??= {
        category: cat,
        containers: [],
        shipments: new Set(),
        pallets: 0,
        nearestEta: null,
        missingDataCount: 0,
      });
      e.containers.push(c);
      e.shipments.add(c.shipment_id);
      e.pallets += c.estimated_pallets_final || 0;
      const eta = c.effective_eta_israel;
      if (eta && (!e.nearestEta || eta < e.nearestEta)) e.nearestEta = eta;
      const missing = !c.effective_eta_israel || !c.carton_length_cm
        || !c.cbm || !c.boxes_total;
      if (missing) e.missingDataCount += 1;
    }
    return Object.values(map).sort((a, b) => {
      // Categories with nearest ETA first
      if (a.nearestEta && !b.nearestEta) return -1;
      if (!a.nearestEta && b.nearestEta) return 1;
      if (!a.nearestEta && !b.nearestEta) return 0;
      return (a.nearestEta || "") < (b.nearestEta || "") ? -1 : 1;
    });
  }, [inTransit]);

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="קטגוריות בדרך"
        subtitle="סיכום לפי קטגוריית מוצר. לחץ על קטגוריה לפירוט."
      />

      {containers.isLoading ? <Loader /> :
       grouped.length === 0 ? <EmptyState title="אין מכולות בדרך" icon="🏷️" /> : (
         <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
           {grouped.map((g) => (
             <button
               key={g.category}
               onClick={() => setDrill(drill === g.category ? null : g.category)}
               className={clsx(
                 "text-right rounded-2xl border p-5 hover:shadow-md transition",
                 drill === g.category ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-white",
               )}
             >
               <div className="flex items-center justify-between mb-3">
                 <span className="text-lg font-semibold text-slate-900">{g.category}</span>
                 <span className="text-2xl">📦</span>
               </div>
               <div className="grid grid-cols-3 gap-2 text-center">
                 <Stat label="מכולות" value={g.containers.length} />
                 <Stat label="משלוחים" value={g.shipments.size} />
                 <Stat label="משטחים" value={g.pallets} />
               </div>
               <div className="mt-3 flex items-center justify-between text-xs">
                 <span className="text-slate-500">
                   {g.nearestEta ? `הכי קרוב: ${fmtDate(g.nearestEta)}` : "ללא ETA"}
                 </span>
                 {g.missingDataCount > 0 && (
                   <span className="badge-amber">{g.missingDataCount} חסר מידע</span>
                 )}
               </div>
             </button>
           ))}
         </div>
       )}

      {drill && (
        <div className="bg-white rounded-2xl border border-slate-200 mt-6 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-semibold">מכולות ב-{drill}</h2>
            <button onClick={() => setDrill(null)} className="text-slate-400 hover:text-slate-700">✕</button>
          </div>
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="text-right py-3 px-3">ETA</th>
                <th className="text-right py-3 px-3">מכולה</th>
                <th className="text-right py-3 px-3">SHP</th>
                <th className="text-right py-3 px-3">ספק</th>
                <th className="text-right py-3 px-3">קרטונים</th>
                <th className="text-right py-3 px-3">CBM</th>
                <th className="text-right py-3 px-3">משטחים</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {grouped.find((g) => g.category === drill)?.containers
                .sort((a, b) => (a.effective_eta_israel || "9999") < (b.effective_eta_israel || "9999") ? -1 : 1)
                .map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="py-3 px-3">{fmtDate(c.effective_eta_israel)}</td>
                    <td className="py-3 px-3 font-mono">
                      <Link to={`/containers/${c.id}`} className="text-brand-600">{c.container_number}</Link>
                    </td>
                    <td className="py-3 px-3">
                      <Link to={`/shipments/${c.shipment_id}`} className="text-brand-600">{c.shipment_shp_id}</Link>
                    </td>
                    <td className="py-3 px-3">{c.supplier}</td>
                    <td className="py-3 px-3">{c.boxes_total ?? "—"}</td>
                    <td className="py-3 px-3">{c.cbm ?? "—"}</td>
                    <td className="py-3 px-3 font-semibold">{c.estimated_pallets_final ?? "—"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-semibold tabular-nums">{fmtNumber(value)}</div>
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
    </div>
  );
}
