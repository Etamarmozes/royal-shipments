import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { PageHeader, Loader, ErrorState } from "../components/common";

/**
 * Renders the SUPPLIER_SHIPMENT_DATA_REQUIREMENTS.md doc inline.
 * No fancy markdown lib — we render with whitespace preserved.
 */
export default function SupplierHelp() {
  const q = useQuery({
    queryKey: ["supplier-help"],
    queryFn: async () => (await api.get("/shipments/help/supplier-doc")).data,
  });

  return (
    <div className="max-w-3xl mx-auto pb-12">
      <PageHeader
        title="מדריך לספקים"
        subtitle="פורמט שליחת מיילים לקליטה אוטומטית במערכת"
      />
      {q.isLoading ? <Loader /> :
       q.isError ? <ErrorState error={q.error} /> :
       q.data ? (
         <article className="bg-white rounded-2xl border border-slate-200 p-6 prose prose-slate prose-sm max-w-none whitespace-pre-wrap leading-relaxed text-slate-800" dir="ltr">
           {q.data.markdown}
         </article>
       ) : null}
    </div>
  );
}
