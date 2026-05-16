import { useState, useRef, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  importTemplateUrl, previewExcelImport, applyExcelImport,
  type ImportPreview, type ImportPreviewRow,
} from "../api/endpoints";
import { PageHeader, Loader } from "../components/common";
import { hasPermission } from "../auth/store";
import clsx from "clsx";

/**
 * Excel shipment import — 3-step flow:
 *   1. Download template (button → backend serves the .xlsx)
 *   2. User fills the template, uploads → preview returns parsed/dedup view
 *   3. User chooses per-row action (create/update/skip) and clicks Approve
 *      → backend applies in a single transaction.
 */
export default function ImportExcel() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  // External-format rows are keyed by source_row_number.
  // Template rows are keyed by _row. We use source_row_number when present.
  const [actions, setActions] = useState<Record<string, "create" | "update" | "skip">>({});
  const [confirmText, setConfirmText] = useState("");

  // Helper to compute the row key consistently
  const rowKey = (r: any): string => String(r.source_row_number ?? r._row);

  // Track per-row "force create anyway" overrides (set by the modal)
  const [forceCreate, setForceCreate] = useState<Record<string, boolean>>({});

  const previewMut = useMutation({
    mutationFn: (f: File) => previewExcelImport(f),
    onSuccess: (data) => {
      setPreview(data);
      setConfirmText("");
      setForceCreate({});
      // Initialize actions:
      //  - needs_review rows → skip
      //  - exact_duplicate / strong_possible_match → skip
      //  - soft_possible_match → create (with warning shown)
      //  - no_match → create
      //  - error/needs_review default → skip
      const a: Record<string, "create" | "update" | "skip"> = {};
      for (const r of data.rows) {
        const key = rowKey(r);
        if (r._action_default === "error") {
          a[key] = "skip";
        } else if ((r._action_default as string) === "needs_review") {
          a[key] = "skip";
        } else {
          a[key] = r._action_default as any;
        }
      }
      setActions(a);
    },
  });

  const applyMut = useMutation({
    mutationFn: () => {
      if (!preview) throw new Error("no preview");
      const rows = preview.rows.map((r) => {
        const key = rowKey(r);
        return {
          ...r,
          _action: actions[key] || "skip",
          // Pass the explicit override flag through to the backend so
          // it knows the user has consciously chosen to create a duplicate
          _force_create: actions[key] === "create" && !!forceCreate[key],
        };
      });
      return applyExcelImport(rows);
    },
    onSuccess: (r: any) => {
      qc.invalidateQueries({ queryKey: ["shipments"] });
      qc.invalidateQueries({ queryKey: ["containers"] });
      qc.invalidateQueries({ queryKey: ["data-review"] });
      qc.invalidateQueries({ queryKey: ["import-batches"] });
      // Different summary shape for external vs template
      let msg: string;
      if (r.batch_id) {
        msg =
          `יבוא הושלם — Batch #${r.batch_id} (${r.source_provider})\n` +
          `  נוצרו ${r.created} משלוחים\n` +
          `  עודכנו ${r.updated} משלוחים\n` +
          `  דולגו ${r.skipped} שורות\n` +
          `  נוספו ${r.containers_added} placeholder מכולות\n` +
          `  שגיאות: ${r.errors}`;
        const errs = (r.per_row || []).filter((x: any) => x.error);
        if (errs.length) {
          msg += "\n\nשגיאות:\n" +
            errs.map((x: any) => `  • שורה ${x.source_row_number}: ${x.error}`).join("\n");
        }
      } else {
        msg =
          `יבוא הושלם:\n` +
          `  נוצרו ${r.created_shipments} משלוחים\n` +
          `  עודכנו ${r.updated_shipments} משלוחים\n` +
          `  נוספו ${r.added_containers} מכולות\n` +
          `  עודכנו ${r.updated_containers} מכולות\n` +
          `  דולגו ${r.skipped} שורות` +
          (r.details && r.details.length ? `\n\nפרטים:\n${r.details.join("\n")}` : "");
      }
      alert(msg);
      // Reset
      setFile(null);
      setPreview(null);
      setActions({});
      setForceCreate({});
      setConfirmText("");
      if (fileRef.current) fileRef.current.value = "";
    },
  });

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(null);
    previewMut.mutate(f);
  };

  const setAction = (key: string, action: "create" | "update" | "skip") => {
    setActions((a) => ({ ...a, [key]: action }));
  };

  // Live counters per current action selection
  const liveCounts = useMemo(() => {
    if (!preview) return { create: 0, update: 0, skip: 0, needs_review: 0 };
    let create = 0, update = 0, skip = 0, needs_review = 0;
    for (const r of preview.rows) {
      const a = actions[rowKey(r)] || "skip";
      if (a === "create") create++;
      else if (a === "update") update++;
      else skip++;
      if ((r as any).needs_review) needs_review++;
    }
    return { create, update, skip, needs_review };
  }, [preview, actions]);

  const canImport = hasPermission("shipment.create");

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="ייבוא משלוחים מאקסל"
        subtitle="הורד תבנית, מלא, העלה — תקבל תצוגה מקדימה לאישור לפני שזה נכנס למסד."
      />

      {!canImport && (
        <div className="card border-amber-200 bg-amber-50 mb-4 text-sm">
          אין לך הרשאה ליצור משלוחים. דבר עם מנהל יבוא.
        </div>
      )}

      {/* Step 1: download template */}
      <Step n={1} title="הורד תבנית">
        <p className="text-sm text-slate-600 mb-3">
          התבנית מכילה את כל העמודות, נתוני דוגמה (כתום בהיר), ועזרה בכל עמודה.
          השדה <code>supplier_name</code> חובה. שאר השדות אופציונליים.
        </p>
        <a
          href={importTemplateUrl()}
          download
          className="btn-primary"
        >
          📥 הורד shipment_import_template.xlsx
        </a>
        <div className="mt-3 text-xs text-slate-500">
          מחק את שורות הדוגמה (כתום) לפני שמירה.
          ערוך-העלה: <code>SAMPLE-1</code>, <code>SAMPLE-2</code> = שורות לדוגמה (תסוננו אוטומטית).
        </div>
      </Step>

      {/* Step 2: upload */}
      <Step n={2} title="העלה את הקובץ המלא">
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={onPick}
        />
        <button
          className="btn-primary"
          onClick={() => fileRef.current?.click()}
          disabled={previewMut.isPending}
        >
          {previewMut.isPending ? "מנתח..." : file ? `החלף קובץ (${file.name})` : "בחר קובץ Excel"}
        </button>
        {previewMut.isError && (
          <div className="mt-3 text-sm text-red-700">
            שגיאה: {(previewMut.error as Error)?.message}
          </div>
        )}
      </Step>

      {/* Step 3: preview + approve */}
      {previewMut.isPending && <Loader text="מנתח את הקובץ..." />}
      {preview && (
        <Step n={3} title="תצוגה מקדימה ואישור">
          {/* Format banner */}
          {preview.format && preview.format !== "royal_linen_template" && (
            <FormatBanner preview={preview} />
          )}

          {preview.file_errors.length > 0 && (
            <div className="card border-red-200 bg-red-50 mb-3">
              <div className="font-semibold text-red-800 mb-1">שגיאות בקובץ</div>
              <ul className="text-sm text-red-700">
                {preview.file_errors.map((e, i) => <li key={i}>• {e}</li>)}
              </ul>
            </div>
          )}

          {preview.rows.length > 0 && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 mb-4">
                <SummaryTile label="סה״כ" value={preview.summary.total_rows} />
                <SummaryTile label="חדשים (ברירת מחדל)" value={preview.summary.create} tone="success" />
                <SummaryTile label="כפילות מדויקת" value={preview.summary.exact_duplicate || 0} tone="danger" />
                <SummaryTile label="התאמה חזקה" value={preview.summary.strong_match || 0} tone="warning" />
                <SummaryTile label="התאמה רכה" value={preview.summary.soft_match || 0} tone="caution" />
                <SummaryTile label="דורש בדיקה" value={preview.summary.needs_review || 0} tone="warning" />
              </div>

              {((preview.summary.exact_duplicate || 0) + (preview.summary.strong_match || 0)) > 0 && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 mb-4 text-sm">
                  <div className="font-semibold text-red-900">
                    🛑 {((preview.summary.exact_duplicate || 0) + (preview.summary.strong_match || 0))} שורות
                    מתאימות לכפילויות חזקות במערכת.
                  </div>
                  <div className="text-xs text-red-800 mt-1">
                    ברירת המחדל שלהן היא "דלג". כדי בכל זאת ליצור — פתח את השורה,
                    בחר "צור חדש", ואשר עם <code>CREATE ANYWAY</code> בחלונית האישור.
                    כדי לעדכן את הקיים — בחר "עדכן את SHP-XXX" מהתפריט.
                  </div>
                </div>
              )}

              {/* External-format rich rendering */}
              {(preview.format === "icl" || preview.format === "eli_line") ? (
                <ExternalRowList
                  rows={preview.rows}
                  format={preview.format}
                  actions={actions}
                  setAction={setAction}
                  forceCreate={forceCreate}
                  setForceCreate={(key, val) =>
                    setForceCreate((m) => ({ ...m, [key]: val }))
                  }
                />
              ) : (
                <div className="overflow-x-auto card mb-4">
                  <table className="min-w-full text-xs">
                    <thead className="text-slate-500 bg-slate-50">
                      <tr>
                        <th className="py-2 px-2 text-right">שורה</th>
                        <th className="py-2 px-2 text-right">SHP</th>
                        <th className="py-2 px-2 text-right">ספק</th>
                        <th className="py-2 px-2 text-right">מכולה</th>
                        <th className="py-2 px-2 text-right">BL</th>
                        <th className="py-2 px-2 text-right">PO</th>
                        <th className="py-2 px-2 text-right">ETA</th>
                        <th className="py-2 px-2 text-right">קרטונים</th>
                        <th className="py-2 px-2 text-right">CBM</th>
                        <th className="py-2 px-2 text-right">תיאור</th>
                        <th className="py-2 px-2 text-right">פעולה</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {preview.rows.map((r) => (
                        <PreviewRow
                          key={r._row}
                          row={r}
                          action={actions[rowKey(r)] || "skip"}
                          setAction={(a) => setAction(rowKey(r), a)}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Live counters for the user's current selections */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 mb-3">
                <div className="text-xs text-slate-500 mb-2">פעולות נבחרות:</div>
                <div className="flex flex-wrap gap-3 text-sm">
                  <span><b className="text-emerald-700">{liveCounts.create}</b> ליצירה</span>
                  <span><b className="text-blue-700">{liveCounts.update}</b> לעדכון</span>
                  <span><b className="text-slate-700">{liveCounts.skip}</b> ידולג</span>
                  {liveCounts.needs_review > 0 && (
                    <span className="text-amber-800">
                      ⚠ <b>{liveCounts.needs_review}</b> שורות סומנו "דורש בדיקה" —
                      ברירת המחדל שלהן היא "דלג"
                    </span>
                  )}
                </div>
              </div>

              {/* Confirm gate: user must type APPLY before the button activates */}
              {canImport && preview.applyable !== false && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 mb-3">
                  <div className="text-sm text-amber-900 mb-2">
                    כדי לאשר את הייבוא, הקלד <code>APPLY</code> בתיבה למטה ולחץ על כפתור הייבוא.
                    {preview.format === "icl" || preview.format === "eli_line" ? (
                      <> פעולה זו תיצור Import Batch שניתן לבטל מאוחר יותר ב-
                        <Link to="/import-batches" className="text-brand-600 underline">
                          /import-batches
                        </Link>.</>
                    ) : null}
                  </div>
                  <input
                    type="text"
                    className="input"
                    value={confirmText}
                    onChange={(e) => setConfirmText(e.target.value)}
                    placeholder="הקלד APPLY"
                  />
                </div>
              )}

              <div className="flex justify-end gap-2">
                <button
                  className="btn-secondary"
                  onClick={() => { setPreview(null); setFile(null); setActions({}); setForceCreate({}); setConfirmText(""); if (fileRef.current) fileRef.current.value = ""; }}
                  disabled={applyMut.isPending}
                >
                  ביטול
                </button>
                {canImport && preview.applyable !== false && (
                  <button
                    className="btn-primary"
                    onClick={() => applyMut.mutate()}
                    disabled={applyMut.isPending || confirmText !== "APPLY" ||
                             (liveCounts.create + liveCounts.update === 0)}
                    title={
                      confirmText !== "APPLY"
                        ? "הקלד APPLY בתיבת האישור"
                        : liveCounts.create + liveCounts.update === 0
                          ? "לא נבחרו שורות ליצירה או לעדכון"
                          : ""
                    }
                  >
                    {applyMut.isPending ? "מייבא..." : "אשר וייבא"}
                  </button>
                )}
                {canImport && preview.applyable === false && (
                  <button className="btn opacity-60 cursor-not-allowed bg-slate-200 text-slate-600"
                          disabled>
                    פורמט לא נתמך
                  </button>
                )}
              </div>
              {applyMut.isError && (
                <div className="mt-3 text-sm text-red-700">
                  שגיאה: {(applyMut.error as Error)?.message}
                </div>
              )}
            </>
          )}
        </Step>
      )}
    </div>
  );
}


