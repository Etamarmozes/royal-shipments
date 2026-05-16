import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listEmailUpdates, approveEmailUpdate, rejectEmailUpdate, assignEmailUpdate,
  injectEmail, syncEmailNow, listShipments, processFetchedEmails, reprocessEmail,
  gmailStatus, gmailSync, gmailConnectUrl,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState, Section } from "../components/common";
import { hasPermission } from "../auth/store";
import { fmtDateTime } from "../utils/format";
import type { EmailUpdate } from "../types";

const STATUS_LABELS: Record<string, string> = {
  fetched: "נטען מ-Gmail",
  parsed: "נותח",
  pending: "ממתין",
  needs_review: "דורש בדיקה",
  approved: "עודכן",
  rejected: "נדחה",
  auto_applied: "עודכן אוטומטית",
  ignored: "לא רלוונטי",
};

const TYPE_LABELS: Record<string, string> = {
  update: "עדכון משלוח קיים",
  delay: "עיכוב",
  new_shipment: "משלוח חדש",
  unknown: "לא רלוונטי",
  // legacy values
  update_existing: "עדכון משלוח קיים",
  needs_review: "דורש בדיקה",
  irrelevant: "לא רלוונטי",
};

function typeBadge(t?: string | null) {
  switch (t) {
    case "update": return "badge-blue";
    case "delay": return "badge-red";
    case "new_shipment": return "badge-purple";
    case "unknown": return "badge-gray";
    default: return "badge-gray";
  }
}

function confColor(c?: number | null) {
  if (c == null) return "badge-gray";
  if (c >= 0.8) return "badge-green";
  if (c >= 0.5) return "badge-amber";
  return "badge-gray";
}

export default function EmailUpdates() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showInject, setShowInject] = useState(false);

  const q = useQuery({
    queryKey: ["email-updates", statusFilter],
    queryFn: () => listEmailUpdates(statusFilter ? { status: statusFilter } : {}),
  });
  const gmail = useQuery({ queryKey: ["gmail-status"], queryFn: gmailStatus });

  const sync = useMutation({
    mutationFn: syncEmailNow,
    onSuccess: () => qc.invalidateQueries(),
  });
  const fetchGmail = useMutation({
    mutationFn: gmailSync,
    onSuccess: () => qc.invalidateQueries(),
  });
  const parseFetched = useMutation({
    mutationFn: processFetchedEmails,
    onSuccess: (res) => {
      qc.invalidateQueries();
      alert(
        `סיווג הסתיים:\n` +
          `סה"כ: ${res.processed}\n` +
          `עדכונים: ${res.update}\n` +
          `עיכובים: ${res.delay}\n` +
          `משלוחים חדשים: ${res.new_shipment}\n` +
          `לא רלוונטי: ${res.unknown}\n` +
          (res.errors ? `שגיאות: ${res.errors}` : "")
      );
    },
  });

  return (
    <div>
      <PageHeader
        title="מרכז עדכונים ממייל"
        subtitle="כל המיילים שנסרקו, מה זוהה ומה מחכה לטיפול"
        actions={
          <div className="flex flex-wrap gap-2">
            {gmail.data?.connected ? (
              <button
                className="btn-primary"
                onClick={() => fetchGmail.mutate()}
                disabled={fetchGmail.isPending}
              >
                {fetchGmail.isPending ? "מושך מ-Gmail..." : "Sync Gmail"}
              </button>
            ) : (
              <a className="btn-primary" href={gmailConnectUrl()}>
                חבר Gmail
              </a>
            )}
            <button
              className="btn-secondary"
              onClick={() => parseFetched.mutate()}
              disabled={parseFetched.isPending}
            >
              {parseFetched.isPending ? "מנתח..." : "Parse fetched emails"}
            </button>
            <button className="btn-secondary" onClick={() => sync.mutate()} disabled={sync.isPending}>
              סנכרן (stub)
            </button>
            <button className="btn-secondary" onClick={() => setShowInject(!showInject)}>
              הזרק מייל לבדיקה
            </button>
          </div>
        }
      />

      {gmail.data && (
        <div className="text-xs text-slate-500 mb-3">
          {gmail.data.connected ? (
            <>✅ Gmail מחובר {gmail.data.expiry && <>• הטוקן בתוקף עד {fmtDateTime(gmail.data.expiry)}</>}</>
          ) : (
            <>⚠️ Gmail לא מחובר. לחץ "חבר Gmail" כדי להתחיל.</>
          )}
        </div>
      )}

      {showInject && <InjectForm onDone={() => { setShowInject(false); qc.invalidateQueries({ queryKey: ["email-updates"] }); }} />}

      <div className="card mb-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="label">סטטוס</label>
          <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">הכל</option>
            {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>

      {q.isLoading ? <Loader /> :
       q.isError ? <ErrorState error={q.error} /> :
       !q.data || q.data.length === 0 ? <EmptyState title="אין מיילים" description="חבר Gmail או הזרק מייל לבדיקה" /> :
       <ul className="space-y-3">
         {q.data.map((u) => <EmailRow key={u.id} u={u} />)}
       </ul>}
    </div>
  );
}

