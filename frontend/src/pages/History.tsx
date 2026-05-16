import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listShipments } from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState } from "../components/common";
import { fmtDate, fmtDateTime } from "../utils/format";

export default function History() {
  const q = useQuery({
    queryKey: ["shipments-archived"],
    queryFn: () => listShipments({ archived: true, limit: 500 }),
  });

  return (
    <div>
      <PageHeader title="היסטוריה" subtitle="משלוחים שהסתיימו ועברו לארכיון" />

      {q.isLoading ? <Loader /> :
       q.isError ? <ErrorState error={q.error} /> :
       !q.data || q.data.items.length === 0 ?
         <EmptyState title="אין משלוחים בארכיון" icon="🗂️" /> :
       <div className="card overflow-x-auto">
         <table className="min-w-full text-sm">
           <thead>
             <tr className="text-slate-500 text-xs">
               <th className="text-right py-2 px-2">SHP</th>
               <th className="text-right py-2 px-2">ספק</th>
               <th className="text-right py-2 px-2">תיאור</th>
               <th className="text-right py-2 px-2">מקור</th>
               <th className="text-right py-2 px-2">ETA לארץ</th>
               <th className="text-right py-2 px-2">הגעה בפועל</th>
               <th className="text-right py-2 px-2">תוספת עבודה</th>
               <th className="text-right py-2 px-2">הסתיים</th>
             </tr>
           </thead>
           <tbody>
             {q.data.items.map((s) => {
               const delayDays =
                 s.eta_israel && s.actual_arrival_israel
                   ? Math.round((new Date(s.actual_arrival_israel).getTime() - new Date(s.eta_israel).getTime()) / 86400000)
                   : null;
               return (
                 <tr key={s.id} className="border-t border-slate-100">
                   <td className="py-2 px-2 font-semibold">
                     <Link className="text-brand-600" to={`/shipments/${s.id}`}>{s.shp_id}</Link>
                   </td>
                   <td className="py-2 px-2">{s.supplier}</td>
                   <td className="py-2 px-2">{s.goods_description}</td>
                   <td className="py-2 px-2">{s.origin_country}</td>
                   <td className="py-2 px-2">{fmtDate(s.eta_israel)}</td>
                   <td className="py-2 px-2">
                     {fmtDate(s.actual_arrival_israel)}
                     {delayDays !== null && delayDays > 0 && (
                       <span className="badge-red mr-1">+{delayDays} ימים</span>
                     )}
                   </td>
                   <td className="py-2 px-2">{s.extra_work_required ? "כן" : "לא"}</td>
                   <td className="py-2 px-2 text-xs text-slate-500">{fmtDateTime(s.completed_at)}</td>
                 </tr>
               );
             })}
           </tbody>
         </table>
       </div>}
    </div>
  );
}
