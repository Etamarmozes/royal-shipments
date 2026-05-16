import { useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  receivingQueue, getReceivingView, receiveContainer,
} from "../api/endpoints";
import { downloadDocument } from "../utils/fileAccess";
import AuthedImage from "../components/AuthedImage";
import { PageHeader, Loader, EmptyState } from "../components/common";
import AIPanel from "../components/AIPanel";
import { fmtDate, fmtNumber } from "../utils/format";
import clsx from "clsx";

const DOC_LABEL: Record<string, string> = {
  packing_list: "Packing List",
  invoice: "Invoice",
  bl: "BL",
  bol: "BOL",
  booking_confirmation: "Booking",
  customs: "Customs",
  other: "אחר",
};

/**
 * Warehouse Receiving Mode.
 *
 * Two views:
 *  - Queue: list of containers expected to arrive (sorted by ETA)
 *  - Detail: open one container, see all info + documents + receiving form
 *
 * Drives via ?container=<id> query param.
 */
export default function Receiving() {
  const [searchParams, setSearchParams] = useSearchParams();
  const containerId = searchParams.get("container");

  if (containerId) {
    return <ReceivingDetail
      containerId={Number(containerId)}
      onBack={() => setSearchParams({})}
    />;
  }
  return <ReceivingQueue onOpen={(id) => setSearchParams({ container: String(id) })} />;
}

function ReceivingQueue({ onOpen }: { onOpen: (id: number) => void }) {
  const q = useQuery({ queryKey: ["receiving-queue"], queryFn: receivingQueue });

  return (
    <div className="max-w-5xl mx-auto pb-12">
      <PageHeader
        title="קבלת סחורה"
        subtitle="מכולות שצפויות להגיע למחסן. לחץ על שורה לפתיחת מסך קבלה."
      />

      {q.isLoading ? <Loader /> :
       !q.data || q.data.length === 0 ? (
         <EmptyState title="אין מכולות בתור קליטה" icon="📥" />
       ) : (
         <div className="space-y-2">
           {q.data.map((c: any) => (
             <button
               key={c.id}
               onClick={() => onOpen(c.id)}
               className="w-full text-right card hover:shadow-md active:bg-slate-50 transition"
             >
               {/* Header row: container + supplier */}
               <div className="flex items-start gap-3 mb-3">
                 <div className="w-11 h-11 rounded-lg bg-slate-100 flex items-center justify-center text-xl shrink-0">
                   🚢
                 </div>
                 <div className="flex-1 min-w-0">
                   <div className="font-mono font-semibold text-base truncate">{c.container_number}</div>
                   <div className="text-xs text-slate-500 truncate">
                     {c.shipment_shp_id} • {c.supplier}
                   </div>
                 </div>
                 <ReceivingStatusBadge status={c.receiving_status} />
               </div>
               {/* Stats grid — stacks nicely on mobile, 4 columns on tablet+ */}
               <div className="grid grid-cols-4 gap-2 text-xs">
                 <ReceivingStat label="ETA" value={fmtDate(c.eta_for_warehouse)} highlight />
                 <ReceivingStat label="קרטונים" value={c.boxes_total ?? "—"} />
                 <ReceivingStat label="משטחים" value={c.estimated_pallets_final ?? "—"} />
                 <ReceivingStat label="מסמכים" value={c.documents_count ?? 0} />
               </div>
             </button>
           ))}
         </div>
       )}
    </div>
  );
}

