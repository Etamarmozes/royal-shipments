import { useState, useRef, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getShipment, updateShipment, archiveShipment, shipmentEvents,
  listContainers, listExtraWork,
  uploadShipmentProductImage, deleteShipmentProductImage,
  listShipmentDocuments,
  uploadDocument, listCategories,
  getSmartDocStatus, recalculateDocStatus,
  type SmartDocStatus,
} from "../api/endpoints";
import AuthedImage from "../components/AuthedImage";
import DocumentCard from "../components/DocumentCard";
import ShipmentTimeline from "../components/ShipmentTimeline";
import { hasPermission } from "../auth/store";
import { PageHeader, Loader, ErrorState, Section } from "../components/common";
import { DataQualityBadge, MissingDataPanel, OverridePill } from "../components/DataQuality";
import { shipmentDataQuality } from "../api/endpoints";
import { fmtDate, fmtDateTime, stageLabel } from "../utils/format";
import type { Shipment } from "../types";
import clsx from "clsx";

const TABS = [
  { id: "general", label: "פרטים" },
  { id: "containers", label: "מכולות" },
  { id: "documents", label: "מסמכי מקור" },
  { id: "paperwork", label: "ניירת ועלויות" },
  { id: "emails", label: "מיילים" },
  { id: "extra", label: "תוספת עבודה" },
  { id: "history", label: "היסטוריית שינויים" },
];

