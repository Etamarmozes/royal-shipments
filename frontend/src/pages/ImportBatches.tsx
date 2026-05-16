import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  listImportBatches, getImportBatch, rollbackImportBatch,
  type ImportBatchSummary,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState } from "../components/common";
import { hasPermission } from "../auth/store";
import { fmtDateTime } from "../utils/format";
import clsx from "clsx";

/**
 * Import Batches — list every Excel apply + drill into each + rollback.
 *
 * Rollback rules (enforced by the backend):
 *   - Archives only shipments CREATED by this batch (creation_source =
 *     "excel_import_external" + import_batch_id = batch.id)
 *   - UPDATE actions are NOT auto-reverted
 *   - Soft-delete only — never hard-deletes anything
 *   - If a shipment has manual edits since import, it's still archived but
 *     the response flags `had_post_import_edits` per shipment
 */
export default function ImportBatches() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);

  const list = useQuery({
    queryKey: ["import-batches"],
    queryFn: listImportBatches,
  });

  const detail = useQuery({
    queryKey: ["import-batch", selected],
    queryFn: () => getImportBatch(selected!),
    enabled: !!selected,
  });

  const canRollback = hasPermission("shipment.archive");

  if (list.isLoading) return <Loader />;
  if (list.isError) return <ErrorState error={list.error} />;

  const rows = list.data || [];

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="Import Batches"
        subtitle="כל יבוא Excel נשמר כ-batch. לחץ על batch כדי לראות פרטים ולבטל אותו."
        actions={
          <Link to="/import-excel" className="btn-primary">📊 ייבוא חדש</Link>
        }
      />

      <div className="grid lg:grid-cols-2 gap-4">
        {/* List */}
        <div className="card overflow-x-auto">
          <h2 className="font-semibold mb-3">היסטוריית יבוא</h2>
          {rows.length === 0 ? (
            <EmptyState
              iconName="excel"
              title="אין ייבואים עדיין"
              description="כל ייבוא Excel חיצוני (ICL / Eli Line) שיאושר יישמר כאן עם אפשרות Rollback מבוקרת."
              action={{ label: "ייבוא Excel חדש", to: "/import-excel" }}
            />
          ) : (
            <table className="min-w-full text-xs">
              <thead className="text-slate-500 bg-slate-50">
                <tr>
                  <th className="text-right py-2 px-2">#</th>
                  <th className="text-right py-2 px-2">ספק</th>
                  <th className="text-right py-2 px-2">קובץ</th>
                  <th className="text-right py-2 px-2">תאריך</th>
                  <th className="text-right py-2 px-2 text-center">חדשים</th>
                  <th className="text-right py-2 px-2 text-center">עודכנו</th>
                  <th className="text-right py-2 px-2 text-center">דולגו</th>
                  <th className="text-right py-2 px-2">סטטוס</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((b) => (
                  <BatchRow
                    key={b.id}
                    b={b}
                    active={selected === b.id}
                    onClick={() => setSelected(b.id)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail */}
        <div className="card">
          <h2 className="font-semibold mb-3">פרטים</h2>
          {!selected ? (
            <div className="text-sm text-slate-500 py-4 text-center">
              בחר batch מהרשימה כדי לראות פרטים.
            </div>
          ) : detail.isLoading ? (
            <Loader />
          ) : detail.data ? (
            <BatchDetail
              batch={detail.data}
              canRollback={canRollback}
              onRolledBack={() => {
                qc.invalidateQueries({ queryKey: ["import-batches"] });
                qc.invalidateQueries({ queryKey: ["import-batch", selected] });
                qc.invalidateQueries({ queryKey: ["shipments"] });
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}


function BatchRow({
  b, active, onClick,
}: {
  b: ImportBatchSummary;
  active: boolean;
  onClick: () => void;
}) {
  const isRolledBack = b.status === "rolled_back";
  return (
    <tr
      onClick={onClick}
      className={clsx(
        "cursor-pointer hover:bg-slate-50",
        active && "bg-brand-50",
        isRolledBack && "opacity-60",
      )}
    >
      <td className="py-2 px-2 font-mono">{b.id}</td>
      <td className="py-2 px-2">{b.source_provider}</td>
      <td className="py-2 px-2 truncate max-w-[140px]" title={b.source_file_name || ""}>
        {b.source_file_name || "—"}
      </td>
      <td className="py-2 px-2 text-[10px]">
        {b.imported_at ? fmtDateTime(b.imported_at) : "—"}
      </td>
      <td className="py-2 px-2 text-center text-emerald-700 font-semibold">
        {b.created_count}
      </td>
      <td className="py-2 px-2 text-center text-blue-700 font-semibold">
        {b.updated_count}
      </td>
      <td className="py-2 px-2 text-center text-slate-600">{b.skipped_count}</td>
      <td className="py-2 px-2">
        {isRolledBack ? (
          <span className="badge-red text-[10px]">בוטל</span>
        ) : b.error_count > 0 ? (
          <span className="badge-amber text-[10px]">{b.error_count} שגיאות</span>
        ) : (
          <span className="badge-green text-[10px]">פעיל</span>
        )}
      </td>
    </tr>
  );
}


function BatchDetail({
  batch, canRollback, onRolledBack,
}: {
  batch: any;
  canRollback: boolean;
  onRolledBack: () => void;
}) {
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [open, setOpen] = useState(false);

  const rollbackMut = useMutation({
    mutationFn: () => rollbackImportBatch(batch.id, reason),
    onSuccess: (r) => {
      let msg = `Batch #${batch.id} בוטל.\n` +
                `  ${r.archived_count} משלוחים הועברו לארכיון.`;
      if (r.had_edits_count > 0) {
        msg += `\n\n⚠ ${r.had_edits_count} משלוחים נערכו ידנית מאז הייבוא ובכל זאת בוטלו. אפשר לשחזר ידנית מהארכיון.`;
      }
      alert(msg);
      setOpen(false);
      setReason("");
      setConfirmText("");
      onRolledBack();
    },
    onError: (e: any) => alert(`שגיאה: ${e?.message || "—"}`),
  });

  const isRolledBack = batch.status === "rolled_back";

  return (
    <div className="space-y-3">
      <div className="text-xs space-y-0.5">
        <Kv k="Batch ID" v={`#${batch.id}`} />
        <Kv k="ספק / פורמט" v={batch.source_provider} />
        <Kv k="קובץ" v={batch.source_file_name || "—"} />
        <Kv k="גיליון" v={batch.source_sheet_name || "—"} />
        <Kv k="ייבא ע״י" v={batch.imported_by || "—"} />
        <Kv k="תאריך ייבוא" v={batch.imported_at ? fmtDateTime(batch.imported_at) : "—"} />
        <Kv k="שורות בתצוגה" v={String(batch.total_rows_in_preview)} />
        <Kv k="נוצרו" v={String(batch.created_count)} />
        <Kv k="עודכנו" v={String(batch.updated_count)} />
        <Kv k="דולגו" v={String(batch.skipped_count)} />
        {batch.error_count > 0 && <Kv k="שגיאות" v={String(batch.error_count)} />}
        <Kv k="סטטוס" v={batch.status} />
        {isRolledBack && (
          <>
            <Kv k="בוטל ב" v={batch.rolled_back_at ? fmtDateTime(batch.rolled_back_at) : "—"} />
            <Kv k="בוטל ע״י" v={batch.rolled_back_by || "—"} />
            <Kv k="כמות שהועברה לארכיון" v={String(batch.rolled_back_count)} />
            {batch.rolled_back_reason && (
              <Kv k="סיבה" v={batch.rolled_back_reason} />
            )}
          </>
        )}
      </div>

      {batch.live_shipments && batch.live_shipments.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 mb-1">
            משלוחים פעילים מ-batch זה ({batch.live_shipments.length}):
          </div>
          <ul className="text-xs space-y-0.5 max-h-40 overflow-y-auto">
            {batch.live_shipments.map((s: any) => (
              <li key={s.id} className="flex items-center gap-2">
                <Link to={`/shipments/${s.id}`}
                      className="font-mono text-brand-600 hover:underline">
                  {s.shp_id}
                </Link>
                <span className="text-slate-700 truncate">{s.supplier || "—"}</span>
                {s.had_post_import_edits && (
                  <span className="badge-amber text-[9px]">נערך ידנית</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Rollback */}
      {!isRolledBack && canRollback && (
        <div className="pt-3 border-t border-slate-200">
          {!open ? (
            <button onClick={() => setOpen(true)}
                    className="btn-danger text-xs w-full">
              ↶ Rollback batch זה
            </button>
          ) : (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
              <div className="text-xs text-red-900 font-semibold">
                ⚠ ביטול Batch — פעולה רגישה
              </div>
              <div className="text-[11px] text-red-800">
                כל המשלוחים שנוצרו ב-batch זה יועברו לארכיון.
                משלוחים שעודכנו (לא נוצרו) ב-batch זה — לא יושפעו.
                הפעולה רכה: הקבצים והשורות נשארים — רק "מוסתרים".
              </div>
              <textarea
                className="input text-xs"
                rows={2}
                placeholder="סיבת הביטול"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <input
                className="input text-xs"
                placeholder="הקלד ROLLBACK"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <button onClick={() => { setOpen(false); setReason(""); setConfirmText(""); }}
                        className="btn-secondary text-xs">ביטול</button>
                <button
                  onClick={() => rollbackMut.mutate()}
                  disabled={confirmText !== "ROLLBACK" || rollbackMut.isPending}
                  className="btn-danger text-xs"
                >
                  {rollbackMut.isPending ? "מבטל..." : `↶ בטל ${batch.live_shipments.length} משלוחים`}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function Kv({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex">
      <span className="text-slate-500 w-32 shrink-0">{k}:</span>
      <span className="text-slate-800 break-all">{v}</span>
    </div>
  );
}