/** Banner shown for non-template (ICL / Eli Line / unknown) uploads. */
function FormatBanner({ preview }: { preview: ImportPreview }) {
  const fmt = preview.format;
  const info = preview.format_info || {};
  const provider = info.source_provider || fmt;
  const tone = preview.applyable
    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
    : fmt === "unknown"
      ? "border-red-200 bg-red-50 text-red-900"
      : "border-amber-200 bg-amber-50 text-amber-900";
  return (
    <div className={clsx("rounded-lg border p-3 mb-3 text-sm", tone)}>
      <div className="font-semibold">
        ⓘ פורמט מזוהה: {provider}
      </div>
      {info.notes && <div className="text-xs mt-1">{info.notes}</div>}
      {info.sheet_name && (
        <div className="text-xs mt-0.5">
          גיליון: <code>{info.sheet_name}</code>
          {info.header_row && <> · שורת כותרת: {info.header_row}</>}
        </div>
      )}
      {preview.applyable === false && fmt !== "unknown" && (
        <div className="text-xs mt-2">
          ⚠ זוהי תצוגה מקדימה בלבד. נתיב יבוא ייעודי לפורמט {provider} יבנה
          רק לאחר שתאשר את התצוגה. עד אז שום שורה לא תיכנס למסד.
        </div>
      )}
    </div>
  );
}


