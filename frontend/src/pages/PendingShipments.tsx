import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listPendingShipments, approvePendingShipment, rejectPendingShipment,
  updatePendingShipment, assignPendingToShipment, listShipments,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState, Section } from "../components/common";
import { fmtDate } from "../utils/format";
import type { PendingShipment } from "../types";

export default function PendingShipments() {
  const q = useQuery({ queryKey: ["pending"], queryFn: () => listPendingShipments("pending") });

  return (
    <div>
      <PageHeader
        title="משלוחים חדשים לאישור"
        subtitle="טיוטות שהמערכת זיהתה ממיילים — מאשרים ופותחים משלוח חדש"
      />

      {q.isLoading ? <Loader /> :
       q.isError ? <ErrorState error={q.error} /> :
       !q.data || q.data.length === 0 ?
         <EmptyState title="אין טיוטות לאישור" description="המערכת לא זיהתה משלוחים חדשים שדורשים את אישורך" icon="✨" /> :
       <ul className="space-y-3">{q.data.map((p) => <PendingRow key={p.id} p={p} />)}</ul>}
    </div>
  );
}

function PendingRow({ p }: { p: PendingShipment }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<PendingShipment>>(p);
  const set = (k: keyof PendingShipment, v: any) => setForm((f) => ({ ...f, [k]: v }));

  const save = useMutation({
    mutationFn: () => updatePendingShipment(p.id, form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pending"] }); setEditing(false); },
  });
  const approve = useMutation({
    mutationFn: () => approvePendingShipment(p.id),
    onSuccess: (s) => { qc.invalidateQueries(); nav(`/shipments/${s.id}`); },
  });
  const reject = useMutation({
    mutationFn: () => rejectPendingShipment(p.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pending"] }),
  });

  return (
    <li className="card">
      <div className="flex justify-between gap-2 items-start">
        <div>
          <div className="text-xs text-slate-500">
            ממייל • {p.sender || "—"} • {fmtDate(p.created_at)}
          </div>
          <div className="font-semibold text-slate-800">{p.subject || p.detected_goods_description || "טיוטה"}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {p.confidence_score !== null && p.confidence_score !== undefined && (
            <span className="badge-purple">ביטחון {Math.round((p.confidence_score || 0) * 100)}%</span>
          )}
          <span className="badge-amber">סטטוס: {p.status}</span>
        </div>
      </div>

      {!editing ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
          <Field label="ספק" value={p.detected_supplier} />
          <Field label="מדינה" value={p.detected_origin_country} />
          <Field label="ETA לארץ" value={fmtDate(p.detected_eta_israel)} />
          <Field label="ETD" value={fmtDate(p.detected_etd)} />
          <Field label="בוקינג" value={p.detected_booking_number} />
          <Field label="BOL" value={p.detected_bol_number} />
          <Field label="Invoice" value={p.detected_invoice_number} />
          <Field label="PO" value={p.detected_po_number} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
          <div><label className="label">ספק</label><input className="input" value={form.detected_supplier || ""} onChange={(e) => set("detected_supplier", e.target.value)} /></div>
          <div><label className="label">תיאור</label><input className="input" value={form.detected_goods_description || ""} onChange={(e) => set("detected_goods_description", e.target.value)} /></div>
          <div><label className="label">מדינה</label><input className="input" value={form.detected_origin_country || ""} onChange={(e) => set("detected_origin_country", e.target.value)} /></div>
          <div><label className="label">ETD</label><input className="input" type="date" value={form.detected_etd || ""} onChange={(e) => set("detected_etd", e.target.value || null)} /></div>
          <div><label className="label">ETA לארץ</label><input className="input" type="date" value={form.detected_eta_israel || ""} onChange={(e) => set("detected_eta_israel", e.target.value || null)} /></div>
          <div><label className="label">בוקינג</label><input className="input" value={form.detected_booking_number || ""} onChange={(e) => set("detected_booking_number", e.target.value)} /></div>
          <div><label className="label">BOL</label><input className="input" value={form.detected_bol_number || ""} onChange={(e) => set("detected_bol_number", e.target.value)} /></div>
          <div><label className="label">עמיל מכס</label><input className="input" value={form.detected_customs_broker || ""} onChange={(e) => set("detected_customs_broker", e.target.value)} /></div>
        </div>
      )}

      {p.pending_containers.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-slate-500 mb-1">מכולות שזוהו:</div>
          <div className="flex flex-wrap gap-2">
            {p.pending_containers.map((pc) => (
              <span key={pc.id} className="text-xs px-2 py-0.5 bg-slate-100 rounded font-mono">
                {pc.detected_container_number}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3">
        {!editing ? (
          <>
            <button className="btn-primary" onClick={() => approve.mutate()} disabled={approve.isPending}>
              {approve.isPending ? "מאשר..." : "אשר והוסף למשלוחים"}
            </button>
            <button className="btn-secondary" onClick={() => setEditing(true)}>ערוך לפני אישור</button>
            <AssignToExisting pendingId={p.id} />
            <button className="btn-danger" onClick={() => reject.mutate()} disabled={reject.isPending}>דחה ומחק</button>
          </>
        ) : (
          <>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>שמור שינויים</button>
            <button className="btn-secondary" onClick={() => { setForm(p); setEditing(false); }}>בטל</button>
          </>
        )}
      </div>
    </li>
  );
}

function Field({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="font-medium">{value || "—"}</div>
    </div>
  );
}

function AssignToExisting({ pendingId }: { pendingId: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [shipmentId, setShipmentId] = useState<number | "">("");
  const ships = useQuery({ queryKey: ["shipments-list"], queryFn: () => listShipments({ archived: false, limit: 500 }) });
  const assign = useMutation({
    mutationFn: () => assignPendingToShipment(pendingId, Number(shipmentId)),
    onSuccess: () => { qc.invalidateQueries(); setOpen(false); },
  });
  if (!open) return <button className="btn-secondary" onClick={() => setOpen(true)}>שייך למשלוח קיים</button>;
  return (
    <div className="flex gap-2 items-center w-full">
      <select className="input flex-1" value={shipmentId} onChange={(e) => setShipmentId(e.target.value ? Number(e.target.value) : "")}>
        <option value="">בחר משלוח</option>
        {ships.data?.items.map((s) => <option key={s.id} value={s.id}>{s.shp_id} — {s.supplier}</option>)}
      </select>
      <button className="btn-primary" disabled={!shipmentId || assign.isPending} onClick={() => assign.mutate()}>שייך</button>
      <button className="btn-secondary" onClick={() => setOpen(false)}>בטל</button>
    </div>
  );
}
