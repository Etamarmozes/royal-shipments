import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listDocuments,
  assignDocument, changeDocumentType,
  listShipments, autoLinkDocuments, possibleMatches, backfillGmailAttachments,
  redownloadInvalidDocuments,
} from "../api/endpoints";
import { PageHeader, Loader, EmptyState } from "../components/common";
import DocumentCard from "../components/DocumentCard";
import { fmtDateTime } from "../utils/format";
import clsx from "clsx";

const DOC_TYPES = [
  { id: "packing_list",         label: "Packing List" },
  { id: "invoice",              label: "Invoice" },
  { id: "bl",                   label: "BL" },
  { id: "bol",                  label: "BOL" },
  { id: "booking_confirmation", label: "Booking Conf." },
  { id: "customs",              label: "Customs" },
  { id: "other",                label: "אחר" },
];

const DOC_LABEL: Record<string, string> = Object.fromEntries(
  DOC_TYPES.map((t) => [t.id, t.label])
);

export default function Documents() {
  const [tab, setTab] = useState<"all" | "unassigned">("all");
  const [search, setSearch] = useState("");
  const qc = useQueryClient();
  const docs = useQuery({
    queryKey: ["documents", tab],
    queryFn: () => listDocuments(tab === "unassigned" ? { unassigned: true } : {}),
  });
  const backfill = useMutation({
    mutationFn: backfillGmailAttachments,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
  const autoLink = useMutation({
    mutationFn: autoLinkDocuments,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
  const redownloadInvalid = useMutation({
    mutationFn: redownloadInvalidDocuments,
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["file-status"] });
      alert(`תוקנו: ${r.fixed}\nתקינים מראש: ${r.skipped_ok}\nכישלונות: ${r.failed.length}`);
    },
  });

  const filtered = (docs.data || []).filter((d) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      (d.filename || "").toLowerCase().includes(s) ||
      (d.shp_id || "").toLowerCase().includes(s) ||
      (d.source_email_subject || "").toLowerCase().includes(s) ||
      (d.source_email_sender || "").toLowerCase().includes(s)
    );
  });

  return (
    <div className="max-w-7xl mx-auto pb-12">
      <PageHeader
        title="מסמכי מקור"
        subtitle="כל המסמכים שנמשכו ממיילים — Packing List / Invoice / BL / Booking"
        actions={
          <>
            <button
              className="btn-secondary"
              onClick={() => backfill.mutate()}
              disabled={backfill.isPending}
              title="הורד את כל ה-attachments שטרם נמשכו ממיילים שכבר ב-DB"
            >
              {backfill.isPending ? "מוריד..." : "Backfill Gmail"}
            </button>
            <button
              className="btn-secondary"
              onClick={() => autoLink.mutate()}
              disabled={autoLink.isPending}
              title="נסה לקשר את המסמכים הלא משויכים לפי שמות קבצים"
            >
              {autoLink.isPending ? "מקשר..." : "Auto-link"}
            </button>
            <button
              className="btn-secondary"
              onClick={() => redownloadInvalid.mutate()}
              disabled={redownloadInvalid.isPending}
              title="נסה להוריד מחדש מסמכים פגומים או חסרים"
            >
              {redownloadInvalid.isPending ? "מתקן..." : "תקן פגומים"}
            </button>
          </>
        }
      />

      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => setTab("all")}
          className={clsx(
            "px-4 py-2 text-sm font-medium rounded-full transition",
            tab === "all" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          )}
        >הכל</button>
        <button
          onClick={() => setTab("unassigned")}
          className={clsx(
            "px-4 py-2 text-sm font-medium rounded-full transition",
            tab === "unassigned" ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          )}
        >לא משויכים</button>
        <input
          className="input flex-1 max-w-md"
          placeholder="חיפוש..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {docs.isLoading ? <Loader /> :
       filtered.length === 0 ? (
         <EmptyState
           iconName="document"
           title={tab === "unassigned" ? "אין מסמכים לא משויכים" : "אין מסמכי מקור"}
           description={
             tab === "unassigned"
               ? "כל המסמכים שיגיעו ולא יזוהו אוטומטית למשלוח יופיעו כאן."
               : "המערכת נקייה. מסמכים יגיעו אוטומטית מסנכרון Gmail עם attachments, או דרך העלאה ידנית מתוך פרופיל משלוח."
           }
           action={tab !== "unassigned" ? { label: "עבור לייבוא Excel", to: "/import-excel" } : undefined}
         />
       ) : (
         <div className="space-y-2">
           {filtered.map((d) => (
             <DocRow key={d.id} doc={d} />
           ))}
         </div>
       )}
    </div>
  );
}

function DocRow({ doc }: { doc: any }) {
  const [editing, setEditing] = useState(false);
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <DocumentCard doc={doc} />
        </div>
        <button
          className="btn-secondary text-xs px-3 py-1.5 self-start"
          onClick={() => setEditing(!editing)}
        >
          {editing ? "סגור" : "ערוך / שייך"}
        </button>
      </div>
      {editing && <DocEditor doc={doc} onClose={() => setEditing(false)} />}
    </div>
  );
}

function DocEditor({ doc, onClose }: { doc: any; onClose: () => void }) {
  const qc = useQueryClient();
  const ships = useQuery({
    queryKey: ["shipments-mini"],
    queryFn: () => listShipments({ archived: false, limit: 500 }),
  });
  const candidates = useQuery({
    queryKey: ["doc-matches", doc.id],
    queryFn: () => possibleMatches(doc.id),
    enabled: !doc.linked_shipment_id,
  });
  const [shipmentId, setShipmentId] = useState<number | "">(doc.linked_shipment_id ?? "");
  const [docType, setDocType] = useState(doc.document_type || "other");

  const assign = useMutation({
    mutationFn: (sid: number) => assignDocument(doc.id, sid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
  const setType = useMutation({
    mutationFn: () => changeDocumentType(doc.id, docType),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <div className="w-full mt-2 p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
      {/* Suggested matches */}
      {!doc.linked_shipment_id && candidates.data && candidates.data.candidates.length > 0 && (
        <div>
          <label className="label">התאמות מוצעות (לפי שם הקובץ):</label>
          <div className="flex flex-wrap gap-2">
            {candidates.data.candidates.map((c) => (
              <button
                key={c.shipment_id}
                className="text-xs px-3 py-1.5 rounded-full bg-white border border-emerald-300 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                onClick={() => assign.mutate(c.shipment_id)}
                disabled={assign.isPending}
                title={`ביטחון: ${Math.round(c.score * 100)}%`}
              >
                {c.shp_id} • {c.supplier} ({Math.round(c.score * 100)}%)
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="label">סוג מסמך</label>
          <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
            {DOC_TYPES.map((t) => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>
          <button className="btn-secondary mt-1 w-full" onClick={() => setType.mutate()}>
            שמור סוג
          </button>
        </div>
        <div>
          <label className="label">משלוח משויך</label>
          <select
            className="input"
            value={shipmentId}
            onChange={(e) => setShipmentId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">— בחר —</option>
            {ships.data?.items.map((s) => (
              <option key={s.id} value={s.id}>{s.shp_id} — {s.supplier}</option>
            ))}
          </select>
          <button
            className="btn-primary mt-1 w-full"
            disabled={shipmentId === ""}
            onClick={() => assign.mutate(Number(shipmentId))}
          >שייך</button>
        </div>
        <div className="flex items-end justify-end">
          <button className="btn-secondary" onClick={onClose}>סגור</button>
        </div>
      </div>
    </div>
  );
}
