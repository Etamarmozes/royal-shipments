import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listDataReview, flagShipment, bulkFlag, purgeTestData,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState } from "../components/common";
import { hasPermission } from "../auth/store";
import { fmtDateTime, fmtDate } from "../utils/format";
import clsx from "clsx";

/**
 * Existing Shipment Data Review.
 * Shows every shipment with diagnostic info + lets the admin mark as
 * test-data, then bulk-purge only the marked rows.
 *
 * Never deletes anything without explicit user action.
 */
export default function DataReview() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "suspected" | "marked" | "real">("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const q = useQuery({
    queryKey: ["data-review"],
    queryFn: listDataReview,
  });

  const flag = useMutation({
    mutationFn: ({ id, is_test_data, data_source }: any) =>
      flagShipment(id, { is_test_data, data_source }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["data-review"] }),
  });
  const bulk = useMutation({
    mutationFn: ({ ids, is_test_data, data_source }: any) =>
      bulkFlag(ids, is_test_data, data_source),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["data-review"] });
      setSelected(new Set());
    },
  });
  const purge = useMutation({
    mutationFn: () => purgeTestData(),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["data-review"] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
      alert(`נמחקו ${r.deleted} רשומות test data.`);
    },
  });

  const rows = q.data?.rows || [];
  const filtered = useMemo(() => {
    if (filter === "suspected") return rows.filter((r) => r.suspected_demo && !r.is_test_data);
    if (filter === "marked")    return rows.filter((r) => r.is_test_data);
    if (filter === "real")      return rows.filter((r) => !r.suspected_demo && !r.is_test_data);
    return rows;
  }, [rows, filter]);

  const toggle = (id: number) => {
    setSelected((s) => {
      const ns = new Set(s);
      if (ns.has(id)) ns.delete(id); else ns.add(id);
      return ns;
    });
  };
  const selectAllVisible = () => setSelected(new Set(filtered.map((r) => r.id)));
  const clearSelection = () => setSelected(new Set());

  const canEdit = hasPermission("shipment.update");
  const canDelete = hasPermission("shipment.delete");

  if (q.isLoading) return <Loader />;
  if (q.isError) return <ErrorState error={q.error} />;

  const summary = q.data?.summary || { total: 0, suspected_demo: 0, marked_test: 0, real: 0, archived: 0 };
  const markedCount = summary.marked_test;

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="בדיקת נתונים קיימים"
        subtitle="זיהוי איזה רשומות הן demo/test ואיזה הן אמיתיות לפני יבוא נתונים אמיתיים."
      />

      {/* Summary tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
        <Tile label="סה״כ" value={summary.total} tone="default" />
        <Tile label="חשוד דמו" value={summary.suspected_demo} tone="warning"
              onClick={() => setFilter("suspected")} />
        <Tile label="מסומן test" value={summary.marked_test} tone="danger"
              onClick={() => setFilter("marked")} />
        <Tile label="אמיתי" value={summary.real} tone="success"
              onClick={() => setFilter("real")} />
        <Tile label="ארכיון" value={summary.archived} tone="default" />
      </div>

      {/* Filters + bulk actions */}
      <div className="card mb-4 flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          {(["all", "suspected", "marked", "real"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "px-3 py-1 text-xs rounded-full font-medium",
                filter === f
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200",
              )}
            >
              {f === "all" ? "הכל" : f === "suspected" ? "חשודים" : f === "marked" ? "מסומנים" : "אמיתיים"}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <span className="text-sm text-slate-500">
          {selected.size > 0 ? `${selected.size} נבחרו` : `${filtered.length} שורות מוצגות`}
        </span>
        {selected.size > 0 && canEdit && (
          <>
            <button
              className="btn-secondary text-xs"
              onClick={() => bulk.mutate({ ids: [...selected], is_test_data: true, data_source: "demo" })}
              disabled={bulk.isPending}
            >סמן כ-test data</button>
            <button
              className="btn-secondary text-xs"
              onClick={() => bulk.mutate({ ids: [...selected], is_test_data: false })}
              disabled={bulk.isPending}
            >בטל סימון</button>
          </>
        )}
        {selected.size === 0 && (
          <button className="text-xs text-slate-600 hover:text-slate-900"
                  onClick={selectAllVisible}>בחר הכל</button>
        )}
        {selected.size > 0 && (
          <button className="text-xs text-slate-600 hover:text-slate-900"
                  onClick={clearSelection}>נקה בחירה</button>
        )}
      </div>

      {/* Purge danger zone */}
      {markedCount > 0 && canDelete && (
        <div className="card border-red-200 bg-red-50 mb-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-semibold text-red-800">אזור מסוכן</div>
              <div className="text-xs text-red-700 mt-0.5">
                {markedCount} רשומות מסומנות כ-test data. ניתן למחוק אותן לצמיתות.
                המכולות והאירועים המקושרים יימחקו אוטומטית. פעולה לא הפיכה.
              </div>
            </div>
            <button
              className="btn-danger"
              onClick={() => {
                if (confirm(`למחוק ${markedCount} רשומות test data לצמיתות?`)) {
                  purge.mutate();
                }
              }}
              disabled={purge.isPending}
            >
              {purge.isPending ? "מוחק..." : `מחק ${markedCount} רשומות`}
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-xs text-slate-500 border-b border-slate-200">
            <tr>
              <th className="text-right py-2 px-2 w-8">
                <input type="checkbox"
                       checked={selected.size === filtered.length && filtered.length > 0}
                       onChange={(e) => e.target.checked ? selectAllVisible() : clearSelection()} />
              </th>
              <th className="text-right py-2 px-2">SHP</th>
              <th className="text-right py-2 px-2">ספק</th>
              <th className="text-right py-2 px-2">קטגוריה</th>
              <th className="text-right py-2 px-2 text-center">מכולות</th>
              <th className="text-right py-2 px-2">מקור</th>
              <th className="text-right py-2 px-2">data_source</th>
              <th className="text-right py-2 px-2">סטטוס</th>
              <th className="text-right py-2 px-2">נוצר</th>
              <th className="text-right py-2 px-2 text-center">פעולה</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((r) => (
              <tr key={r.id} className={clsx(
                r.is_test_data && "bg-red-50",
                !r.is_test_data && r.suspected_demo && "bg-amber-50",
              )}>
                <td className="py-2 px-2">
                  <input type="checkbox" checked={selected.has(r.id)}
                         onChange={() => toggle(r.id)} />
                </td>
                <td className="py-2 px-2 font-mono font-medium">{r.shp_id}</td>
                <td className="py-2 px-2">{r.supplier || "—"}</td>
                <td className="py-2 px-2">
                  {r.category
                    ? <span className="badge-blue">{r.category}</span>
                    : <span className="text-slate-400 text-xs">—</span>}
                </td>
                <td className="py-2 px-2 text-center tabular-nums">{r.container_count}</td>
                <td className="py-2 px-2 text-xs text-slate-600">{r.creation_source || "—"}</td>
                <td className="py-2 px-2 text-xs">
                  {r.data_source
                    ? <span className="badge-gray">{r.data_source}</span>
                    : <span className="text-slate-400">—</span>}
                </td>
                <td className="py-2 px-2">
                  {r.is_test_data && <span className="badge-red text-[10px]">test data</span>}
                  {!r.is_test_data && r.suspected_demo && (
                    <span className="badge-amber text-[10px]" title={r.demo_reasons.join("\n")}>
                      חשוד דמו
                    </span>
                  )}
                  {!r.is_test_data && !r.suspected_demo && (
                    <span className="badge-green text-[10px]">אמיתי</span>
                  )}
                </td>
                <td className="py-2 px-2 text-xs text-slate-500">
                  {r.created_at ? fmtDate(r.created_at) : "—"}
                </td>
                <td className="py-2 px-2 text-center">
                  {canEdit && (
                    <button
                      className="text-xs text-brand-600 hover:underline"
                      onClick={() => flag.mutate({
                        id: r.id, is_test_data: !r.is_test_data,
                        data_source: !r.is_test_data ? "demo" : undefined,
                      })}
                    >
                      {r.is_test_data ? "בטל סימון" : "סמן test"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={10} className="py-6 text-center text-slate-500">
                  אין רשומות תואמות.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Tile({
  label, value, tone, onClick,
}: {
  label: string; value: number;
  tone: "default" | "success" | "warning" | "danger";
  onClick?: () => void;
}) {
  const cls = {
    default: "border-slate-200",
    success: "border-emerald-200 bg-emerald-50",
    warning: "border-amber-300 bg-amber-50",
    danger:  "border-red-300 bg-red-50",
  }[tone];
  return (
    <button
      onClick={onClick}
      className={clsx(
        "card text-right transition",
        cls,
        onClick && "hover:shadow-md cursor-pointer",
      )}
    >
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums">{value}</div>
    </button>
  );
}