/**
 * External-format row list (ICL / Eli Line). Each row is a card with the
 * full set of fields the parser produced — way too many for a flat table.
 */
function ExternalRowList({
  rows, format, actions, setAction, forceCreate, setForceCreate,
}: {
  rows: any[];
  format: string;
  actions: Record<string, "create" | "update" | "skip">;
  setAction: (key: string, action: "create" | "update" | "skip") => void;
  forceCreate: Record<string, boolean>;
  setForceCreate: (key: string, value: boolean) => void;
}) {
  return (
    <div className="space-y-2 mb-4">
      {rows.map((r) => {
        const key = String(r.source_row_number ?? r._row);
        return (
          <ExternalRowCard
            key={key}
            row={r}
            format={format}
            action={actions[key] || "skip"}
            setAction={(a) => setAction(key, a)}
            forceCreate={!!forceCreate[key]}
            setForceCreate={(v) => setForceCreate(key, v)}
          />
        );
      })}
    </div>
  );
}


function ExternalRowCard({
  row: r, format, action, setAction, forceCreate, setForceCreate,
}: {
  row: any; format: string;
  action: "create" | "update" | "skip";
  setAction: (a: "create" | "update" | "skip") => void;
  forceCreate: boolean;
  setForceCreate: (v: boolean) => void;
}) {
  const needsReview = !!r.needs_review;
  const match = r._match;
  const matchLevel: string = r.match_level || "no_match";
  const possibleMatches = (r.possible_matches || []) as any[];
  const isUnsafeCreate = (matchLevel === "exact_duplicate" || matchLevel === "strong_possible_match")
                          && action === "create";
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [showAllMatches, setShowAllMatches] = useState(false);
  const cardBorder =
    matchLevel === "exact_duplicate"      ? "border-red-300 bg-red-50"
    : matchLevel === "strong_possible_match" ? "border-orange-300 bg-orange-50"
    : matchLevel === "soft_possible_match"   ? "border-yellow-300 bg-yellow-50"
    : needsReview                            ? "border-amber-300 bg-amber-50"
    : "border-slate-200 bg-white";

  return (
    <div className={clsx("rounded-xl border p-3", cardBorder)}>
      <div className="flex items-start gap-3">
        <div className="text-[10px] text-slate-500 font-mono shrink-0 pt-0.5">
          {r.source_provider || format}<br />
          row {r.source_row_number}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-1">
            <span className="font-semibold text-slate-900">
              {r.shipment_reference || <span className="text-slate-400 italic">—</span>}
            </span>
            {r.shipment_reference_note && (
              <span className="text-[10px] text-slate-500">{r.shipment_reference_note}</span>
            )}
            <span className="text-sm">— {r.supplier_name || "ספק לא ידוע"}</span>
            {r.inferred_brand && (
              <span className="badge-blue text-[10px]" title="הוסק מהטקסט">
                🏷 {r.inferred_brand}
              </span>
            )}
            {r.inferred_category && (
              <span className="badge-gray text-[10px]" title="הוסק מהטקסט">
                {r.inferred_category}
              </span>
            )}
            {needsReview && (
              <span className="badge-amber text-[10px]">דורש בדיקה</span>
            )}
            {match && (
              <span className="badge-blue text-[10px]">
                ↺ קיים: {match.shp_id} (לפי {match.matched_by})
              </span>
            )}
            {r.shipment_status && (
              <span className="text-[10px] text-slate-600">סטטוס: {r.shipment_status}</span>
            )}
          </div>

          {r.product_description && (
            <div className="text-sm text-slate-700 mb-1">{r.product_description}</div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-3 gap-y-0.5 text-[11px] text-slate-700">
            {r.origin_port && <Kv k="מקור" v={r.origin_port} />}
            {r.destination_port && <Kv k="יעד" v={r.destination_port} />}
            {r.vessel_name && <Kv k="אוניה" v={r.vessel_name} />}
            {r.incoterm && <Kv k="Incoterm" v={r.incoterm} />}
            {r.carrier && <Kv k="מוביל" v={r.carrier} />}
            {r.etd && <Kv k="ETD" v={r.etd} />}
            {r.eta_port && <Kv k="ETA נמל" v={r.eta_port} />}
            {r.purchase_order_number && <Kv k="PO" v={String(r.purchase_order_number)} />}
            {r.house_bill_of_lading_number && (
              <Kv k="HBL" v={r.house_bill_of_lading_number} />
            )}
            {r.master_bill_of_lading_number && (
              <Kv k="MBL" v={r.master_bill_of_lading_number} />
            )}
            {r.external_job_number && <Kv k="JOB" v={r.external_job_number} />}
            {r.marks && <Kv k="MARKS" v={r.marks} />}
            {r.sho_list && <Kv k="Sho" v={r.sho_list} />}
            {r.customs_file_number && <Kv k="Customs" v={r.customs_file_number} />}
            {(r.container_quantity != null || r.container_type) && (
              <Kv k="מכולות"
                  v={[
                    r.container_quantity != null ? `${r.container_quantity}` : null,
                    r.container_type,
                  ].filter(Boolean).join(" × ")}
                  hint={r.container_raw && r.container_raw !== r.container_quantity
                        ? `raw: ${r.container_raw}` : undefined}
              />
            )}
            {r.cbm_raw && <Kv k="CBM" v={r.cbm_raw} />}
            {r.container_quantity_confidence && r.container_quantity_confidence !== "exact" && (
              <Kv k="דיוק כמות" v={r.container_quantity_confidence} />
            )}
          </div>

          {r.review_reasons && r.review_reasons.length > 0 && (
            <ul className="text-[11px] text-amber-900 mt-2 ml-4 list-disc">
              {r.review_reasons.map((reason: string, i: number) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          )}

          {/* === Match / similarity warning === */}
          {matchLevel !== "no_match" && (
            <div className="mt-2 pt-2 border-t border-slate-200/60">
              <MatchBadge
                level={matchLevel}
                score={r.match_score || 0}
                ref={r.matched_shipment_reference}
                supplier={r.matched_shipment_supplier}
                reasons={r.match_reasons || []}
              />
              {possibleMatches.length > 1 && (
                <button
                  onClick={() => setShowAllMatches((v) => !v)}
                  className="text-[10px] text-slate-600 hover:text-slate-900 mt-1 underline"
                >
                  {showAllMatches
                    ? "סגור רשימה"
                    : `${possibleMatches.length} התאמות אפשריות — הצג הכל`}
                </button>
              )}
              {showAllMatches && (
                <div className="mt-2 space-y-1 text-[11px]">
                  {possibleMatches.map((pm) => (
                    <div key={pm.shipment_id} className="rounded border border-slate-200 bg-white p-2">
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <span className="font-mono font-medium">{pm.shipment_reference}</span>
                        <span className="text-slate-700">{pm.supplier_name || "—"}</span>
                        <span className="text-slate-500">
                          score: <b>{pm.match_score}</b>
                        </span>
                        {pm.eta_port && <span className="text-slate-500">ETA: {pm.eta_port}</span>}
                      </div>
                      <div className="text-slate-600 mt-1">
                        {(pm.match_reasons || []).slice(0, 4).join(" · ")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* === Per-row action selector === */}
          <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-500">פעולה:</span>
            <select
              className="input text-xs py-1 w-auto"
              value={action}
              onChange={(e) => {
                const newAction = e.target.value as any;
                setAction(newAction);
                // If they leave create-mode, reset the override
                if (newAction !== "create") setForceCreate(false);
                // If they pick create on a strong/exact match, demand confirmation
                if (newAction === "create"
                    && (matchLevel === "exact_duplicate"
                        || matchLevel === "strong_possible_match")
                    && !forceCreate) {
                  setConfirmModalOpen(true);
                }
              }}
            >
              <option value="create">צור חדש</option>
              {r.matched_shipment_reference && (
                <option value="update">עדכן את {r.matched_shipment_reference}</option>
              )}
              <option value="skip">דלג</option>
            </select>

            {needsReview && action !== "skip" && (
              <span className="text-[10px] text-amber-800">
                ⚠ שורה סומנה "דורש בדיקה" — בחירת {action} תנצח את ברירת המחדל
              </span>
            )}
            {isUnsafeCreate && forceCreate && (
              <span className="text-[10px] text-red-700 font-semibold">
                🛑 CREATE ANYWAY — תיווצר רשומה כפולה במודע
              </span>
            )}
            {isUnsafeCreate && !forceCreate && (
              <button
                onClick={() => setConfirmModalOpen(true)}
                className="text-[10px] text-red-700 underline"
              >
                ⚠ נדרש אישור CREATE ANYWAY
              </button>
            )}
          </div>
        </div>
      </div>

      {/* === Force-create confirmation modal === */}
      {confirmModalOpen && (
        <ForceCreateModal
          row={r}
          onConfirm={() => {
            setForceCreate(true);
            setConfirmModalOpen(false);
          }}
          onCancel={() => {
            setForceCreate(false);
            setAction("skip");          // bounce back to safe default
            setConfirmModalOpen(false);
          }}
        />
      )}
    </div>
  );
}


function MatchBadge({
  level, score, ref, supplier, reasons,
}: {
  level: string;
  score: number;
  ref: string | null;
  supplier: string | null;
  reasons: string[];
}) {
  const badge = {
    exact_duplicate:        { color: "bg-red-100 text-red-800 border-red-300",        text: "🛑 כפילות מדויקת" },
    strong_possible_match:  { color: "bg-orange-100 text-orange-800 border-orange-300", text: "⚠ התאמה אפשרית חזקה" },
    soft_possible_match:    { color: "bg-yellow-100 text-yellow-800 border-yellow-300", text: "⚠ התאמה אפשרית רכה" },
    no_match:               { color: "bg-slate-100 text-slate-700 border-slate-200",   text: "—" },
  }[level] || { color: "bg-slate-100 text-slate-700 border-slate-200", text: level };

  return (
    <div className="text-[11px]">
      <div className="flex items-center gap-2 flex-wrap">
        <span className={clsx("px-2 py-0.5 rounded-md border font-semibold", badge.color)}>
          {badge.text} ({score})
        </span>
        {ref && (
          <span className="text-slate-700">
            ייתכן שכבר קיים: <b>{ref}</b>
            {supplier && <> · {supplier}</>}
          </span>
        )}
      </div>
      {reasons.length > 0 && (
        <div className="text-slate-700 mt-1">
          <span className="text-slate-500">סיבות: </span>
          {reasons.slice(0, 4).join(" · ")}
        </div>
      )}
    </div>
  );
}


function ForceCreateModal({
  row, onConfirm, onCancel,
}: {
  row: any;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const ok = text === "CREATE ANYWAY";
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
         onClick={onCancel}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col"
           onClick={(e) => e.stopPropagation()}>
        <header className="px-5 py-3 border-b border-slate-200">
          <div className="font-semibold text-slate-900">⚠ אישור יצירה כפולה</div>
        </header>
        <div className="p-5 space-y-3 text-sm">
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-900">
            השורה הזו מתאימה לכפילות
            <span className="font-semibold"> {row.match_level === "exact_duplicate" ? "מדויקת" : "חזקה"} </span>
            עם <b>{row.matched_shipment_reference}</b>
            {row.matched_shipment_supplier && <> · {row.matched_shipment_supplier}</>}
            (score {row.match_score}/100).
          </div>
          {row.match_reasons && row.match_reasons.length > 0 && (
            <ul className="text-xs text-slate-700 space-y-0.5 ml-4 list-disc">
              {row.match_reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}
            </ul>
          )}
          <div className="text-xs text-slate-700">
            כדי בכל זאת ליצור רשומה חדשה, הקלד <code>CREATE ANYWAY</code> כאן:
          </div>
          <input
            className="input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="CREATE ANYWAY"
          />
        </div>
        <footer className="px-5 py-3 border-t border-slate-200 flex justify-end gap-2">
          <button onClick={onCancel} className="btn-secondary">ביטול — חזור ל-skip</button>
          <button
            onClick={onConfirm}
            disabled={!ok}
            className={clsx(
              "btn",
              ok
                ? "bg-red-600 text-white hover:bg-red-700"
                : "bg-slate-200 text-slate-500 cursor-not-allowed",
            )}
          >
            אשר יצירה כפולה
          </button>
        </footer>
      </div>
    </div>
  );
}


function Kv({ k, v, hint }: { k: string; v: string | number; hint?: string }) {
  return (
    <div className="truncate" title={hint}>
      <span className="text-slate-500">{k}:</span>{" "}
      <span className="text-slate-800">{v}</span>
    </div>
  );
}

function PreviewRow({
  row, action, setAction,
}: {
  row: ImportPreviewRow;
  action: "create" | "update" | "skip";
  setAction: (a: "create" | "update" | "skip") => void;
}) {
  const hasErrors = row._errors.length > 0;
  const matchInfo = row._match;

  return (
    <tr className={clsx(
      hasErrors && "bg-red-50",
      !hasErrors && matchInfo && "bg-blue-50",
    )}>
      <td className="py-2 px-2 text-slate-500">{row._row}</td>
      <td className="py-2 px-2 font-mono">
        {row.shipment_reference || <span className="text-slate-400 italic">חדש</span>}
      </td>
      <td className="py-2 px-2 truncate max-w-[150px]">{row.supplier_name || "—"}</td>
      <td className="py-2 px-2 font-mono text-[10px]">{row.container_number || "—"}</td>
      <td className="py-2 px-2 font-mono text-[10px]">{row.bill_of_lading_number || "—"}</td>
      <td className="py-2 px-2">{row.purchase_order_number || "—"}</td>
      <td className="py-2 px-2">{row.eta_warehouse || row.eta_port || row.etd || "—"}</td>
      <td className="py-2 px-2 tabular-nums">{row.number_of_cartons || "—"}</td>
      <td className="py-2 px-2 tabular-nums">{row.cbm || "—"}</td>
      <td className="py-2 px-2 truncate max-w-[200px]" title={row.notes || ""}>
        {row.notes || "—"}
      </td>
      <td className="py-2 px-2">
        {hasErrors ? (
          <div>
            <span className="badge-red text-[10px]">שגיאה</span>
            <div className="text-[10px] text-red-700 mt-1">
              {row._errors.slice(0, 2).join("; ")}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {matchInfo && (
              <div className="text-[10px] text-blue-700">
                ↺ קיים: {matchInfo.shp_id}
                <div className="text-slate-500">לפי {matchInfo.matched_by}</div>
              </div>
            )}
            <select
              className="input text-xs py-1"
              value={action}
              onChange={(e) => setAction(e.target.value as any)}
            >
              {!matchInfo && <option value="create">צור חדש</option>}
              {matchInfo && <option value="update">עדכן קיים</option>}
              <option value="skip">דלג</option>
            </select>
          </div>
        )}
      </td>
    </tr>
  );
}

function Step({ n, title, children }: {
  n: number; title: string; children: React.ReactNode;
}) {
  return (
    <section className="bg-white border border-slate-200 rounded-2xl p-5 mb-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-7 h-7 rounded-full bg-brand-500 text-white flex items-center justify-center text-sm font-semibold">
          {n}
        </div>
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function SummaryTile({
  label, value, tone = "default",
}: { label: string; value: number;
     tone?: "default" | "success" | "info" | "danger" | "warning" | "caution" }) {
  const cls = {
    default: "border-slate-200",
    success: "border-emerald-200 bg-emerald-50",
    info:    "border-blue-200 bg-blue-50",
    danger:  "border-red-200 bg-red-50",
    warning: "border-amber-300 bg-amber-50",
    caution: "border-yellow-200 bg-yellow-50",
  }[tone];
  return (
    <div className={clsx("rounded-lg border p-2 text-center", cls)}>
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
