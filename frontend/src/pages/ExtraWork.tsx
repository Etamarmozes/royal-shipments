import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listExtraWork, completeExtraWork, updateExtraWork } from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState } from "../components/common";
import { fmtDate } from "../utils/format";

const STATUS_OPTIONS = [
  "לא התחיל", "ממתין לסחורה", "ממתין לגורם אריזה", "בעבודה",
  "ממתין לאישור", "הסתיים", "מתעכב", "בוטל",
];

export default function ExtraWork() {
  const [openOnly, setOpenOnly] = useState(true);
  const [delayedOnly, setDelayedOnly] = useState(false);
  const params: Record<string, any> = {};
  if (openOnly) params.open_only = true;
  if (delayedOnly) params.delayed_only = true;

  const q = useQuery({
    queryKey: ["extra-work", params],
    queryFn: () => listExtraWork(params),
  });
  const qc = useQueryClient();
  const complete = useMutation({
    mutationFn: (id: number) => completeExtraWork(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["extra-work"] }),
  });

  return (
    <div>
      <PageHeader
        title="תוספות עבודה"
        subtitle="משימות שמתבצעות אחרי הגעה למחסן ולפני חלוקה לסניפים"
      />

      <div className="card mb-4 flex flex-wrap gap-4">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} />
          <span className="text-sm">פתוחות בלבד</span>
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={delayedOnly} onChange={(e) => setDelayedOnly(e.target.checked)} />
          <span className="text-sm">מתעכבות בלבד</span>
        </label>
      </div>

      {q.isLoading ? <Loader /> : q.isError ? <ErrorState error={q.error} /> :
       !q.data || q.data.length === 0 ? <EmptyState title="אין משימות תואמות" icon="🛠️" /> :
       <div className="card overflow-x-auto">
         <table className="min-w-full text-sm">
           <thead>
             <tr className="text-slate-500 text-xs">
               <th className="text-right py-2 px-2">SHP</th>
               <th className="text-right py-2 px-2">ספק</th>
               <th className="text-right py-2 px-2">מכולה</th>
               <th className="text-right py-2 px-2">סוג עבודה</th>
               <th className="text-right py-2 px-2">אחראי</th>
               <th className="text-right py-2 px-2">סטטוס</th>
               <th className="text-right py-2 px-2">סיום צפוי</th>
               <th className="text-right py-2 px-2">סיום בפועל</th>
               <th className="text-right py-2 px-2">מוכן להפצה</th>
               <th className="text-right py-2 px-2">עיכוב</th>
               <th></th>
             </tr>
           </thead>
           <tbody>
             {q.data.map((t) => (
               <tr key={t.id} className="border-t border-slate-100">
                 <td className="py-2 px-2">{t.shp_id}</td>
                 <td className="py-2 px-2">{t.supplier}</td>
                 <td className="py-2 px-2 font-mono">{t.container_number || "—"}</td>
                 <td className="py-2 px-2">{t.work_type}</td>
                 <td className="py-2 px-2">{t.responsible_party || "—"}</td>
                 <td className="py-2 px-2">
                   <span className={t.work_status === "מתעכב" ? "badge-red" : "badge-blue"}>{t.work_status}</span>
                 </td>
                 <td className="py-2 px-2">{fmtDate(t.expected_end_date)}</td>
                 <td className="py-2 px-2">{fmtDate(t.actual_end_date)}</td>
                 <td className="py-2 px-2">{fmtDate(t.ready_for_distribution_estimated_date)}</td>
                 <td className="py-2 px-2">{t.delay_status ? <span className="badge-red">כן</span> : "—"}</td>
                 <td className="py-2 px-2">
                   {t.work_status !== "הסתיים" && (
                     <button className="btn-secondary text-xs" onClick={() => complete.mutate(t.id)}>סיים</button>
                   )}
                 </td>
               </tr>
             ))}
           </tbody>
         </table>
       </div>}
    </div>
  );
}