function EmailRow({ u }: { u: EmailUpdate }) {
  const qc = useQueryClient();
  const approve = useMutation({
    mutationFn: () => approveEmailUpdate(u.id),
    onSuccess: () => qc.invalidateQueries(),
  });
  const reject = useMutation({
    mutationFn: () => rejectEmailUpdate(u.id),
    onSuccess: () => qc.invalidateQueries(),
  });
  const reparse = useMutation({
    mutationFn: () => reprocessEmail(u.id),
    onSuccess: () => qc.invalidateQueries(),
  });

  const isActionable =
    (u.status === "parsed" || u.status === "pending" || u.status === "needs_review")
    && (u.detection_type === "update" || u.detection_type === "delay" || u.detection_type === "update_existing");

  // For new_shipment we point to /pending-shipments page instead (PendingShipment lives there)
  const isNewShipment = u.detection_type === "new_shipment";

  // Render extracted fields from new shape (extracted_fields nested) or legacy flat
  const fieldsObj = u.detected_fields_json as any;
  const extracted = fieldsObj?.extracted_fields ?? fieldsObj ?? {};
  const summary = fieldsObj?.summary ?? null;

  return (
    <li className="card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-xs text-slate-500">{fmtDateTime(u.received_at)} • מאת {u.sender}</div>
          <div className="font-semibold text-slate-800">{u.subject}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {u.detection_type && (
            <span className={typeBadge(u.detection_type)}>
              {TYPE_LABELS[u.detection_type] || u.detection_type}
            </span>
          )}
          {u.auto_applied && <span className="badge-green">✓ עודכן אוטומטית</span>}
          {u.needs_review && <span className="badge-red">⚠ דורש בדיקה</span>}
          {u.confidence_score !== null && u.confidence_score !== undefined && (
            <span className={confColor(u.confidence_score)}>
              ביטחון {Math.round((u.confidence_score || 0) * 100)}%
            </span>
          )}
          {!u.auto_applied && !u.needs_review && (
            <span className="badge-gray">{STATUS_LABELS[u.status] || u.status}</span>
          )}
          {u.detected_shp_id && <span className="badge-green">{u.detected_shp_id}</span>}
        </div>
      </div>

      {summary && (
        <div className="text-sm text-slate-700 mt-2 font-medium">{summary}</div>
      )}

      {u.review_reason && (
        <div className="mt-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-900">
          <b>סיבת בדיקה:</b> {u.review_reason}
        </div>
      )}

      {u.applied_fields_json && Array.isArray(u.applied_fields_json) && u.applied_fields_json.length > 0 && (
        <div className="mt-2 text-xs">
          <span className="text-emerald-700 font-medium">עודכן אוטומטית: </span>
          {u.applied_fields_json.map((f: any, i: number) => (
            <span key={i} className="text-slate-600">
              {f.field}: {f.old || "—"} → {f.new}
              {i < u.applied_fields_json.length - 1 ? " · " : ""}
            </span>
          ))}
        </div>
      )}

      {u.flagged_fields_json && Array.isArray(u.flagged_fields_json) && u.flagged_fields_json.length > 0 && (
        <div className="mt-2 text-xs">
          <span className="text-red-700 font-medium">חסום עד אישור: </span>
          {u.flagged_fields_json.map((f: any, i: number) => (
            <span key={i} className="text-slate-600">
              {f.field}: {f.old || "—"} → {f.new}
              {i < u.flagged_fields_json.length - 1 ? " · " : ""}
            </span>
          ))}
        </div>
      )}

      <div className="text-sm text-slate-600 mt-2 whitespace-pre-line line-clamp-3">{u.body_excerpt}</div>

      {extracted && Object.keys(extracted).length > 0 && (
        <div className="mt-2">
          <div className="text-xs text-slate-500 mb-1">שדות שזוהו:</div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(extracted).map(([k, v]) => {
              if (v === false || v === null || v === undefined) return null;
              const display = Array.isArray(v) ? v.join(", ") : String(v);
              return (
                <span key={k} className="text-xs px-2 py-0.5 bg-slate-100 rounded">
                  <b>{k}:</b> {display}
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3">
        {isActionable && u.detected_shipment_id && hasPermission("email.approve") && (
          <>
            <button className="btn-primary" onClick={() => approve.mutate()} disabled={approve.isPending}>
              {approve.isPending ? "מאשר..." : "אשר עדכון"}
            </button>
            <button className="btn-danger" onClick={() => reject.mutate()} disabled={reject.isPending}>
              דחה
            </button>
          </>
        )}
        {isActionable && u.detected_shipment_id && !hasPermission("email.approve") && (
          <span className="text-xs text-slate-500">דורש מנהל יבוא לאישור</span>
        )}
        {isActionable && !u.detected_shipment_id && hasPermission("email.approve") && (
          <AssignButton emailId={u.id} />
        )}
        {isNewShipment && (
          <a href="/pending-shipments" className="btn-secondary">
            פתח טיוטת משלוח חדש →
          </a>
        )}
        {(u.status === "fetched" || u.status === "ignored") && (
          <button className="btn-secondary" onClick={() => reparse.mutate()} disabled={reparse.isPending}>
            {reparse.isPending ? "מנתח..." : "נתח מחדש"}
          </button>
        )}
      </div>
    </li>
  );
}

function AssignButton({ emailId }: { emailId: number }) {
  const [open, setOpen] = useState(false);
  const [shipmentId, setShipmentId] = useState<number | "">("");
  const qc = useQueryClient();
  const ships = useQuery({ queryKey: ["shipments-list"], queryFn: () => listShipments({ archived: false, limit: 500 }) });
  const assign = useMutation({
    mutationFn: () => assignEmailUpdate(emailId, Number(shipmentId)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["email-updates"] }); setOpen(false); },
  });
  if (!open) return <button className="btn-secondary" onClick={() => setOpen(true)}>שייך למשלוח</button>;
  return (
    <div className="flex gap-2 items-center">
      <select className="input" value={shipmentId} onChange={(e) => setShipmentId(e.target.value ? Number(e.target.value) : "")}>
        <option value="">בחר משלוח</option>
        {ships.data?.items.map((s) => (
          <option key={s.id} value={s.id}>{s.shp_id} — {s.supplier}</option>
        ))}
      </select>
      <button className="btn-primary" disabled={!shipmentId || assign.isPending} onClick={() => assign.mutate()}>
        שייך
      </button>
      <button className="btn-secondary" onClick={() => setOpen(false)}>בטל</button>
    </div>
  );
}

function InjectForm({ onDone }: { onDone: () => void }) {
  const [sender, setSender] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const inject = useMutation({
    mutationFn: () => injectEmail({ sender, subject, body }),
    onSuccess: onDone,
  });
  return (
    <Section title="הזרקת מייל לבדיקה (Demo)">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <input className="input" placeholder="שולח (מייל)" value={sender} onChange={(e) => setSender(e.target.value)} />
        <input className="input" placeholder="נושא" value={subject} onChange={(e) => setSubject(e.target.value)} />
        <textarea className="input md:col-span-2" rows={5} placeholder="תוכן המייל..." value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
      <div className="flex justify-end gap-2 mt-3">
        <button className="btn-primary" onClick={() => inject.mutate()} disabled={!sender || !subject || !body || inject.isPending}>
          הזרק
        </button>
      </div>
      <div className="text-xs text-slate-500 mt-2">
        טיפ: כלול בגוף המייל <code>SHP-008</code>, <code>ETA: 12/06/2026</code>, <code>Container ABCD1234567</code>, <code>Booking BK998877</code> כדי לראות זיהוי אוטומטי.
      </div>
    </Section>
  );
}
