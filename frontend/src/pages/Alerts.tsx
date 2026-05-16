import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listAlerts, resolveAlert, scanAlerts } from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState } from "../components/common";
import { fmtDateTime, severityColor } from "../utils/format";

export default function Alerts() {
  const [showResolved, setShowResolved] = useState(false);
  const params: Record<string, any> = {};
  if (!showResolved) params.resolved = false;

  const q = useQuery({
    queryKey: ["alerts", params],
    queryFn: () => listAlerts(params),
  });
  const qc = useQueryClient();
  const resolve = useMutation({
    mutationFn: (id: number) => resolveAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
  const scan = useMutation({
    mutationFn: () => scanAlerts(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  return (
    <div>
      <PageHeader
        title="התראות"
        subtitle="התראות פעילות במערכת"
        actions={
          <>
            <button className="btn-secondary" onClick={() => scan.mutate()} disabled={scan.isPending}>
              {scan.isPending ? "סורק..." : "סרוק עכשיו"}
            </button>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
              הצג גם טופלו
            </label>
          </>
        }
      />

      {q.isLoading ? <Loader /> :
       q.isError ? <ErrorState error={q.error} /> :
       !q.data || q.data.length === 0 ? <EmptyState title="אין התראות" icon="✅" /> :
       <ul className="space-y-2">
         {q.data.map((a) => (
           <li key={a.id} className="card flex items-center justify-between">
             <div>
               <div className="flex items-center gap-2">
                 <span className={severityColor(a.severity)}>{a.severity}</span>
                 <span className="font-semibold">{a.title}</span>
                 {a.shp_id && <span className="badge-blue">{a.shp_id}</span>}
               </div>
               {a.description && <div className="text-sm text-slate-600 mt-1">{a.description}</div>}
               <div className="text-xs text-slate-400 mt-1">
                 {fmtDateTime(a.created_at)}
                 {a.resolved && <> • טופל ע"י {a.resolved_by}</>}
               </div>
             </div>
             {!a.resolved && (
               <button className="btn-secondary" onClick={() => resolve.mutate(a.id)} disabled={resolve.isPending}>
                 טופל
               </button>
             )}
           </li>
         ))}
       </ul>}
    </div>
  );
}
