import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  listQcDocuments, qcSummary, runQcScan, qcApprove, qcArchive,
  searchShipments, type QcRow, type ShipmentSearchRow,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState } from "../components/common";
import { hasPermission } from "../auth/store";
import { downloadDocument, viewDocument } from "../utils/fileAccess";
import clsx from "clsx";

/**
 * Document Assignment QC — operational console.
 *
 * Per-row actions (no auto-action, every change requires user click):
 *   הצג         view PDF / image inline
 *   הורד        download
 *   שייך        open ReassignModal → search shipments → confirm
 *   נתק         clear linked_shipment_id (file kept, audit logged)
 *   ארכב        soft-archive (with delete-file fallback gated by typing DELETE)
 *   תקין        mark current assignment as correct (close as approved_keep)
 *   לבדיקה      keeps QC open + records "user touched" marker
 *
 * Bulk: select N rows → bulk reassign / detach / mark-correct / archive.
 */
export default function DocumentAssignmentReview() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "strong" | "suspicious" | "minor" | "unassigned">("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [reassignFor, setReassignFor] = useState<{ ids: number[]; rows: QcRow[] } | null>(null);
  const [archiveFor, setArchiveFor] = useState<QcRow | null>(null);

  const summary = useQuery({ queryKey: ["qc-summary"], queryFn: qcSummary });
  const docs = useQuery({
    queryKey: ["qc-documents", "open"],
    queryFn: () => listQcDocuments({ status: "open" }),
  });

  const runScan = useMutation({
    mutationFn: runQcScan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["qc-documents"] });
      qc.invalidateQueries({ queryKey: ["qc-summary"] });
    },
  });

  const approveMut = useMutation({
    mutationFn: ({ id, body }: any) => qcApprove(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["qc-documents"] });
      qc.invalidateQueries({ queryKey: ["qc-summary"] });
      qc.invalidateQueries({ queryKey: ["shipment-documents"] });
      qc.invalidateQueries({ queryKey: ["docs"] });
      setReassignFor(null);
      setSelected(new Set());
    },
    onError: (e: any) => alert(`שגיאה: ${e?.message || "לא ידוע"}`),
  });

  const archiveMut = useMutation({
    mutationFn: ({ id, body }: any) => qcArchive(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["qc-documents"] });
      qc.invalidateQueries({ queryKey: ["qc-summary"] });
      qc.invalidateQueries({ queryKey: ["shipment-documents"] });
      qc.invalidateQueries({ queryKey: ["docs"] });
      setArchiveFor(null);
    },
    onError: (e: any) => alert(`שגיאה: ${e?.message || "לא ידוע"}`),
  });

  const rows = docs.data?.rows || [];
  const filtered = useMemo(() => {
    if (filter === "strong")     return rows.filter((r) => r.severity === "strong_mismatch");
    if (filter === "suspicious") return rows.filter((r) => r.severity === "suspicious");
    if (filter === "minor")      return rows.filter((r) => r.severity === "minor");
    if (filter === "unassigned") return rows.filter((r) => r.current_shipment_id === null);
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

  const canAct = hasPermission("document.assign");
  const canDelete = hasPermission("document.delete");

  if (docs.isLoading) return <Loader />;
  if (docs.isError) return <ErrorState error={docs.error} />;

  const sum = summary.data || {
    open_total: 0, open_strong_mismatch: 0, open_suspicious: 0, last_scan_at: null,
  };

  const selectedRows = filtered.filter((r) => selected.has(r.id));

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="בדיקת שיוכי מסמכים"
        subtitle="קונסולת תיקון. כל פעולה דורשת אישור — שום שיוך לא משתנה אוטומטית."
        actions={
          <button
            className="btn-primary"
            onClick={() => runScan.mutate()}
            disabled={runScan.isPending}
          >
            {runScan.isPending ? "סורק..." : "🔄 הרץ QC עכשיו"}
          </button>
        }
      />

      {/* Summary tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
        <Tile label="פתוחים סה״כ" value={sum.open_total} />
        <Tile label="פערים חזקים" value={sum.open_strong_mismatch} tone="danger"
              onClick={() => setFilter("strong")} />
        <Tile label="חשודים" value={sum.open_suspicious} tone="warning"
              onClick={() => setFilter("suspicious")} />
        <Tile label="סריקה אחרונה"
              value={sum.last_scan_at ? new Date(sum.last_scan_at).toLocaleString("he-IL") : "—" as any}
              tone="default" />
        <Tile label="מסומנים" value={selected.size} tone={selected.size > 0 ? "info" : "default"} />
      </div>

      {/* Filters + bulk toolbar */}
      <div className="card mb-4 flex flex-wrap items-center gap-2">
        <div className="flex gap-1 flex-wrap">
          {(["all", "strong", "suspicious", "minor", "unassigned"] as const).map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); clearSelection(); }}
              className={clsx(
                "px-3 py-1 text-xs rounded-full font-medium",
                filter === f ? "bg-slate-900 text-white"
                             : "bg-slate-100 text-slate-700 hover:bg-slate-200",
              )}
            >
              {f === "all" ? "הכל"
                : f === "strong" ? "פערים חזקים"
                : f === "suspicious" ? "חשודים"
                : f === "minor" ? "מינור"
                : "לא משויכים"}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <span className="text-sm text-slate-500">{filtered.length} שורות</span>
        {selected.size === 0 ? (
          <button onClick={selectAllVisible}
                  className="text-xs text-slate-600 hover:text-slate-900">בחר הכל</button>
        ) : (
          <>
            <button onClick={clearSelection}
                    className="text-xs text-slate-600 hover:text-slate-900">נקה בחירה</button>
            {canAct && (
              <>
                <button
                  className="btn-primary text-xs"
                  onClick={() => setReassignFor({ ids: [...selected], rows: selectedRows })}
                >
                  שייך {selected.size} פריטים
                </button>
                <button
                  className="btn-secondary text-xs"
                  onClick={() => {
                    if (!confirm(`לנתק ${selected.size} מסמכים? הקובץ הפיזי יישמר.`)) return;
                    selectedRows.forEach((r) => approveMut.mutate({
                      id: r.id, body: { action: "detach", reason: "bulk detach" },
                    }));
                  }}
                >נתק {selected.size}</button>
                <button
                  className="btn-secondary text-xs"
                  onClick={() => {
                    selectedRows.forEach((r) => approveMut.mutate({
                      id: r.id, body: { action: "mark_correct", reason: "bulk mark correct" },
                    }));
                  }}
                >סמן {selected.size} כתקין</button>
              </>
            )}
          </>
        )}
      </div>

      {/* Rows */}
      <div className="space-y-2">
        {filtered.length === 0 && (
          <EmptyState
            iconName="check"
            tone="success"
            title="אין שיוכים חשודים"
            description={
              filter === "all"
                ? "המערכת לא זיהתה אף מסמך עם שיוך מפוקפק. סורק חוזר רץ אוטומטית מדי שעה."
                : "אין פריטי QC פתוחים בתצוגה הזאת. נסה לשנות את הסינון למעלה."
            }
          />
        )}
        {filtered.map((r) => (
          <RowCard
            key={r.id}
            r={r}
            selected={selected.has(r.id)}
            onToggle={() => toggle(r.id)}
            canAct={canAct}
            canDelete={canDelete}
            isPending={approveMut.isPending || archiveMut.isPending}
            onReassign={() => setReassignFor({ ids: [r.id], rows: [r] })}
            onDetach={() => {
              if (!confirm(`לנתק את "${r.filename}" מ-${r.current_shp_id}?`)) return;
              approveMut.mutate({ id: r.id, body: { action: "detach" } });
            }}
            onMarkCorrect={() =>
              approveMut.mutate({ id: r.id, body: { action: "mark_correct" } })}
            onNeedsReview={() =>
              approveMut.mutate({ id: r.id, body: { action: "needs_review" } })}
            onArchive={() => setArchiveFor(r)}
          />
        ))}
      </div>

      {/* Modals */}
      {reassignFor && (
        <ReassignModal
          rows={reassignFor.rows}
          onClose={() => setReassignFor(null)}
          onConfirm={(targetId) => {
            reassignFor.ids.forEach((id) => approveMut.mutate({
              id, body: { action: "move", target_shipment_id: targetId, reason: "QC reassign" },
            }));
          }}
        />
      )}
      {archiveFor && (
        <ArchiveModal
          row={archiveFor}
          onClose={() => setArchiveFor(null)}
          onConfirm={(mode, reason) =>
            archiveMut.mutate({ id: archiveFor.id, body: { mode, reason } })}
        />
      )}
    </div>
  );
}


