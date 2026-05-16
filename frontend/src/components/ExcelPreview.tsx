import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { excelPreview } from "../api/endpoints";
import type { ExcelPreviewData, ExcelSheet } from "../api/endpoints";
import { downloadDocument } from "../utils/fileAccess";
import { Loader, ErrorState } from "./common";
import clsx from "clsx";

/**
 * Inline Excel viewer — opens in a modal.
 *
 * Renders sheets as tabs and shows the cells in a sticky-header table.
 * Caps at 200 rows × 30 cols (server-side enforcement). Always shows
 * a "Download original" link so the user can open the full file in Excel.
 */
export default function ExcelPreviewModal({
  docId, filename, onClose,
}: {
  docId: number;
  filename?: string | null;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ["excel-preview", docId],
    queryFn: () => excelPreview(docId),
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
          <div className="min-w-0">
            <div className="font-semibold text-slate-900 truncate">
              📊 {filename || "Excel preview"}
            </div>
            <div className="text-xs text-slate-500">
              תצוגה מקדימה בלבד — הקובץ המקורי זמין להורדה
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              className="btn-primary"
              onClick={() => downloadDocument(docId, filename || undefined)}
            >
              הורד מקור
            </button>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl px-2">
              ✕
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-hidden">
          {q.isLoading ? <Loader /> :
           q.isError ? <ErrorState error={q.error} /> :
           q.data ? <SheetView data={q.data} /> : null}
        </div>
      </div>
    </div>
  );
}

function SheetView({ data }: { data: ExcelPreviewData }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const sheets = data.sheets || [];

  if (data.error) {
    return (
      <div className="p-6">
        <div className="card border-amber-300 bg-amber-50">
          <div className="font-semibold text-amber-900">לא ניתן להציג את הקובץ</div>
          <div className="text-sm text-amber-800 mt-2">{data.error}</div>
        </div>
      </div>
    );
  }
  if (sheets.length === 0) {
    return <div className="p-6 text-sm text-slate-500">הקובץ ריק.</div>;
  }

  const active = sheets[activeIdx];

  return (
    <div className="flex flex-col h-full">
      {/* Sheet tabs */}
      {sheets.length > 1 && (
        <div className="flex gap-1 border-b border-slate-200 px-3 pt-2 overflow-x-auto">
          {sheets.map((s, i) => (
            <button
              key={s.name + i}
              onClick={() => setActiveIdx(i)}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-t-lg whitespace-nowrap",
                i === activeIdx
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200 border-b-white"
                  : "text-slate-600 hover:bg-slate-50",
              )}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* Stats line */}
      <div className="px-5 pt-2 pb-2 text-xs text-slate-500">
        {active.row_count.toLocaleString("he-IL")} שורות × {active.col_count} עמודות
        {active.truncated && (
          <span className="badge-amber mr-2 text-[10px]">
            מציג עד 200×30 — הקובץ ארוך יותר
          </span>
        )}
      </div>

      {/* Sheet table */}
      <div className="flex-1 overflow-auto px-5 pb-5">
        <ExcelTable sheet={active} />
      </div>
    </div>
  );
}

function ExcelTable({ sheet }: { sheet: ExcelSheet }) {
  if (!sheet.rows || sheet.rows.length === 0) {
    return <div className="text-sm text-slate-500 py-4">דף ריק</div>;
  }

  const colCount = Math.max(...sheet.rows.map((r) => r.length));

  // Excel-style column letters: A, B, ..., Z, AA, AB, ...
  function colLetter(n: number): string {
    let s = "";
    while (n >= 0) {
      s = String.fromCharCode(65 + (n % 26)) + s;
      n = Math.floor(n / 26) - 1;
    }
    return s;
  }

  return (
    <table className="border-collapse text-xs" dir="ltr">
      <thead className="sticky top-0 bg-slate-100 z-10">
        <tr>
          <th className="border border-slate-300 bg-slate-200 w-10 px-2 py-1 sticky right-0 left-0"></th>
          {Array.from({ length: colCount }).map((_, i) => (
            <th
              key={i}
              className="border border-slate-300 bg-slate-200 px-2 py-1 text-center font-semibold text-slate-600 min-w-[80px]"
            >
              {colLetter(i)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sheet.rows.map((row, rIdx) => (
          <tr key={rIdx} className={rIdx === 0 ? "font-semibold bg-slate-50" : ""}>
            <td className="border border-slate-300 bg-slate-100 text-center text-slate-500 sticky right-0 left-0 px-2 py-1">
              {rIdx + 1}
            </td>
            {Array.from({ length: colCount }).map((_, cIdx) => {
              const v = row[cIdx];
              return (
                <td
                  key={cIdx}
                  className="border border-slate-200 px-2 py-1 align-top max-w-[300px] overflow-hidden text-ellipsis whitespace-nowrap"
                  title={v != null ? String(v) : ""}
                >
                  {v != null ? String(v) : ""}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
