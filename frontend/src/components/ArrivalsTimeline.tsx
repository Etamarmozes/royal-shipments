import { useMemo } from "react";
import { Link } from "react-router-dom";
import { fmtDate } from "../utils/format";
import type { Container, Shipment } from "../types";
import clsx from "clsx";

/**
 * Visual logistics timeline — NOT a financial chart.
 *
 * Each shipment shows as a horizontal track:
 *  ETD ────── ETA Israel ────── ETA Warehouse
 * with a small ship icon and station dots placed at their date positions.
 *
 * Containers are grouped by shipment. Shipments are sorted by the closest
 * meaningful arrival date (warehouse > israel > port > etd).
 */
export default function ArrivalsTimeline({
  shipments, containers, daysAhead = 30,
}: {
  shipments: Shipment[];
  containers: Container[];
  daysAhead?: number;
}) {
  // Build the date axis from today to today+daysAhead
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const startMs = today.getTime();
  const endMs = startMs + daysAhead * 86400000;
  const totalMs = endMs - startMs;

  function pct(dateStr?: string | null): number | null {
    if (!dateStr) return null;
    const d = new Date(dateStr).getTime();
    if (isNaN(d)) return null;
    if (d < startMs) return 0;
    if (d > endMs) return 100;
    return ((d - startMs) / totalMs) * 100;
  }

  // Group containers by shipment for compact rendering
  const tracks = useMemo(() => {
    const byShip = new Map<number, { shipment: Shipment; containers: Container[] }>();
    for (const c of containers) {
      const s = shipments.find((x) => x.id === c.shipment_id);
      if (!s || s.archived) continue;
      // Only show if any of (etd / eta_israel / eta_warehouse) falls within window
      const dates = [c.eta_warehouse, s.eta_warehouse, c.eta_israel, s.eta_israel, c.eta_port, s.eta_port, s.etd]
        .filter(Boolean) as string[];
      const inWindow = dates.some((d) => {
        const t = new Date(d).getTime();
        return t >= startMs && t <= endMs;
      });
      if (!inWindow) continue;
      const e = byShip.get(s.id);
      if (e) e.containers.push(c);
      else byShip.set(s.id, { shipment: s, containers: [c] });
    }
    // Compute "anchor" date for each track: warehouse ETA → Israel → port → ETD
    return Array.from(byShip.values())
      .map((t) => {
        const c0 = t.containers[0];
        const anchor =
          (c0.eta_warehouse || t.shipment.eta_warehouse) ||
          (c0.eta_israel || t.shipment.eta_israel) ||
          (c0.eta_port || t.shipment.eta_port) ||
          t.shipment.etd ||
          null;
        return { ...t, anchor };
      })
      .sort((a, b) => {
        if (!a.anchor) return 1;
        if (!b.anchor) return -1;
        return a.anchor < b.anchor ? -1 : 1;
      });
  }, [shipments, containers, startMs, endMs]);

  // Build axis ticks (every ~5 days)
  const ticks: { label: string; pct: number }[] = [];
  const tickStep = Math.max(1, Math.round(daysAhead / 6));
  for (let d = 0; d <= daysAhead; d += tickStep) {
    const date = new Date(startMs + d * 86400000);
    ticks.push({
      label: date.toLocaleDateString("he-IL", { month: "short", day: "numeric" }),
      pct: (d / daysAhead) * 100,
    });
  }

  if (tracks.length === 0) {
    return (
      <div className="text-sm text-slate-500 py-6 text-center">
        אין משלוחים צפויים ב-{daysAhead} הימים הקרובים
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Axis */}
      <div className="relative h-6 ml-32">
        <div className="absolute inset-x-0 top-3 h-px bg-slate-200" />
        {ticks.map((t, i) => (
          <div
            key={i}
            className="absolute top-0 -translate-x-1/2 text-[10px] text-slate-400"
            style={{ right: `${t.pct}%` }}
          >
            <span className="block">{t.label}</span>
            <span className="block w-px h-2 bg-slate-300 mx-auto mt-0.5" />
          </div>
        ))}
      </div>

      {tracks.map((t) => {
        const s = t.shipment;
        const c0 = t.containers[0];
        const ETD = s.etd;
        const ETAi = c0.eta_israel || s.eta_israel;
        const ETAp = c0.eta_port || s.eta_port;
        const ETAw = c0.eta_warehouse || s.eta_warehouse;
        const stations = [
          { key: "ETD", date: ETD, label: "יציאה", pct: pct(ETD), tone: "slate" as const },
          { key: "ETAp", date: ETAp, label: "נמל", pct: pct(ETAp), tone: "blue" as const },
          { key: "ETAi", date: ETAi, label: "ארץ", pct: pct(ETAi), tone: "indigo" as const },
          { key: "ETAw", date: ETAw, label: "מחסן", pct: pct(ETAw), tone: "emerald" as const },
        ].filter((x) => x.pct !== null);

        const shipPct = stations[stations.length - 1]?.pct ?? null;

        return (
          <div key={s.id} className="group">
            <div className="flex items-center gap-3">
              {/* Label column */}
              <Link
                to={`/shipments/${s.id}`}
                className="w-32 shrink-0 text-right pr-1"
              >
                <div className="text-sm font-semibold text-slate-900 truncate group-hover:text-brand-600">
                  {s.shp_id}
                </div>
                <div className="text-[10px] text-slate-500 truncate">
                  {s.supplier}
                </div>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {s.category && <span className="badge-blue text-[9px] px-1.5 py-0">{s.category}</span>}
                  {t.containers.length > 1 && (
                    <span className="badge-gray text-[9px] px-1.5 py-0">{t.containers.length} מכולות</span>
                  )}
                </div>
              </Link>

              {/* Track */}
              <div className="relative flex-1 h-8">
                <div className="absolute inset-y-3 inset-x-0 rounded-full bg-slate-100" />
                {/* Path line — from earliest to latest known station */}
                {stations.length >= 2 && (
                  <div
                    className="absolute inset-y-3 rounded-full bg-gradient-to-l from-emerald-200 via-indigo-200 to-blue-200"
                    style={{
                      right: `${Math.min(...stations.map((x) => x.pct!))}%`,
                      left: `${100 - Math.max(...stations.map((x) => x.pct!))}%`,
                    }}
                  />
                )}
                {/* Stations */}
                {stations.map((st) => (
                  <div
                    key={st.key}
                    className="absolute -translate-x-1/2 group/station"
                    style={{ right: `${st.pct}%`, top: 0, height: "100%" }}
                    title={`${st.label}: ${fmtDate(st.date)}`}
                  >
                    <div className={clsx(
                      "w-2.5 h-2.5 rounded-full mx-auto mt-2.5 ring-2 ring-white",
                      st.tone === "slate" && "bg-slate-400",
                      st.tone === "blue" && "bg-blue-500",
                      st.tone === "indigo" && "bg-indigo-500",
                      st.tone === "emerald" && "bg-emerald-500",
                    )} />
                    <div className="text-[9px] text-slate-500 absolute -bottom-3 right-1/2 translate-x-1/2 whitespace-nowrap">
                      {st.label}
                    </div>
                  </div>
                ))}
                {/* Ship icon at the latest known station */}
                {shipPct != null && (
                  <div
                    className="absolute -translate-x-1/2 -translate-y-1/2 top-1/2 text-base leading-none drop-shadow"
                    style={{ right: `${shipPct}%` }}
                    aria-label="ship"
                  >
                    🚢
                  </div>
                )}
                {/* Delay overlay */}
                {s.delay_status && (
                  <span className="absolute top-0 right-0 badge-red text-[9px] px-1.5 py-0">עיכוב</span>
                )}
              </div>

              {/* Right summary */}
              <div className="w-20 shrink-0 text-left">
                <div className="text-xs text-slate-600">
                  {ETAw ? fmtDate(ETAw) : ETAi ? fmtDate(ETAi) : "—"}
                </div>
                <div className="text-[10px] text-slate-500">
                  {t.containers.reduce((acc, c) => acc + (c.estimated_pallets_final || 0), 0)} משטחים
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