export default function ShipmentProfile() {
  const { id } = useParams();
  const sid = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<string>("general");

  const ship = useQuery({
    queryKey: ["shipment", sid],
    queryFn: () => getShipment(sid),
    enabled: !Number.isNaN(sid),
  });
  const containers = useQuery({
    queryKey: ["containers", "shipment", sid],
    queryFn: () => listContainers(),
    enabled: !!ship.data,
    select: (rows) => rows.filter((c) => c.shipment_id === sid),
  });
  const extra = useQuery({
    queryKey: ["extra", sid],
    queryFn: () => listExtraWork({ shipment_id: sid }),
    enabled: !!ship.data?.extra_work_required,
  });
  const events = useQuery({
    queryKey: ["events", "shipment", sid],
    queryFn: () => shipmentEvents(sid),
    enabled: tab === "history",
  });

  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState<number>(0);  // ticks each successful save
  const update = useMutation({
    mutationFn: (payload: Partial<Shipment>) => updateShipment(sid, payload),
    onSuccess: () => {
      // Refetch the shipment AND every list/dashboard query that surfaces it,
      // so the dashboard, Active Shipments, and Containers In Transit all
      // reflect the new value immediately.
      qc.invalidateQueries({ queryKey: ["shipment", sid] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
      qc.invalidateQueries({ queryKey: ["shipments-active"] });
      qc.invalidateQueries({ queryKey: ["containers"] });
      qc.invalidateQueries({ queryKey: ["kpis"] });
      qc.invalidateQueries({ queryKey: ["pallet-kpis"] });
      qc.invalidateQueries({ queryKey: ["events", "shipment", sid] });
      setSaveError(null);
      setSaveOk((n) => n + 1);
    },
    onError: (err: any) => {
      // Surface the backend error so the user knows it DID NOT save —
      // previously this was swallowed and the user thought it persisted.
      const msg = err?.message
        || err?.response?.data?.detail
        || "השמירה נכשלה — נסה שוב";
      setSaveError(typeof msg === "string" ? msg : JSON.stringify(msg));
    },
  });
  const archive = useMutation({
    mutationFn: () => archiveShipment(sid),
    onSuccess: () => navigate("/history"),
    onError: (err: any) => {
      alert(`ארכיון נכשל: ${err?.message || "שגיאה לא ידועה"}`);
    },
  });

  if (ship.isLoading) return <Loader />;
  if (ship.isError) return <ErrorState error={ship.error} />;
  if (!ship.data) return null;
  const s = ship.data;

  const focusField = (field: string) => {
    setTab("general");
    setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-field="${field}"]`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        const input = el.querySelector("input,select,textarea") as HTMLElement | null;
        input?.focus();
      }
    }, 100);
  };

  return (
    <div>
      <PageHeader
        title={`${s.shp_id} — ${s.supplier || ""}`}
        subtitle={s.goods_description || ""}
        actions={
          <>
            <Link className="btn-secondary" to="/shipments">חזרה לרשימה</Link>
            {!s.archived && hasPermission("shipment.archive") && (
              <button
                className="btn-danger"
                onClick={() => archive.mutate()}
                disabled={archive.isPending}
              >
                העבר לארכיון
              </button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-4">
        <Mini label="שלב" value={stageLabel(s.current_stage)} />
        <Mini label="ETA לארץ" value={fmtDate(s.eta_israel)} />
        <Mini label="ETA נמל" value={fmtDate(s.eta_port)} />
        <Mini label="ETA מחסן" value={fmtDate(s.eta_warehouse)} />
        <Mini label="מכולות" value={String(s.container_count || 0)} />
        <Mini label="עיכוב" value={s.delay_status ? "כן" : "לא"} />
      </div>

      {/* Visual lifecycle — Phase 1: read-only.  Clicking a stage just
          scrolls to the שלב editor field; no DB write happens here. */}
      <ShipmentTimeline
        currentStage={s.current_stage}
        onStageClick={() => focusField("current_stage")}
        className="mb-4"
      />

      <div className="mb-4 flex items-center gap-2 flex-wrap">
        <DataQualityBadge type="shipment" id={s.id} />
        {s.last_auto_update_at && (
          <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-2 py-1">
            ✓ עודכן אוטומטית ממייל #{s.last_auto_update_source_email_id || "?"} — {fmtDateTime(s.last_auto_update_at)}
          </span>
        )}
      </div>

      <MissingDataInline shipmentId={s.id} onFix={focusField} />

      <ProductImageSection shipment={s} />


      <div className="flex gap-1 border-b border-slate-200 mb-4 overflow-x-auto">
        {TABS.filter((t) => t.id !== "extra" || s.extra_work_required).map((t) => (
          <button
            key={t.id}
            className={clsx(
              "px-4 py-2 text-sm font-medium whitespace-nowrap",
              tab === t.id
                ? "border-b-2 border-brand-500 text-brand-700"
                : "text-slate-600 hover:text-slate-800"
            )}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "general" && <GeneralTab
        s={s}
        onUpdate={(p) => { setSaveError(null); update.mutate(p); }}
        isPending={update.isPending}
        saveError={saveError}
        saveOk={saveOk}
      />}
      {tab === "containers" && (
        <Section title="מכולות במשלוח">
          {containers.isLoading ? (
            <Loader />
          ) : containers.data && containers.data.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-slate-500 text-xs">
                    <th className="text-right py-2 px-2">מספר</th>
                    <th className="text-right py-2 px-2">סוג</th>
                    <th className="text-right py-2 px-2">CBM</th>
                    <th className="text-right py-2 px-2">קופסאות</th>
                    <th className="text-right py-2 px-2">משקל</th>
                    <th className="text-right py-2 px-2">ETA לארץ</th>
                    <th className="text-right py-2 px-2">סטטוס</th>
                    <th className="text-right py-2 px-2">עדיפות</th>
                  </tr>
                </thead>
                <tbody>
                  {containers.data.map((c) => (
                    <tr key={c.id} className="border-t border-slate-100">
                      <td className="py-2 px-2 font-mono">{c.container_number}</td>
                      <td className="py-2 px-2">{c.container_type || "—"}</td>
                      <td className="py-2 px-2">{c.cbm ?? "—"}</td>
                      <td className="py-2 px-2">{c.boxes_total ?? "—"}</td>
                      <td className="py-2 px-2">{c.gross_weight_kg ?? "—"}</td>
                      <td className="py-2 px-2">{fmtDate(c.effective_eta_israel)}</td>
                      <td className="py-2 px-2">{c.container_status || "—"}</td>
                      <td className="py-2 px-2">{c.unloading_priority || "רגיל"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-sm text-slate-500">אין מכולות.</div>
          )}
        </Section>
      )}
      {tab === "documents" && <DocumentsTab shipmentId={s.id} />}
      {tab === "paperwork" && <PaperworkTab
        s={s}
        onUpdate={(p) => { setSaveError(null); update.mutate(p); }}
        isPending={update.isPending}
        saveError={saveError}
        saveOk={saveOk}
      />}
      {tab === "emails" && (
        <Section title="מיילים מקושרים">
          <div className="text-sm text-slate-500">
            למסך מיילים מלא <Link className="text-brand-600" to="/email-updates">לחץ כאן</Link>.
          </div>
        </Section>
      )}
      {tab === "extra" && (
        <Section title="תוספת עבודה">
          {extra.data && extra.data.length ? (
            <ul className="divide-y divide-slate-100">
              {extra.data.map((t) => (
                <li key={t.id} className="py-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{t.work_type}</div>
                      <div className="text-xs text-slate-500">
                        סטטוס: {t.work_status} • אחראי: {t.responsible_party || "—"}
                      </div>
                    </div>
                    <div className="text-xs text-slate-600">
                      צפוי: {fmtDate(t.expected_end_date)}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-500">לא הוגדרו משימות.</div>
          )}
        </Section>
      )}
      {tab === "history" && (
        <Section title="לוג שינויים">
          {events.isLoading ? (
            <Loader />
          ) : events.data && events.data.length ? (
            <ul className="divide-y divide-slate-100">
              {events.data.map((e) => (
                <li key={e.id} className="py-2 text-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium">{e.action_type}</span>
                      {e.field_changed && (
                        <span className="text-slate-600">
                          {" "}— {e.field_changed}: {e.old_value || "—"} → {e.new_value || "—"}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-400">
                      {fmtDateTime(e.changed_at)} • {e.source}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-500">אין רישומי לוג.</div>
          )}
        </Section>
      )}
    </div>
  );
}

function DocumentsTab({ shipmentId }: { shipmentId: number }) {
  const qc = useQueryClient();
  const [showNoise, setShowNoise] = useState(false);

  const docs = useQuery({
    queryKey: ["shipment-documents", shipmentId],
    queryFn: () => listShipmentDocuments(shipmentId),
  });

  // Smart status — uses backend classification
  const status = useQuery({
    queryKey: ["doc-status", shipmentId],
    queryFn: () => getSmartDocStatus(shipmentId),
  });

  const recalc = useMutation({
    mutationFn: () => recalculateDocStatus(shipmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doc-status", shipmentId] });
      qc.invalidateQueries({ queryKey: ["shipment-documents", shipmentId] });
    },
  });

  const fileRef = useRef<HTMLInputElement>(null);
  const [docType, setDocType] = useState("packing_list");
  const upload = useMutation({
    mutationFn: (f: File) => uploadDocument(f, shipmentId, undefined, docType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shipment-documents", shipmentId] });
      qc.invalidateQueries({ queryKey: ["doc-status", shipmentId] });
    },
  });

  // Filter docs by noise flag
  const allDocs = docs.data || [];
  const visibleDocs = showNoise
    ? allDocs
    : allDocs.filter((d: any) => !d.is_email_noise);
  const noiseCount = allDocs.filter((d: any) => d.is_email_noise).length;

  const renderDoc = (d: any) => (
    <DocumentCard key={d.id} doc={d} showShipmentLink={false} />
  );

  return (
    <Section title="מסמכי מקור">
      {/* Smart document status panel */}
      <SmartDocStatusPanel
        status={status.data}
        loading={status.isLoading}
        onRecalc={() => recalc.mutate()}
        recalcing={recalc.isPending}
      />

      {/* Filter toggle for email noise */}
      {noiseCount > 0 && (
        <div className="mb-3 flex items-center gap-2 text-xs">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showNoise}
              onChange={(e) => setShowNoise(e.target.checked)}
            />
            <span className="text-slate-700">
              הצג גם {noiseCount} קבצים שסוננו (לוגואים / חתימות / תמונות מייל)
            </span>
          </label>
        </div>
      )}

      {/* Upload — visible only to roles with document.upload */}
      {hasPermission("document.upload") && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <select
            className="input w-auto"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
          >
            <option value="packing_list">Packing List</option>
            <option value="invoice">Invoice</option>
            <option value="bl">BL</option>
            <option value="bol">BOL</option>
            <option value="booking_confirmation">Booking Conf.</option>
            <option value="customs">Customs</option>
            <option value="other">אחר</option>
          </select>
          <button
            className="btn-primary"
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
          >
            {upload.isPending ? "מעלה..." : "📤 העלה מסמך"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.xls,.xlsx,.doc,.docx"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.target.value = "";
            }}
          />
          {upload.isError && <span className="text-sm text-red-700">שגיאה בהעלאה</span>}
        </div>
      )}

      {docs.isLoading ? <Loader /> :
       !visibleDocs.length ? (
         <div className="text-sm text-slate-500 py-2">
           {allDocs.length === 0
             ? "לא נמצאו מסמכים. בדוק אם המיילים כוללים attachments או רק קישורי Drive, או העלה מסמך ידנית בכפתור למעלה."
             : "כל המסמכים הקיימים סוננו כרעש מייל. הפעל את התיבה למעלה כדי להציג אותם."}
         </div>
       ) : (
         <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
           {visibleDocs.map(renderDoc)}
         </div>
       )}
    </Section>
  );
}


function ProductImageSection({ shipment }: { shipment: Shipment }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => uploadShipmentProductImage(shipment.id, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shipment", shipment.id] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
      setPreviewUrl(null);
      setError(null);
    },
    onError: (e: any) => setError(e?.message || "שגיאה בהעלאה"),
  });
  const remove = useMutation({
    mutationFn: () => deleteShipmentProductImage(shipment.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shipment", shipment.id] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setError(null);
    setPreviewUrl(URL.createObjectURL(f));
    upload.mutate(f);
  };

  const hasImage = !!shipment.product_image_path;
  // Cache buster: include updated_at so re-uploads refetch the image.
  // (apiBase prefix is added by AuthedImage via fetchAuthedBlob.)
  const imgPath = `/shipments/${shipment.id}/product-image?t=${encodeURIComponent(shipment.updated_at || "")}`;

  return (
    <Section title="תמונת מוצר">
      <div className="flex flex-col sm:flex-row gap-4 items-start">
        <div className="w-40 h-40 rounded-xl overflow-hidden bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
          {previewUrl ? (
            <img src={previewUrl} alt="טוען..." className="w-full h-full object-cover opacity-70" />
          ) : hasImage ? (
            <AuthedImage path={imgPath} alt="תמונת מוצר"
                         className="w-full h-full object-cover"
                         fallback={<div className="text-slate-400 text-xs text-center px-2">תמונה לא זמינה</div>} />
          ) : (
            <div className="text-slate-400 text-xs text-center px-2">אין תמונה</div>
          )}
        </div>
        <div className="flex-1">
          <p className="text-sm text-slate-600 mb-3">
            ניתן להעלות תמונת מוצר אחת לכל משלוח. סוגים מותרים: jpg, png, webp. עד 8MB.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className="btn-primary"
              onClick={() => fileRef.current?.click()}
              disabled={upload.isPending}
            >
              {upload.isPending ? "מעלה..." : hasImage ? "החלף תמונה" : "העלה תמונה"}
            </button>
            {hasImage && (
              <button
                className="btn-danger"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
              >
                מחק
              </button>
            )}
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={onPick}
            />
          </div>
          {error && <div className="text-sm text-red-700 mt-2">{error}</div>}
        </div>
      </div>
    </Section>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-base font-semibold mt-1">{value}</div>
    </div>
  );
}

function MissingDataInline({
  shipmentId, onFix,
}: { shipmentId: number; onFix: (field: string) => void }) {
  const q = useQuery({
    queryKey: ["shipment-quality", shipmentId],
    queryFn: () => shipmentDataQuality(shipmentId),
  });
  if (q.isLoading || !q.data) return null;
  if (q.data.score === "complete") return null;
  return (
    <div className="mb-4">
      <MissingDataPanel quality={q.data} onFix={onFix} />
    </div>
  );
}

function GeneralTab({
  s, onUpdate, isPending, saveError, saveOk,
}: {
  s: Shipment;
  onUpdate: (p: Partial<Shipment>) => void;
  isPending: boolean;
  saveError: string | null;
  saveOk: number;
}) {
  const [form, setForm] = useState<Partial<Shipment>>(s);
  const set = (k: keyof Shipment, v: any) => setForm((f) => ({ ...f, [k]: v }));
  const cats = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const ov = s.manual_overrides;

  // Re-sync local form whenever the server sends fresh data (e.g. after a
  // successful save the parent invalidates → refetches → `s` updates).
  // Without this, the input would keep showing the user's typed value
  // even if the server normalized/rejected/altered it.
  useEffect(() => {
    setForm(s);
  }, [s.updated_at, s.id]);

  // Wrapper: apply consistent label + override pill + data-field anchor.
  const Field = ({ field, label, children }: {
    field: string; label: string; children: React.ReactNode;
  }) => (
    <div data-field={field}>
      <label className="label flex items-center gap-1.5">
        <span>{label}</span>
        <OverridePill overrides={ov} field={field} />
      </label>
      {children}
    </div>
  );

  return (
    <Section title="פרטי משלוח">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Field field="category" label="קטגוריה">
          <select
            className="input"
            value={form.category || ""}
            onChange={(e) => set("category", e.target.value || null)}
          >
            <option value="">— ללא —</option>
            {(cats.data?.categories || []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          {form.category_source === "email_auto" && !ov?.category && (
            <div className="text-[10px] text-emerald-700 mt-1">זוהתה ממייל</div>
          )}
        </Field>
        <Field field="supplier" label="ספק">
          <input className="input" value={form.supplier || ""} onChange={(e) => set("supplier", e.target.value)} />
        </Field>
        <Field field="origin_country" label="מדינת מקור">
          <input className="input" value={form.origin_country || ""} onChange={(e) => set("origin_country", e.target.value)} />
        </Field>
        <Field field="origin_port" label="נמל יציאה">
          <input className="input" value={form.origin_port || ""} onChange={(e) => set("origin_port", e.target.value)} />
        </Field>
        <Field field="goods_description" label="תיאור סחורה">
          <input className="input" value={form.goods_description || ""} onChange={(e) => set("goods_description", e.target.value)} />
        </Field>
        <Field field="customs_broker" label="עמיל מכס">
          <input className="input" value={form.customs_broker || ""} onChange={(e) => set("customs_broker", e.target.value)} />
        </Field>
        <Field field="current_stage" label="שלב">
          <select className="input" value={form.current_stage || ""} onChange={(e) => set("current_stage", Number(e.target.value) || null)}>
            <option value="">—</option>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
              <option key={n} value={n}>{stageLabel(n)}</option>
            ))}
          </select>
        </Field>
        <Field field="etd" label="ETD">
          <input className="input" type="date" value={form.etd || ""} onChange={(e) => set("etd", e.target.value || null)} />
        </Field>
        <Field field="eta_israel" label="ETA לארץ">
          <input className="input" type="date" value={form.eta_israel || ""} onChange={(e) => set("eta_israel", e.target.value || null)} />
        </Field>
        <Field field="eta_port" label="ETA נמל">
          <input className="input" type="date" value={form.eta_port || ""} onChange={(e) => set("eta_port", e.target.value || null)} />
        </Field>
        <Field field="eta_warehouse" label="ETA מחסן">
          <input className="input" type="date" value={form.eta_warehouse || ""} onChange={(e) => set("eta_warehouse", e.target.value || null)} />
        </Field>
        <Field field="booking_number" label="מספר בוקינג">
          <input className="input" value={form.booking_number || ""} onChange={(e) => set("booking_number", e.target.value)} />
        </Field>
        <Field field="bol_number" label="BOL">
          <input className="input" value={form.bol_number || ""} onChange={(e) => set("bol_number", e.target.value)} />
        </Field>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={!!form.delay_status}
            onChange={(e) => set("delay_status", e.target.checked)}
          />
          <span className="text-sm">בעיכוב</span>
        </label>
        {form.delay_status && (
          <div className="md:col-span-2">
            <label className="label">סיבת עיכוב (חובה)</label>
            <input
              className="input"
              value={form.delay_reason || ""}
              onChange={(e) => set("delay_reason", e.target.value)}
            />
          </div>
        )}
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={!!form.paperwork_complete}
            onChange={(e) => set("paperwork_complete", e.target.checked)}
          />
          <span className="text-sm">ניירת מלאה</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={!!form.extra_work_required}
            onChange={(e) => set("extra_work_required", e.target.checked)}
          />
          <span className="text-sm">נדרשת תוספת עבודה</span>
        </label>
      </div>

      <div className="mt-3" data-field="notes">
        <label className="label flex items-center gap-1.5">
          <span>הערות</span>
          <OverridePill overrides={ov} field="notes" />
        </label>
        <textarea className="input" rows={3} value={form.notes || ""} onChange={(e) => set("notes", e.target.value)} />
      </div>

      <SaveBar
        isPending={isPending}
        saveError={saveError}
        saveOk={saveOk}
        canSave={hasPermission("shipment.update")}
        onSave={() => onUpdate(form)}
      />
    </Section>
  );
}

function PaperworkTab({
  s, onUpdate, isPending, saveError, saveOk,
}: {
  s: Shipment;
  onUpdate: (p: Partial<Shipment>) => void;
  isPending: boolean;
  saveError: string | null;
  saveOk: number;
}) {
  const [form, setForm] = useState<Partial<Shipment>>(s);
  const set = (k: keyof Shipment, v: any) => setForm((f) => ({ ...f, [k]: v }));
  const ov = s.manual_overrides;
  useEffect(() => { setForm(s); }, [s.updated_at, s.id]);
  return (
    <Section title="ניירת ועלויות">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div data-field="invoice_number">
          <label className="label flex items-center gap-1.5">
            <span>Invoice</span>
            <OverridePill overrides={ov} field="invoice_number" />
          </label>
          <input className="input" value={form.invoice_number || ""} onChange={(e) => set("invoice_number", e.target.value)} />
        </div>
        <div data-field="po_number">
          <label className="label flex items-center gap-1.5">
            <span>PO</span>
            <OverridePill overrides={ov} field="po_number" />
          </label>
          <input className="input" value={form.po_number || ""} onChange={(e) => set("po_number", e.target.value)} />
        </div>
        <div>
          <label className="label">סטטוס אישור</label>
          <input className="input" value={form.approval_status || ""} onChange={(e) => set("approval_status", e.target.value)} />
        </div>
        <div>
          <label className="label">ערך סחורה (USD)</label>
          <input className="input" type="number" value={form.goods_value_usd ?? ""} onChange={(e) => set("goods_value_usd", e.target.value ? Number(e.target.value) : null)} />
        </div>
        <div>
          <label className="label">עלות הובלה (USD)</label>
          <input className="input" type="number" value={form.freight_price_usd ?? ""} onChange={(e) => set("freight_price_usd", e.target.value ? Number(e.target.value) : null)} />
        </div>
      </div>
      <SaveBar
        isPending={isPending}
        saveError={saveError}
        saveOk={saveOk}
        canSave={hasPermission("shipment.update")}
        onSave={() => onUpdate(form)}
      />
    </Section>
  );
}

/**
 * Reusable save-button row with explicit feedback:
 *   - shows a spinner + "שומר..." while the mutation is pending
 *   - red banner with the backend message on error (NOT silent anymore)
 *   - green confirmation badge for ~3 sec after each successful save
 */
function SaveBar({
  isPending, saveError, saveOk, canSave, onSave,
}: {
  isPending: boolean;
  saveError: string | null;
  saveOk: number;
  canSave: boolean;
  onSave: () => void;
}) {
  const [showOk, setShowOk] = useState(false);
  useEffect(() => {
    if (saveOk > 0) {
      setShowOk(true);
      const t = setTimeout(() => setShowOk(false), 3000);
      return () => clearTimeout(t);
    }
  }, [saveOk]);

  if (!canSave) {
    return (
      <div className="mt-4 text-xs text-slate-500">
        צפייה בלבד — אין הרשאת עריכה
      </div>
    );
  }
  return (
    <div className="mt-4 space-y-2">
      {saveError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          ❌ {saveError}
        </div>
      )}
      {showOk && !saveError && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          ✓ נשמר בהצלחה
        </div>
      )}
      <div className="flex gap-2 justify-end">
        <button
          className="btn-primary"
          onClick={onSave}
          disabled={isPending}
        >
          {isPending ? "שומר..." : "שמור"}
        </button>
      </div>
    </div>
  );
}


function SmartDocStatusPanel({
  status, loading, onRecalc, recalcing,
}: {
  status: SmartDocStatus | undefined;
  loading: boolean;
  onRecalc: () => void;
  recalcing: boolean;
}) {
  if (loading || !status) {
    return (
      <div className="mb-3 text-xs text-slate-500">טוען סטטוס מסמכים...</div>
    );
  }
  const types: Array<"invoice" | "packing_list" | "bl"> = ["invoice", "packing_list", "bl"];
  const labels: Record<string, string> = {
    invoice: "Invoice",
    packing_list: "Packing List",
    bl: "BL / BOL",
  };
  return (
    <div className="mb-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="text-sm font-semibold text-slate-800">סטטוס מסמכים</div>
          <div className="text-[11px] text-slate-500">
            מבוסס על סיווג אוטומטי של המסמכים שמקושרים למשלוח.
            {status.noise_filtered_count > 0 &&
              ` ${status.noise_filtered_count} קבצים סוננו כרעש מייל.`}
          </div>
        </div>
        <button
          onClick={onRecalc}
          disabled={recalcing}
          className="btn-secondary text-xs px-3 py-1.5"
        >
          {recalcing ? "מנתח..." : "🔄 נתח מסמכים מחדש"}
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {types.map((t) => {
          const info = status.by_type[t];
          if (!info) return null;
          const tone =
            info.status === "data_extracted" ? "border-emerald-300 bg-emerald-50"
            : info.status === "document_exists" ? "border-blue-300 bg-blue-50"
            : info.status === "missing" ? "border-amber-300 bg-amber-50"
            : "border-slate-200 bg-white";
          const icon =
            info.status === "data_extracted" ? "✅"
            : info.status === "document_exists" ? "📄"
            : info.status === "missing" ? "⚠"
            : "•";
          return (
            <div key={t} className={clsx("rounded-lg border p-2 text-xs", tone)}>
              <div className="font-semibold text-slate-800 flex items-center gap-1">
                <span>{icon}</span>
                <span>{labels[t]}</span>
              </div>
              <div className="text-[11px] text-slate-700 mt-0.5">
                {info.label_he}
              </div>
              {info.documents.length > 0 && (
                <div className="text-[10px] text-slate-500 mt-1 truncate"
                     title={info.documents.map(d => d.filename || "").join("\n")}>
                  {info.documents.length === 1
                    ? `מסמך: ${info.documents[0].filename}`
                    : `${info.documents.length} מסמכים`}
                </div>
              )}
              {info.shipment_field_value && (
                <div className="text-[10px] text-emerald-700 mt-0.5 font-mono truncate">
                  ערך: {info.shipment_field_value}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {status.other_documents && status.other_documents.length > 0 && (
        <div className="text-[10px] text-slate-600 mt-2 pt-2 border-t border-slate-200">
          מסמכים נוספים: {status.other_documents.length} (PO, Customs, Certificate, …)
        </div>
      )}
    </div>
  );
}
