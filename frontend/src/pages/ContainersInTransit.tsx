import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listContainers, listCategories, requiredDocumentsStatus } from "../api/endpoints";
import { PageHeader, Loader, EmptyState, ErrorState } from "../components/common";
import { fmtDate } from "../utils/format";
import type { Container } from "../types";
import clsx from "clsx";

/**
 * Operational view of all containers still en route — sorted by ETA.
 * Includes filters for missing data, category, supplier, delays.
 */
export default function ContainersInTransit() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("");
  const [missingFilter, setMissingFilter] = useState<string>("");

  const cats = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const containers = useQuery({
    queryKey: ["containers", "all"],
    queryFn: () => listContainers(),
  });

  // Filter to "in transit" — containers without actual_arrival_warehouse
  // and not in archived shipments
  const inTransit = (containers.data || []).filter((c) => !c.actual_arrival_warehouse);

  // Apply filters
  let filtered = inTransit;
  if (search) {
    const s = search.toLowerCase();
    filtered = filtered.filter((c) =>
      (c.container_number || "").toLowerCase().includes(s) ||
      (c.shipment_shp_id || "").toLowerCase().includes(s) ||
      (c.supplier || "").toLowerCase().includes(s) ||
      (c.goods_description || "").toLowerCase().includes(s)
    );
  }
  if (category) filtered = filtered.filter((c) => (c.effective_category || "אחר") === category);

  if (missingFilter === "eta") filtered = filtered.filter((c) => !c.effective_eta_israel);
  if (missingFilter === "dims") filtered = filtered.filter((c) =>
    !c.carton_length_cm || !c.carton_width_cm || !c.carton_height_cm);
  if (missingFilter === "cbm") filtered = filtered.filter((c) => !c.cbm);
  if (missingFilter === "cartons") filtered = filtered.filter((c) => !c.boxes_total);
  if (missingFilter === "category") filtered = filtered.filter((c) => !c.effective_category);
  if (missingFilter === "delay") filtered = filtered.filter((c) =>
    c.shipment_shp_id  // we'll proxy delay through… simpler: skip delays here for MVP
  );

  // Sort by effective ETA (Israel) ascending; nulls last
  filtered = [...filtered].sort((a, b) => {
    const x = a.effective_eta_israel || "9999";
    const y = b.effective_eta_israel || "9999";
    return x < y ? -1 : x > y ? 1 : 0;
  });

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="מכולות בדרך"
        subtitle="המסך התפעולי המרכזי. מיון ברירת מחדל: ETA הקרוב ביותר."
      />

      {/* Filters */}
      <div className="card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className="label">חיפוש</label>
          <input
            className="input" placeholder="מכולה / SHP / ספק"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div>
          <label className="label">קטגוריה</label>
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">הכל</option>
            {(cats.data?.categories || []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">חסר נתון</label>
          <select className="input" value={missingFilter} onChange={(e) => setMissingFilter(e.target.value)}>
            <option value="">הכל</option>
            <option value="eta">חסר ETA</option>
            <option value="dims">חסרות מידות קרטון</option>
            <option value="cbm">חסר CBM</option>
            <option value="cartons">חסר כמות קרטונים</option>
            <option value="category">חסרה קטגוריה</option>
          </select>
        </div>
        <div className="flex items-end">
          <div className="text-sm text-slate-500">
            מציג {filtered.length} / {inTransit.length} מכולות
          </div>
        </div>
      </div>

      {containers.isLoading ? <Loader /> :
       containers.isError ? <ErrorState error={containers.error} /> :
       filtered.length === 0 ? <EmptyState title="אין מכולות בדרך" icon="🚢" /> :
       <>
         {/* Mobile: card list */}
         <div className="lg:hidden space-y-2">
           {filtered.map((c) => (
             <MobileCard key={c.id} c={c} />
           ))}
         </div>
         {/* Desktop / tablet: full table */}
         <div className="hidden lg:block bg-white rounded-2xl border border-slate-200 overflow-hidden">
           <table className="min-w-full text-sm">
             <thead className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500">
               <tr>
                 <th className="text-right py-3 px-3 font-medium">ETA</th>
                 <th className="text-right py-3 px-3 font-medium">מכולה</th>
                 <th className="text-right py-3 px-3 font-medium">SHP</th>
                 <th className="text-right py-3 px-3 font-medium">ספק</th>
                 <th className="text-right py-3 px-3 font-medium">קטגוריה</th>
                 <th className="text-right py-3 px-3 font-medium">קרטונים</th>
                 <th className="text-right py-3 px-3 font-medium">CBM</th>
                 <th className="text-right py-3 px-3 font-medium">משטחים</th>
                 <th className="text-right py-3 px-3 font-medium">מסמכים</th>
                 <th className="text-right py-3 px-3 font-medium">חסר</th>
               </tr>
             </thead>
             <tbody className="divide-y divide-slate-100">
               {filtered.map((c) => (
                 <Row key={c.id} c={c} />
               ))}
             </tbody>
           </table>
         </div>
       </>}
    </div>
  );
}