function ReceivingDetail({ containerId, onBack }: { containerId: number; onBack: () => void }) {
  const qc = useQueryClient();
  const view = useQuery({
    queryKey: ["receiving-view", containerId],
    queryFn: () => getReceivingView(containerId),
  });
  const data = view.data;

  const [cartons, setCartons] = useState<string>("");
  const [pallets, setPallets] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [receivedBy, setReceivedBy] = useState("warehouse");
  const submit = useMutation({
    mutationFn: () => receiveContainer(containerId, {
      received_cartons_actual: cartons ? Number(cartons) : undefined,
      received_pallets_actual: pallets ? Number(pallets) : undefined,
      received_notes: notes || undefined,
      received_by: receivedBy,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["receiving-view", containerId] });
      qc.invalidateQueries({ queryKey: ["receiving-queue"] });
    },
  });

  if (view.isLoading) return <Loader />;
  if (!data) return null;

  const expectedCartons = data.boxes_total;
  const expectedPallets = data.estimated_pallets_final;

  return (
    <div className="max-w-5xl mx-auto pb-12">
      <PageHeader
        title={`קליטת מכולה ${data.container_number}`}
        subtitle={`${data.shipment_shp_id} • ${data.supplier || ""}`}
        actions={<button className="btn-secondary" onClick={onBack}>← לתור הקליטה</button>}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Expected */}
        <div className="card">
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">צפוי</div>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between"><span>קרטונים:</span><span className="font-semibold tabular-nums">{fmtNumber(expectedCartons)}</span></div>
            <div className="flex justify-between"><span>משטחים:</span><span className="font-semibold tabular-nums">{fmtNumber(expectedPallets)}</span></div>
            <div className="flex justify-between"><span>CBM:</span><span className="font-semibold tabular-nums">{data.cbm ?? "—"}</span></div>
            <div className="flex justify-between"><span>משקל:</span><span className="font-semibold tabular-nums">{fmtNumber(data.gross_weight_kg)} ק״ג</span></div>
            <div className="flex justify-between"><span>קטגוריה:</span><span>{data.shipment_category || "—"}</span></div>
            <div className="flex justify-between"><span>סוג:</span><span>{data.container_type || "—"}</span></div>
          </div>
        </div>

        {/* Product image */}
        <div className="card">
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">תמונת מוצר</div>
          {data.shipment_product_image_path ? (
            <AuthedImage
              path={`/shipments/${data.shipment_id}/product-image`}
              alt=""
              className="w-full h-40 object-cover rounded-lg"
            />
          ) : (
            <div className="h-40 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400 text-sm">
              אין תמונה
            </div>
          )}
        </div>

        {/* Status */}
        <div className="card">
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">סטטוס</div>
          <div className="text-2xl font-semibold mb-2">
            <ReceivingStatusBadge status={data.receiving_status} />
          </div>
          {data.received_at && (
            <div className="text-xs text-slate-500">
              נקלטה ב-{fmtDate(data.received_at)} ע״י {data.received_by}
            </div>
          )}
          <div className="mt-3 text-sm">
            <div><span className="text-slate-500">תיאור:</span> {data.shipment_goods || "—"}</div>
          </div>
        </div>
      </div>

      {/* Documents */}
      <Section title="מסמכי קבלה">
        {(!data.documents || data.documents.length === 0) ? (
          <div className="text-sm text-slate-500">אין מסמכים מקושרים — ניתן לראות במסך "מסמכי מקור"</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.documents.map((d: any) => (
              <button
                key={d.id}
                onClick={() => downloadDocument(d.id, d.filename)}
                className="text-right rounded-xl border border-slate-200 p-3 hover:bg-slate-50 flex items-start gap-3"
              >
                <span className="text-2xl">📄</span>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{d.filename}</div>
                  <div className="text-xs text-slate-500">
                    <span className="badge-blue">{DOC_LABEL[d.document_type] || d.document_type}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* Warehouse AI panel */}
      <Section title="🧰 שאל את עוזר המחסן">
        <p className="text-xs text-slate-500 -mt-1 mb-2">
          קבל תשובה מתוך הנתונים במערכת. ה-AI מכיר את המכולה הזאת.
        </p>
        <AIPanel
          context={{ container_id: containerId, page: "receiving" }}
          compact
          placeholder="לדוגמה: מה אמור להגיע פה?"
        />
      </Section>

      {/* Receiving form */}
      <Section title="קליטה בפועל">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field
            label="קרטונים שהתקבלו"
            value={cartons}
            onChange={setCartons}
            type="number"
            placeholder={String(expectedCartons || "")}
            expected={expectedCartons}
            actual={cartons ? Number(cartons) : null}
          />
          <Field
            label="משטחים שהתקבלו"
            value={pallets}
            onChange={setPallets}
            type="number"
            placeholder={String(expectedPallets || "")}
            expected={expectedPallets}
            actual={pallets ? Number(pallets) : null}
          />
          <div className="md:col-span-2">
            <label className="label">הערות קליטה</label>
            <textarea
              className="input"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="פערים / חריגים / תקלות"
            />
          </div>
          <div>
            <label className="label">נקלט ע״י</label>
            <input className="input" value={receivedBy} onChange={(e) => setReceivedBy(e.target.value)} />
          </div>
        </div>

        {submit.isError && (
          <div className="mt-3 text-sm text-red-700">שגיאה בקליטה</div>
        )}
        {submit.isSuccess && submit.data && (
          <div className="mt-3 text-sm text-emerald-700">
            ✓ נקלט בסטטוס: {submit.data.receiving_status}
          </div>
        )}

        <div className="mt-4 flex gap-2 justify-end">
          <button
            className="btn-primary"
            onClick={() => submit.mutate()}
            disabled={submit.isPending || (!cartons && !pallets)}
          >
            {submit.isPending ? "קולט..." : "אשר קבלה"}
          </button>
        </div>
      </Section>
    </div>
  );
}

function Field({
  label, value, onChange, type = "text", placeholder, expected, actual,
}: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; expected?: number | null; actual?: number | null;
}) {
  const diff = expected != null && actual != null ? actual - expected : null;
  return (
    <div>
      <label className="label">{label}</label>
      <input
        type={type} className="input"
        value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      {expected != null && (
        <div className="mt-1 text-xs text-slate-500">
          צפוי: <b>{fmtNumber(expected)}</b>
          {diff !== null && diff !== 0 && (
            <span className={clsx("mr-2", Math.abs(diff) > 1 ? "text-red-600" : "text-amber-700")}>
              ← פער {diff > 0 ? "+" : ""}{diff}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ReceivingStatusBadge({ status }: { status?: string | null }) {
  const map: Record<string, { label: string; cls: string }> = {
    not_received: { label: "ממתין", cls: "badge-gray" },
    partially_received: { label: "התקבל חלקית", cls: "badge-amber" },
    received: { label: "נקלט", cls: "badge-green" },
    discrepancy: { label: "פער", cls: "badge-red" },
  };
  const k = status || "not_received";
  const v = map[k] || { label: k, cls: "badge-gray" };
  return <span className={v.cls}>{v.label}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 mb-5">
      <h2 className="text-lg font-semibold text-slate-900 mb-3">{title}</h2>
      {children}
    </section>
  );
}

function ReceivingStat({ label, value, highlight }: {
  label: string; value: any; highlight?: boolean;
}) {
  return (
    <div className={clsx(
      "rounded-lg p-2 text-center",
      highlight ? "bg-blue-50" : "bg-slate-50"
    )}>
      <div className="text-[10px] text-slate-500 leading-none mb-1">{label}</div>
      <div className={clsx(
        "text-sm tabular-nums",
        highlight ? "font-semibold text-blue-700" : "font-medium text-slate-800"
      )}>
        {value}
      </div>
    </div>
  );
}