/** ===================================================================
 * RowCard — one document with all 7 action buttons
 * =================================================================== */
function RowCard({
  r, selected, onToggle, canAct, canDelete, isPending,
  onReassign, onDetach, onMarkCorrect, onNeedsReview, onArchive,
}: {
  r: QcRow;
  selected: boolean;
  onToggle: () => void;
  canAct: boolean;
  canDelete: boolean;
  isPending: boolean;
  onReassign: () => void;
  onDetach: () => void;
  onMarkCorrect: () => void;
  onNeedsReview: () => void;
  onArchive: () => void;
}) {
  const sevColor = {
    strong_mismatch: "border-red-300 bg-red-50",
    suspicious: "border-amber-300 bg-amber-50",
    minor: "border-blue-200 bg-blue-50",
    ok: "border-slate-200",
  }[r.severity] || "border-slate-200";

  return (
    <div className={clsx("rounded-xl border p-3", sevColor)}>
      <div className="flex items-start gap-3">
        <input type="checkbox" checked={selected} onChange={onToggle}
               className="mt-1.5" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-base">📄</span>
            <span className="font-medium text-slate-800 truncate"
                  title={r.filename || ""}>
              {r.filename || "—"}
            </span>
            {r.document_type && (
              <span className="badge-blue text-[10px]">{r.document_type}</span>
            )}
            <SeverityBadge severity={r.severity} score={r.confidence_score} />
          </div>

          <div className="text-xs text-slate-700 space-y-0.5 mb-2">
            <div>
              <span className="text-slate-500">משויך כעת:</span>{" "}
              {r.current_shp_id ? (
                <Link to={`/shipments/${r.current_shipment_id}`}
                      className="text-brand-600 hover:underline">
                  {r.current_shp_id}
                </Link>
              ) : <span className="text-amber-700">לא משויך</span>}
              {r.current_supplier && (
                <span className="text-slate-600"> · {r.current_supplier}</span>
              )}
            </div>
            {r.suspected_shp_id && (
              <div>
                <span className="text-slate-500">מוצע:</span>{" "}
                <span className="text-emerald-700 font-medium">
                  {r.suspected_shp_id}
                </span>
                {r.suspected_supplier && (
                  <span className="text-slate-600"> · {r.suspected_supplier}</span>
                )}
              </div>
            )}
            {r.mismatch_reasons.length > 0 && (
              <ul className="text-[11px] text-slate-700 mt-1">
                {r.mismatch_reasons.slice(0, 4).map((reason, i) => (
                  <li key={i}>• {reason}</li>
                ))}
              </ul>
            )}
            {r.matched_signals.length > 0 && (
              <details className="text-[10px] text-slate-500 mt-1">
                <summary className="cursor-pointer">
                  אותות שזוהו ({r.matched_signals.length})
                </summary>
                <ul className="ml-3 mt-1">
                  {r.matched_signals.slice(0, 6).map((s, i) => (
                    <li key={i}>
                      <code>{s.keyword}</code> ב-<b>{s.signal}</b> — {s.rule}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap gap-1 pt-2 border-t border-slate-200/60">
            <button onClick={() => viewDocument(r.document_id)}
                    className="btn-secondary text-xs px-3 py-1">הצג</button>
            <button onClick={() => downloadDocument(r.document_id, r.filename || undefined)}
                    className="btn-secondary text-xs px-3 py-1">הורד</button>
            {canAct && (
              <>
                <button onClick={onReassign}
                        disabled={isPending}
                        className="text-xs px-3 py-1 rounded-lg bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-50"
                        title={r.suspected_shp_id ? `מוצע: ${r.suspected_shp_id}` : "בחר משלוח"}>
                  שייך{r.suspected_shp_id ? ` (${r.suspected_shp_id})` : ""}
                </button>
                <button onClick={onDetach} disabled={isPending}
                        className="btn-secondary text-xs px-3 py-1">נתק</button>
                <button onClick={onMarkCorrect} disabled={isPending}
                        className="text-xs px-3 py-1 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100">
                  ✓ תקין
                </button>
                <button onClick={onNeedsReview} disabled={isPending}
                        className="text-xs px-3 py-1 rounded-lg bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100">
                  ☐ לבדיקה
                </button>
              </>
            )}
            {canDelete && (
              <button onClick={onArchive} disabled={isPending}
                      className="btn-danger text-xs px-3 py-1">
                ארכב
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


/** ===================================================================
 * ReassignModal — searchable shipment list, confirm-then-apply
 * =================================================================== */
function ReassignModal({
  rows, onClose, onConfirm,
}: {
  rows: QcRow[];
  onClose: () => void;
  onConfirm: (targetShipmentId: number) => void;
}) {
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Pre-suggest the QC's suspected shipment if all rows agree on one
  const suggestedId = useMemo(() => {
    const ids = new Set(rows.map((r) => r.suspected_shipment_id).filter(Boolean));
    return ids.size === 1 ? [...ids][0] as number : null;
  }, [rows]);

  // Pre-fill search with the suggested supplier name to make it easy to click
  useEffect(() => {
    if (suggestedId && rows[0]?.suspected_supplier) {
      setQ(rows[0].suspected_supplier.split(" / ")[0]);
    }
  }, [suggestedId, rows]);

  const search = useQuery({
    queryKey: ["shipment-search", q],
    queryFn: () => searchShipments(q || ""),
    enabled: true,
  });

  const isBulk = rows.length > 1;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
         onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden"
           onClick={(e) => e.stopPropagation()}>
        <header className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
          <div>
            <div className="font-semibold text-slate-900">
              {isBulk ? `שיוך ${rows.length} מסמכים` : `שייך מסמך למשלוח אחר`}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              {isBulk
                ? "שלב את הבחירה למשלוח יחיד עבור כל הפריטים שנבחרו."
                : `${rows[0]?.filename}`}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl px-2">✕</button>
        </header>

        {/* Context for the selected docs */}
        {!isBulk && rows[0] && (
          <div className="px-5 py-3 bg-slate-50 border-b border-slate-200 text-xs space-y-0.5">
            <div>
              <span className="text-slate-500">משויך כעת:</span>{" "}
              {rows[0].current_shp_id || "לא משויך"}
              {rows[0].current_supplier && ` · ${rows[0].current_supplier}`}
            </div>
            {rows[0].suspected_shp_id && (
              <div>
                <span className="text-slate-500">QC מציע:</span>{" "}
                <span className="text-emerald-700 font-medium">
                  {rows[0].suspected_shp_id} · {rows[0].suspected_supplier}
                </span>
              </div>
            )}
            {rows[0].mismatch_reasons.length > 0 && (
              <div className="text-[11px] text-slate-600 pt-1">
                סיבה: {rows[0].mismatch_reasons[0]}
              </div>
            )}
          </div>
        )}

        {/* Search input */}
        <div className="px-5 py-3 border-b border-slate-200">
          <input
            autoFocus
            type="text"
            className="input"
            placeholder="חיפוש: SHP / ספק / קטגוריה / מכולה / PO / BL …"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-3">
          {search.isLoading ? (
            <Loader />
          ) : (search.data?.rows || []).length === 0 ? (
            <div className="text-center text-slate-500 text-sm py-8">
              לא נמצאו תוצאות. נסה ניסוח אחר.
            </div>
          ) : (
            <div className="space-y-1">
              {(search.data?.rows || []).map((s) => (
                <ShipmentRow
                  key={s.id}
                  s={s}
                  selected={selectedId === s.id}
                  highlighted={s.id === suggestedId}
                  onClick={() => setSelectedId(s.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="px-5 py-3 border-t border-slate-200 flex items-center justify-between gap-2">
          <div className="text-xs text-slate-500">
            {selectedId
              ? <>נבחר: <b>{search.data?.rows.find((r) => r.id === selectedId)?.shp_id}</b></>
              : "בחר משלוח מהרשימה"}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn-secondary">ביטול</button>
            <button
              onClick={() => selectedId && onConfirm(selectedId)}
              disabled={!selectedId}
              className="btn-primary"
            >
              אשר שיוך
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function ShipmentRow({
  s, selected, highlighted, onClick,
}: {
  s: ShipmentSearchRow;
  selected: boolean;
  highlighted: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "w-full text-right rounded-lg border p-2.5 transition",
        selected
          ? "border-brand-500 bg-brand-50"
          : highlighted
            ? "border-emerald-300 bg-emerald-50 hover:bg-emerald-100"
            : "border-slate-200 bg-white hover:bg-slate-50",
      )}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono font-semibold">{s.shp_id}</span>
        <span className="text-sm">— {s.supplier || "—"}</span>
        {highlighted && <span className="badge-green text-[10px]">QC מוצע</span>}
        {s.category && <span className="badge-blue text-[10px]">{s.category}</span>}
      </div>
      {s.goods_description && (
        <div className="text-xs text-slate-600 truncate mt-0.5">
          {s.goods_description}
        </div>
      )}
      <div className="text-[10px] text-slate-500 mt-0.5 flex flex-wrap gap-2">
        {s.po_number && <span>PO: {s.po_number}</span>}
        {s.bol_number && <span>BL: {s.bol_number}</span>}
        {s.eta_israel && <span>ETA: {s.eta_israel}</span>}
        {s.container_numbers.length > 0 && (
          <span className="font-mono">{s.container_numbers.slice(0, 2).join(", ")}</span>
        )}
      </div>
    </button>
  );
}


/** ===================================================================
 * ArchiveModal — archive_record_only / archive_file / delete_file
 * =================================================================== */
function ArchiveModal({
  row, onClose, onConfirm,
}: {
  row: QcRow;
  onClose: () => void;
  onConfirm: (mode: "archive_record_only" | "archive_file" | "delete_file",
              reason: string) => void;
}) {
  const [mode, setMode] = useState<"archive_record_only" | "archive_file" | "delete_file">(
    "archive_record_only");
  const [reason, setReason] = useState("");
  const [confirmText, setConfirmText] = useState("");

  const canConfirm = mode !== "delete_file" || confirmText === "DELETE";

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
         onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col"
           onClick={(e) => e.stopPropagation()}>
        <header className="px-5 py-3 border-b border-slate-200">
          <div className="font-semibold text-slate-900">ארכב/מחק מסמך</div>
          <div className="text-xs text-slate-500 mt-0.5 truncate">
            {row.filename}
          </div>
        </header>

        <div className="p-5 space-y-3">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            ⚠️ פעולה זו תוסר את המסמך ממסך השילוח.
            ברירת המחדל: ארכוב רשומה בלבד — הקובץ הפיזי לא נמחק.
          </div>

          <Mode
            value="archive_record_only" current={mode} onSelect={setMode}
            title="ארכב רשומה בלבד (מומלץ)"
            desc="המסמך מוסתר מכל המסכים. הקובץ הפיזי נשאר על הדיסק. הפיך."
          />
          <Mode
            value="archive_file" current={mode} onSelect={setMode}
            title="ארכב + העבר את הקובץ לתיקיית _archived"
            desc="הקובץ עובר ל-uploads/documents/_archived/. הפיך ידנית."
          />
          <Mode
            value="delete_file" current={mode} onSelect={setMode}
            title="מחק את הקובץ הפיזי לצמיתות"
            desc="הקובץ נמחק מהדיסק. לא ניתן לשחזר. דורש הקלדת DELETE."
            danger
          />

          <div>
            <label className="label">סיבה (אופציונלי)</label>
            <textarea
              className="input" rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="לדוגמה: נמשך בטעות מ-thread שלא רלוונטי"
            />
          </div>

          {mode === "delete_file" && (
            <div>
              <label className="label text-red-700">
                להמשיך — הקלד <code>DELETE</code> כאן:
              </label>
              <input
                className="input"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="DELETE"
              />
            </div>
          )}
        </div>

        <footer className="px-5 py-3 border-t border-slate-200 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">ביטול</button>
          <button
            onClick={() => onConfirm(mode, reason)}
            disabled={!canConfirm}
            className={clsx(
              "btn",
              mode === "delete_file"
                ? "bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                : "btn-primary",
            )}
          >
            {mode === "delete_file" ? "מחק לצמיתות" : "ארכב"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function Mode({
  value, current, onSelect, title, desc, danger,
}: {
  value: "archive_record_only" | "archive_file" | "delete_file";
  current: string;
  onSelect: (v: any) => void;
  title: string; desc: string; danger?: boolean;
}) {
  const active = current === value;
  return (
    <button
      onClick={() => onSelect(value)}
      className={clsx(
        "w-full text-right rounded-lg border p-3 transition",
        active
          ? danger ? "border-red-400 bg-red-50" : "border-brand-500 bg-brand-50"
          : "border-slate-200 hover:bg-slate-50",
      )}
    >
      <div className={clsx(
        "text-sm font-medium",
        danger && "text-red-800"
      )}>{title}</div>
      <div className="text-xs text-slate-600 mt-0.5">{desc}</div>
    </button>
  );
}


/** ===================================================================
 * Helpers
 * =================================================================== */
function SeverityBadge({ severity, score }: { severity: string; score: number }) {
  const cls = {
    strong_mismatch: "bg-red-100 text-red-800 border-red-200",
    suspicious:      "bg-amber-100 text-amber-800 border-amber-200",
    minor:           "bg-blue-50 text-blue-700 border-blue-200",
    ok:              "bg-emerald-50 text-emerald-700 border-emerald-200",
  }[severity] || "bg-slate-100 text-slate-700 border-slate-200";
  const label = {
    strong_mismatch: "פער חזק",
    suspicious:      "חשוד",
    minor:           "מינור",
    ok:              "תקין",
  }[severity] || severity;
  return (
    <span className={clsx("text-[10px] px-2 py-0.5 rounded-md border font-medium", cls)}>
      {label} ({score}%)
    </span>
  );
}

function Tile({
  label, value, tone, onClick,
}: {
  label: string; value: number | string;
  tone?: "default" | "info" | "warning" | "danger";
  onClick?: () => void;
}) {
  const cls = {
    default: "border-slate-200",
    info:    "border-blue-200 bg-blue-50",
    warning: "border-amber-300 bg-amber-50",
    danger:  "border-red-300 bg-red-50",
  }[tone || "default"];
  return (
    <button
      onClick={onClick}
      className={clsx("card text-right transition", cls,
        onClick && "hover:shadow-md cursor-pointer")}
    >
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums">{value}</div>
    </button>
  );
}