function MobileCard({ c }: { c: Container }) {
  const docs = useQuery({
    queryKey: ["doc-status", c.shipment_id],
    queryFn: () => requiredDocumentsStatus(c.shipment_id),
    staleTime: 60_000,
    enabled: !!c.shipment_id,
  });
  const missing: string[] = [];
  if (!c.effective_eta_israel) missing.push("ETA");
  if (!c.carton_length_cm) missing.push("מידות");
  if (!c.cbm) missing.push("CBM");
  if (!c.boxes_total) missing.push("קרטונים");
  if (!c.effective_category) missing.push("קטגוריה");
  const present = new Set(docs.data?.present || []);
  const docBadges = [
    { key: "packing_list", label: "PL" },
    { key: "invoice", label: "INV" },
    { key: "bl", label: "BL" },
    { key: "booking_confirmation", label: "BK" },
  ];
  return (
    <Link
      to={`/containers/${c.id}`}
      className="block bg-white rounded-xl border border-slate-200 p-3 active:bg-slate-50"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="font-mono font-semibold text-brand-700 truncate">
            {c.container_number || "—"}
          </div>
          <div className="text-xs text-slate-500 truncate">
            {c.shipment_shp_id} • {c.supplier || "—"}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[10px] text-slate-500">ETA</div>
          <div className="text-sm font-medium tabular-nums">
            {fmtDate(c.effective_eta_israel)}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs mb-2">
        <Stat label="קרטונים" value={c.boxes_total ?? "—"} />
        <Stat label="CBM" value={c.cbm ?? "—"} />
        <Stat label="משטחים" value={c.estimated_pallets_final ?? "—"} bold />
      </div>
      <div className="flex flex-wrap items-center gap-1">
        {c.effective_category && <span className="badge-blue">{c.effective_category}</span>}
        {docBadges.map((b) => {
          const ok = present.has(b.key) ||
            (b.key === "bl" && (present.has("bol") || present.has("booking_confirmation")));
          return (
            <span
              key={b.key}
              className={clsx(
                "text-[10px] px-1.5 py-0.5 rounded font-medium",
                ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
              )}
            >{b.label}</span>
          );
        })}
        {missing.length === 0 ? (
          <span className="badge-green text-[10px]">תקין</span>
        ) : (
          missing.slice(0, 3).map((m, i) => (
            <span key={i} className="badge-amber text-[10px]">{m}</span>
          ))
        )}
      </div>
    </Link>
  );
}

function Stat({ label, value, bold }: { label: string; value: any; bold?: boolean }) {
  return (
    <div className="bg-slate-50 rounded-lg p-2 text-center">
      <div className="text-[9px] text-slate-500">{label}</div>
      <div className={clsx("tabular-nums", bold ? "font-semibold text-slate-900" : "text-slate-700")}>
        {value}
      </div>
    </div>
  );
}

function Row({ c }: { c: Container }) {
  const docs = useQuery({
    queryKey: ["doc-status", c.shipment_id],
    queryFn: () => requiredDocumentsStatus(c.shipment_id),
    staleTime: 60_000,
    enabled: !!c.shipment_id,
  });
  const missing: string[] = [];
  if (!c.effective_eta_israel) missing.push("ETA");
  if (!c.carton_length_cm) missing.push("מידות");
  if (!c.cbm) missing.push("CBM");
  if (!c.boxes_total) missing.push("קרטונים");
  if (!c.effective_category) missing.push("קטגוריה");

  // Document presence badges
  const present = new Set(docs.data?.present || []);
  const docBadges = [
    { key: "packing_list", label: "PL" },
    { key: "invoice", label: "INV" },
    { key: "bl", label: "BL" },
    { key: "booking_confirmation", label: "BK" },
  ];

  return (
    <tr className="hover:bg-slate-50">
      <td className="py-3 px-3">
        <div className="font-medium text-slate-900">{fmtDate(c.effective_eta_israel)}</div>
      </td>
      <td className="py-3 px-3 font-mono">
        <Link to={`/containers/${c.id}`} className="text-brand-600 hover:underline">
          {c.container_number || "—"}
        </Link>
      </td>
      <td className="py-3 px-3">
        {c.shipment_shp_id && (
          <Link to={`/shipments/${c.shipment_id}`} className="text-brand-600 hover:underline">
            {c.shipment_shp_id}
          </Link>
        )}
      </td>
      <td className="py-3 px-3">{c.supplier || "—"}</td>
      <td className="py-3 px-3">
        {c.effective_category ? (
          <span className="badge-blue">{c.effective_category}</span>
        ) : (
          <span className="text-slate-400 text-xs">—</span>
        )}
      </td>
      <td className="py-3 px-3">{c.boxes_total ?? "—"}</td>
      <td className="py-3 px-3">{c.cbm ?? "—"}</td>
      <td className="py-3 px-3 font-semibold">{c.estimated_pallets_final ?? "—"}</td>
      <td className="py-3 px-3">
        <div className="flex gap-1">
          {docBadges.map((b) => {
            const ok = present.has(b.key) || (b.key === "bl" && (present.has("bol") || present.has("booking_confirmation")));
            return (
              <span
                key={b.key}
                className={clsx(
                  "text-[10px] px-1.5 py-0.5 rounded font-medium",
                  ok ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                )}
                title={ok ? `${b.label} קיים` : `${b.label} חסר`}
              >
                {b.label}
              </span>
            );
          })}
        </div>
      </td>
      <td className="py-3 px-3">
        <div className="flex flex-wrap gap-1">
          {missing.length === 0 ? (
            <span className="badge-green text-[10px]">תקין</span>
          ) : (
            missing.slice(0, 3).map((m, i) => (
              <span key={i} className="badge-amber text-[10px]">{m}</span>
            ))
          )}
        </div>
      </td>
    </tr>
  );
}
