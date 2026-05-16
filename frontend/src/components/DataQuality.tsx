import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  shipmentDataQuality, containerDataQuality, type DataQuality,
} from "../api/endpoints";

/**
 * Compact badge — green / amber / red based on score.
 * Drop next to the page title or in a list cell.
 */
export function DataQualityBadge({
  type, id, compact,
}: { type: "shipment" | "container"; id: number; compact?: boolean }) {
  const q = useQuery({
    queryKey: [type === "shipment" ? "shipment-quality" : "container-quality", id],
    queryFn: () => (type === "shipment" ? shipmentDataQuality(id) : containerDataQuality(id)),
  });
  if (q.isLoading || !q.data) return null;
  const d = q.data;
  const cls = {
    complete: "bg-emerald-50 text-emerald-700 border-emerald-200",
    missing_minor: "bg-amber-50 text-amber-800 border-amber-200",
    missing_critical: "bg-red-50 text-red-700 border-red-200",
  }[d.score];
  const icon = { complete: "✓", missing_minor: "⚠", missing_critical: "✕" }[d.score];
  const label = {
    complete: "מידע מלא",
    missing_minor: `חסר ${d.missing_minor.length} פריטים`,
    missing_critical: `חסר מידע קריטי (${d.missing_critical.length})`,
  }[d.score];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium border",
        cls,
      )}
      title={[
        ...d.missing_critical.map((m) => `קריטי: ${m.label}`),
        ...d.missing_minor.map((m) => `חסר: ${m.label}`),
      ].join("\n") || "כל המידע קיים"}
    >
      <span>{icon}</span>
      <span>{compact ? icon : label}</span>
    </span>
  );
}

/**
 * Full panel — shows critical + minor missing items, each with an action
 * button that scrolls/jumps to the relevant edit field.
 *
 * The `onFix` callback receives a field name; the host page is responsible
 * for switching tabs, scrolling, and focusing the right input.
 */
export function MissingDataPanel({
  quality, onFix,
}: { quality: DataQuality; onFix?: (field: string) => void }) {
  const all = [
    ...quality.missing_critical.map((m) => ({ ...m, severity: "critical" as const })),
    ...quality.missing_minor.map((m) => ({ ...m, severity: "minor" as const })),
  ];
  if (all.length === 0) {
    return (
      <div className="card border-emerald-200 bg-emerald-50">
        <div className="text-sm font-semibold text-emerald-800">✓ כל המידע מלא</div>
        <div className="text-xs text-emerald-700 mt-1">
          לא חסר שדה קריטי או נחמד-לדעת. מעקב משלוח שלם.
        </div>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm font-semibold text-slate-800">חסר מידע</div>
          <div className="text-xs text-slate-500">
            לחץ על "השלם עכשיו" כדי לערוך את השדה החסר.
          </div>
        </div>
        <DataQualityBadge type={quality.entity_type} id={quality.entity_id} />
      </div>
      <ul className="divide-y divide-slate-100">
        {all.map((m) => (
          <li
            key={m.field}
            className="py-2 flex items-center justify-between gap-2"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className={clsx(
                "inline-block w-1.5 h-1.5 rounded-full shrink-0",
                m.severity === "critical" ? "bg-red-500" : "bg-amber-500",
              )} />
              <span className="text-sm text-slate-700 truncate">{m.label}</span>
              {m.severity === "critical" && (
                <span className="badge-red text-[9px]">קריטי</span>
              )}
            </div>
            {onFix && (
              <button
                onClick={() => onFix(m.field)}
                className="btn-secondary text-xs px-3 py-1"
              >
                השלם עכשיו
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Small pill marking that a field was manually overridden.
 * Show next to the field label in edit forms so users know auto-updates
 * from email won't touch it.
 */
export function OverridePill({
  overrides, field,
}: {
  overrides?: Record<string, { by?: string; at?: string }> | null;
  field: string;
}) {
  const ov = overrides?.[field];
  if (!ov) return null;
  const date = ov.at ? new Date(ov.at).toLocaleDateString("he-IL") : "";
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded"
      title={`נערך ידנית ע״י ${ov.by || "—"} ב-${date}`}
    >
      🔒 ידני
    </span>
  );
}
