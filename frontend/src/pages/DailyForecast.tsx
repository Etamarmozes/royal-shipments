import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { dashboardPalletForecastDaily, dashboardPalletKpis, listShipments } from "../api/endpoints";
import { PageHeader, Loader, EmptyState, ErrorState } from "../components/common";
import { fmtDate, fmtNumber } from "../utils/format";
import clsx from "clsx";

export default function DailyForecast() {
  const [days, setDays] = useState(14);
  const q = useQuery({
    queryKey: ["pallet-forecast-daily", days],
    queryFn: () => dashboardPalletForecastDaily(days),
  });
  const k = useQuery({ queryKey: ["pallet-kpis"], queryFn: dashboardPalletKpis });
  const ships = useQuery({
    queryKey: ["shipments-list-active"],
    queryFn: () => listShipments({ archived: false, limit: 500 }),
  });

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="תחזית משטחים יומית"
        subtitle="כמה משלוחים ומשטחים מגיעים בכל יום בשבועיים הקרובים"
        actions={
          <select
            className="input"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>7 ימים</option>
            <option value={14}>14 ימים</option>
            <option value={30}>30 ימים</option>
          </select>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Kpi label="היום" big={k.data?.pallets_today ?? 0} small={`${k.data?.containers_today ?? 0} מכולות`} tone="info" />
        <Kpi label="מחר" big={k.data?.pallets_tomorrow ?? 0} small={`${k.data?.containers_tomorrow ?? 0} מכולות`} />
        <Kpi label="7 ימים קדימה" big={k.data?.pallets_next_7_days ?? 0} small={`${k.data?.containers_next_7_days ?? 0} מכולות`} />
        <Kpi
          label="מכולות ללא מידות"
          big={k.data?.containers_missing_carton_dimensions ?? 0}
          small="חישוב לפי CBM בלבד"
          tone={k.data?.containers_missing_carton_dimensions ? "warning" : "default"}
        />
      </div>

      {q.isLoading ? <Loader /> :
       q.isError ? <ErrorState error={q.error} /> :
       !q.data ? <EmptyState title="אין נתונים" /> : (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <table className="min-w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr className="text-xs text-slate-500">
                <th className="text-right py-3 px-4 font-medium">תאריך</th>
                <th className="text-right py-3 px-4 font-medium">מכולות</th>
                <th className="text-right py-3 px-4 font-medium">משטחים</th>
                <th className="text-right py-3 px-4 font-medium">קרטונים</th>
                <th className="text-right py-3 px-4 font-medium">CBM</th>
                <th className="text-right py-3 px-4 font-medium">ספקים</th>
                <th className="text-right py-3 px-4 font-medium">משלוחים</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {q.data.map((d) => (
                <tr key={d.date} className={clsx(
                  d.is_today && "bg-blue-50",
                  d.containers_arriving === 0 && "text-slate-400",
                )}>
                  <td className="py-3 px-4">
                    <div className="font-medium text-slate-900">
                      {d.is_today ? "היום" : d.is_tomorrow ? "מחר" : d.weekday.slice(0, 3)}
                    </div>
                    <div className="text-xs text-slate-500">{fmtDate(d.date)}</div>
                  </td>
                  <td className="py-3 px-4 tabular-nums">{d.containers_arriving}</td>
                  <td className="py-3 px-4 tabular-nums font-semibold">
                    {d.estimated_pallets}
                    {d.missing_carton_dimensions > 0 && (
                      <span className="badge-amber mr-2 text-[10px]">
                        ⚠ {d.missing_carton_dimensions} ללא מידות
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 tabular-nums">{fmtNumber(d.total_cartons)}</td>
                  <td className="py-3 px-4 tabular-nums">{fmtNumber(d.total_cbm, 1)}</td>
                  <td className="py-3 px-4 text-sm">
                    {d.suppliers.slice(0, 2).join(", ")}
                    {d.suppliers.length > 2 ? "…" : ""}
                  </td>
                  <td className="py-3 px-4 text-sm">
                    <div className="flex flex-wrap gap-1">
                      {d.shipment_ids.slice(0, 5).map((sid) => {
                        const ship = ships.data?.items.find((s) => s.id === sid);
                        return (
                          <Link
                            key={sid}
                            to={`/shipments/${sid}`}
                            className="text-brand-600 hover:underline"
                          >
                            {ship?.shp_id || `#${sid}`}
                          </Link>
                        );
                      })}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
       )
      }
    </div>
  );
}

function Kpi({ label, big, small, tone = "default" }: { label: string; big: number; small?: string; tone?: "default" | "info" | "warning" }) {
  const ring = {
    default: "border-slate-200",
    info: "border-blue-200",
    warning: "border-amber-300",
  }[tone];
  const valColor = {
    default: "text-slate-900",
    info: "text-blue-700",
    warning: "text-amber-800",
  }[tone];
  return (
    <div className={clsx("bg-white rounded-2xl border p-4", ring)}>
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className={clsx("text-3xl font-semibold mt-1 tabular-nums", valColor)}>{fmtNumber(big)}</div>
      {small && <div className="text-xs text-slate-400 mt-1">{small}</div>}
    </div>
  );
}
