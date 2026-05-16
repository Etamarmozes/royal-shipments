import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fileStatus, setDocumentType, markDocAsNoise, restoreDocAsDocument,
         type DocumentClassification } from "../api/endpoints";
import { viewDocument, downloadDocument } from "../utils/fileAccess";
import ExcelPreviewModal from "./ExcelPreview";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { hasPermission } from "../auth/store";
import clsx from "clsx";

const CLASSIFICATION_BADGE: Record<string, { label: string; cls: string }> = {
  commercial_invoice:     { label: "Invoice",     cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  packing_list:           { label: "Packing List", cls: "bg-blue-100 text-blue-800 border-blue-200" },
  bill_of_lading:         { label: "BL",          cls: "bg-violet-100 text-violet-800 border-violet-200" },
  house_bill_of_lading:   { label: "HBL",         cls: "bg-violet-100 text-violet-800 border-violet-200" },
  master_bill_of_lading:  { label: "MBL",         cls: "bg-violet-100 text-violet-800 border-violet-200" },
  purchase_order:         { label: "PO",          cls: "bg-amber-100 text-amber-800 border-amber-200" },
  customs_document:       { label: "Customs",     cls: "bg-orange-100 text-orange-800 border-orange-200" },
  delivery_note:          { label: "Delivery",    cls: "bg-cyan-100 text-cyan-800 border-cyan-200" },
  certificate:            { label: "Certificate", cls: "bg-pink-100 text-pink-800 border-pink-200" },
  product_image:          { label: "תמונת מוצר",  cls: "bg-teal-100 text-teal-800 border-teal-200" },
  shipment_document:      { label: "מסמך",        cls: "bg-slate-100 text-slate-700 border-slate-200" },
  email_noise:            { label: "🚫 רעש מייל", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  unknown_needs_review:   { label: "לא מסווג",    cls: "bg-yellow-100 text-yellow-800 border-yellow-200" },
};

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
 * Detect what kind of file this is to choose the right preview/download UX.
 * Uses the magic-byte signature (server returns it via /file-status), which
 * is more trustworthy than the email's claimed mime type.
 */
function classifyDoc(file_type: string | undefined | null, signature: string | undefined | null) {
  const sig = signature || "";
  const mime = (file_type || "").toLowerCase();
  if (sig === "pdf" || mime === "application/pdf") return "pdf";
  if (sig === "ooxml" || mime.includes("openxml") || mime.includes("xlsx") || mime.includes("docx")) {
    // Could be xlsx OR docx OR pptx — disambiguate by mime/filename
    if (mime.includes("spreadsheet") || mime.includes("excel")) return "xlsx";
    if (mime.includes("word") || mime.includes("document")) return "docx";
    return "ooxml_unknown";
  }
  if (sig === "ole" || mime === "application/vnd.ms-excel" || mime === "application/msword") {
    if (mime.includes("excel") || mime === "application/vnd.ms-excel") return "xls";
    if (mime.includes("word") || mime === "application/msword") return "doc";
    return "ole_unknown";
  }
  if (sig.startsWith("image_") || mime.startsWith("image/")) return "image";
  return "other";
}

/**
 * One reusable card showing a document with the right action buttons for its type.
 * Uses /file-status on mount to verify validity, and shows a status badge.
 */
export default function DocumentCard({
  doc,
  showShipmentLink = true,
  showSourceEmail = true,
}: {
  doc: any;
  showShipmentLink?: boolean;
  showSourceEmail?: boolean;
}) {
  const [excelOpen, setExcelOpen] = useState(false);
  const isDriveLink = !!doc.source_url;
  const status = useQuery({
    queryKey: ["file-status", doc.id],
    queryFn: () => fileStatus(doc.id),
    enabled: !isDriveLink,
    staleTime: 60_000,
  });

  // Pick filename hint for type detection (from server signature when ready)
  const docKind = classifyDoc(doc.file_type, status.data?.signature);
  const isValid = isDriveLink ? true : status.data?.status === "valid";

  // Filename also used for type detection — sometimes mime is wrong but extension is right
  const fname = (doc.filename || "").toLowerCase();
  const looksXlsx = fname.endsWith(".xlsx") || fname.endsWith(".xlsm");
  const looksXls = fname.endsWith(".xls");
  const looksXl = looksXlsx || looksXls;
  const looksWord = fname.endsWith(".doc") || fname.endsWith(".docx");
  const isExcel = isValid && (docKind === "xlsx" || docKind === "xls" || looksXl);

  return (
    <div
      className={clsx(
        "rounded-xl border p-3 flex items-start gap-3",
        isValid ? "border-slate-200 hover:bg-slate-50" : "border-red-300 bg-red-50",
      )}
    >
      <span className="text-2xl">
        {isDriveLink ? "🔗" :
         docKind === "pdf" ? "📕" :
         isExcel ? "📊" :
         looksWord ? "📝" :
         docKind === "image" ? "🖼️" : "📄"}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-800 truncate">
            {isDriveLink ? "Drive link" : doc.filename || "—"}
          </span>
          {doc.classification ? (
            <ClassificationBadge
              classification={doc.classification}
              confidence={doc.classification_confidence}
              manuallySet={!!doc.manually_classified_by}
            />
          ) : (
            <span className="badge-blue text-[10px]">
              {DOC_LABEL[doc.document_type || ""] || doc.document_type || "אחר"}
            </span>
          )}
          {isDriveLink && <span className="badge-purple text-[10px]">Drive</span>}
          {!isDriveLink && (
            isValid ? (
              <span className="badge-green text-[10px]">
                ✓ {status.data?.size ? `${Math.round(status.data.size / 1024)}KB` : ""}
              </span>
            ) : status.isLoading ? (
              <span className="badge-gray text-[10px]">בודק...</span>
            ) : (
              <span className="badge-red text-[10px]">
                ⚠ {status.data?.status === "missing" ? "חסר בדיסק" :
                   status.data?.status === "empty" ? "ריק" :
                   "לא תקין"}
              </span>
            )
          )}
          {showShipmentLink && doc.shp_id && (
            <Link to={`/shipments/${doc.linked_shipment_id}`} className="badge-green text-[10px]">
              {doc.shp_id}
            </Link>
          )}
          {showShipmentLink && !doc.shp_id && !isDriveLink && (
            <span className="badge-amber text-[10px]">לא משויך</span>
          )}
          {doc.container_number && (
            <span className="badge-gray text-[10px]">📦 {doc.container_number}</span>
          )}
        </div>

        {showSourceEmail && (
          <div className="text-xs text-slate-500 mt-1 truncate">
            {doc.source_email_sender && <>מאת: {doc.source_email_sender} • </>}
            {doc.source_email_subject || ""}
          </div>
        )}
        {isDriveLink && (
          <div className="text-[10px] text-slate-400 mt-1 break-all">{doc.source_url}</div>
        )}
      </div>

      {/* Action buttons — depend on file type */}
      <div className="flex flex-col gap-1 shrink-0">
        {isDriveLink ? (
          <a
            className="btn-primary text-xs px-3 py-1.5"
            href={doc.source_url}
            target="_blank"
            rel="noopener"
          >
            פתח Drive
          </a>
        ) : !isValid ? (
          <span className="text-[10px] text-red-700">לא ניתן להוריד</span>
        ) : (
          <>
            {/* PDF / image preview — fetched with JWT, opened as Blob URL */}
            {(docKind === "pdf" || docKind === "image") && (
              <button
                className="btn-secondary text-xs px-3 py-1.5"
                onClick={() => viewDocument(doc.id)}
              >
                הצג
              </button>
            )}
            {/* Excel inline preview */}
            {isExcel && (
              <button
                className="btn-secondary text-xs px-3 py-1.5"
                onClick={() => setExcelOpen(true)}
              >
                הצג Excel
              </button>
            )}
            {/* Always: download — fetched with JWT, saved via Blob URL */}
            <button
              className="btn-secondary text-xs px-3 py-1.5"
              onClick={() => downloadDocument(doc.id, doc.filename)}
            >
              הורד
            </button>
          </>
        )}
      </div>

      {/* Reclassify dropdown — admin/import_manager only */}
      {hasPermission("document.assign") && (
        <ReclassifyMenu doc={doc} />
      )}

      {excelOpen && (
        <ExcelPreviewModal
          docId={doc.id}
          filename={doc.filename}
          onClose={() => setExcelOpen(false)}
        />
      )}
    </div>
  );
}


function ClassificationBadge({
  classification, confidence, manuallySet,
}: {
  classification: string;
  confidence?: number | null;
  manuallySet?: boolean;
}) {
  const meta = CLASSIFICATION_BADGE[classification] ||
               { label: classification, cls: "bg-slate-100 text-slate-700 border-slate-200" };
  const conf = confidence != null ? Math.round(confidence * 100) : null;
  return (
    <span
      className={clsx(
        "text-[10px] px-2 py-0.5 rounded-md border font-medium",
        meta.cls,
      )}
      title={`classification: ${classification}${conf ? ` (${conf}%)` : ""}${
        manuallySet ? " · נקבע ידנית" : ""}`}
    >
      {meta.label}
      {manuallySet && " 🔒"}
    </span>
  );
}


function ReclassifyMenu({ doc }: { doc: any }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const setType = useMutation({
    mutationFn: (cls: DocumentClassification) =>
      setDocumentType(doc.id, cls, "manually set from card"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docs"] });
      qc.invalidateQueries({ queryKey: ["shipment-documents"] });
      qc.invalidateQueries({ queryKey: ["doc-status"] });
      qc.invalidateQueries({ queryKey: ["filtered-noise"] });
      setOpen(false);
    },
  });
  const restore = useMutation({
    mutationFn: () => restoreDocAsDocument(doc.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docs"] });
      qc.invalidateQueries({ queryKey: ["shipment-documents"] });
      qc.invalidateQueries({ queryKey: ["doc-status"] });
      qc.invalidateQueries({ queryKey: ["filtered-noise"] });
      setOpen(false);
    },
  });

  const isNoise = doc.is_email_noise === true;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="btn-secondary text-xs px-2 py-1.5"
        title="שנה סיווג"
      >⋯</button>
      {open && (
        <div
          className="absolute left-0 mt-1 z-10 w-56 bg-white border border-slate-200 rounded-lg shadow-lg p-1 text-xs"
          onMouseLeave={() => setOpen(false)}
        >
          <div className="px-2 py-1 text-[10px] text-slate-500 font-semibold">
            הגדר סיווג ידני
          </div>
          {Object.entries(CLASSIFICATION_BADGE)
            .filter(([k]) => k !== "email_noise" && k !== "unknown_needs_review")
            .map(([k, v]) => (
              <button
                key={k}
                className="w-full text-right px-2 py-1 hover:bg-slate-50 rounded"
                onClick={() => setType.mutate(k as DocumentClassification)}
                disabled={setType.isPending}
              >
                {v.label}
              </button>
            ))}
          <div className="border-t border-slate-100 my-1" />
          {!isNoise ? (
            <button
              className="w-full text-right px-2 py-1 hover:bg-rose-50 rounded text-rose-700"
              onClick={() => setType.mutate("email_noise")}
              disabled={setType.isPending}
            >
              🚫 סמן כרעש מייל
            </button>
          ) : (
            <button
              className="w-full text-right px-2 py-1 hover:bg-emerald-50 rounded text-emerald-700"
              onClick={() => restore.mutate()}
              disabled={restore.isPending}
            >
              ↶ שחזר כמסמך
            </button>
          )}
        </div>
      )}
    </div>
  );
}
