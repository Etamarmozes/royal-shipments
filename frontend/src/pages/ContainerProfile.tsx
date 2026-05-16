import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getContainer, updateContainer, getPalletBreakdown, calculatePallets,
  containerDataQuality,
} from "../api/endpoints";
import { PageHeader, Loader, ErrorState, Section } from "../components/common";
import { DataQualityBadge, MissingDataPanel, OverridePill } from "../components/DataQuality";
import { hasPermission } from "../auth/store";
import { fmtDate, fmtNumber } from "../utils/format";
import type { Container } from "../types";
import clsx from "clsx";

export default function ContainerProfile() {
  const { id } = useParams();
  const cid = Number(id);
  const qc = useQueryClient();

  const cQuery = useQuery({
    queryKey: ["container", cid],
    queryFn: () => getContainer(cid),
    enabled: !Number.isNaN(cid),
  });
  const breakdownQuery = useQuery({
    queryKey: ["pallet-breakdown", cid],
    queryFn: () => getPalletBreakdown(cid),
    enabled: !Number.isNaN(cid),
  });
  const quality = useQuery({
    queryKey: ["container-quality", cid],
    queryFn: () => containerDataQuality(cid),
    enabled: !Number.isNaN(cid),
  });

  const focusField = (field: string) => {
    setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-field="${field}"]`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        const input = el.querySelector("input,select,textarea") as HTMLElement | null;
        input?.focus();
      }
    }, 100);
  };

  const [form, setForm] = useState<Partial<Container>>({});
  useEffect(() => {
    if (cQuery.data) {
      setForm({
        carton_length_cm: cQuery.data.carton_length_cm,
        carton_width_cm: cQuery.data.carton_width_cm,
        carton_height_cm: cQuery.data.carton_height_cm,
        pallet_type_preference: cQuery.data.pallet_type_preference || "auto",
        boxes_total: cQuery.data.boxes_total,
      });
    }
  }, [cQuery.data]);

  const save = useMutation({
    mutationFn: (payload: Partial<Container>) => updateContainer(cid, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["container", cid] });
      qc.invalidateQueries({ queryKey: ["pallet-breakdown", cid] });
      qc.invalidateQueries({ queryKey: ["containers"] });
    },
  });
  const recalc = useMutation({
    mutationFn: () => calculatePallets(cid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["container", cid] });
      qc.invalidateQueries({ queryKey: ["pallet-breakdown", cid] });
      qc.invalidateQueries({ queryKey: ["containers"] });
    },
  });

  if (cQuery.isLoading) return <Loader />;
  if (cQuery.isError) return <ErrorState error={cQuery.error} />;
  if (!cQuery.data) return null;
  const c = cQuery.data;
  const b = breakdownQuery.data;

  return (
    <div>
      <PageHeader
        title={`מכולה ${c.container_number || c.id}`}
        subtitle={`${c.container_type || ""} ${c.shipment_shp_id ? `• ${c.shipment_shp_id}` : ""} ${c.supplier ? `• ${c.supplier}` : ""}`}
        actions={
          <>
            <Link
              className="btn-primary"
              to={`/receiving?container=${c.id}`}
            >
              📥 קליטה במחסן
            </Link>
            <Link className="btn-secondary" to={`/shipments/${c.shipment_id}`}>
              למשלוח →
            </Link>
            <Link className="btn-secondary" to="/containers-in-transit">
              חזרה לרשימה
            </Link>
          </>
        }
      />

      <div className="mb-4 flex items-center gap-2 flex-wrap">
        <DataQualityBadge type="container" id={c.id} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-4">
        <Mini label="קופסאות" value={fmtNumber(c.boxes_total)} />
        <Mini label="CBM" value={c.cbm != null ? c.cbm.toString() : "—"} />
        <Mini label="משקל (ק״ג)" value={fmtNumber(c.gross_weight_kg)} />
        <Mini label="ETA לארץ" value={fmtDate(c.effective_eta_israel)} />
        <Mini label="סטטוס" value={c.container_status || "—"} />
        <Mini label="עדיפות" value={c.unloading_priority || "—"} />
      </div>

      {quality.data && quality.data.score !== "complete" && (
        <div className="mb-4">
          <MissingDataPanel quality={quality.data} onFix={focusField} />
        </div>
      )}

      <Section
        title="חישוב משטחים"
        action={
          <button
            className="btn-secondary"
            onClick={() => recalc.mutate()}
            disabled={recalc.isPending}
          >
            {recalc.isPending ? "מחשב..." : "חשב מחדש"}
          </button>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Inputs */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">קלט</h3>
            <div className="grid grid-cols-2 gap-3">
              <div data-field="carton_length_cm">
                <label className="label flex items-center gap-1.5">
                  <span>אורך קרטון (ס״מ)</span>
                  <OverridePill overrides={c.manual_overrides} field="carton_length_cm" />
                </label>
                <input
                  type="number" step="0.1" className="input"
                  value={form.carton_length_cm ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, carton_length_cm: e.target.value ? Number(e.target.value) : null }))}
                />
              </div>
              <div data-field="carton_width_cm">
                <label className="label flex items-center gap-1.5">
                  <span>רוחב קרטון (ס״מ)</span>
                  <OverridePill overrides={c.manual_overrides} field="carton_width_cm" />
                </label>
                <input
                  type="number" step="0.1" className="input"
                  value={form.carton_width_cm ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, carton_width_cm: e.target.value ? Number(e.target.value) : null }))}
                />
              </div>
              <div data-field="carton_height_cm">
                <label className="label flex items-center gap-1.5">
                  <span>גובה קרטון (ס״מ)</span>
                  <OverridePill overrides={c.manual_overrides} field="carton_height_cm" />
                </label>
                <input
                  type="number" step="0.1" className="input"
                  value={form.carton_height_cm ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, carton_height_cm: e.target.value ? Number(e.target.value) : null }))}
                />
              </div>
              <div data-field="boxes_total">
                <label className="label flex items-center gap-1.5">
                  <span>כמות קרטונים</span>
                  <OverridePill overrides={c.manual_overrides} field="boxes_total" />
                </label>
                <input
                  type="number" className="input"
                  value={form.boxes_total ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, boxes_total: e.target.value ? Number(e.target.value) : null }))}
                />
              </div>
              <div className="col-span-2">
                <label className="label">העדפת משטח</label>
                <select
                  className="input"
                  value={(form.pallet_type_preference as string) || "auto"}
                  onChange={(e) => setForm((f) => ({ ...f, pallet_type_preference: e.target.value }))}
                >
                  <option value="auto">אוטומטי (פחות משטחים, Euro על שוויון)</option>
                  <option value="euro">Euro (120×80)</option>
                  <option value="industrial">תעשייתי (120×100)</option>
                </select>
              </div>
            </div>
            {b && (
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs bg-slate-50 rounded-lg p-3">
                <div className="flex justify-between">
                  <span className="text-slate-500">גובה כולל מותר:</span>
                  <span className="font-semibold">{b.max_total_height_cm ?? 160} ס״מ</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">גובה משטח:</span>
                  <span className="font-semibold">{b.pallet_height_cm ?? 15} ס״מ</span>
                </div>
                <div className="flex justify-between col-span-2">
                  <span className="text-slate-500">גובה זמין לקרטונים:</span>
                  <span className="font-semibold">
                    {b.available_carton_height_cm ?? 145} ס״מ
                  </span>
                </div>
              </div>
            )}
            <div className="mt-3 flex gap-2">
              {hasPermission("container.update") ? (
                <button
                  className="btn-primary"
                  onClick={() => save.mutate(form)}
                  disabled={save.isPending}
                >
                  {save.isPending ? "שומר..." : "שמור וחשב"}
                </button>
              ) : (
                <div className="text-xs text-slate-500">צפייה בלבד — אין הרשאת עריכה</div>
              )}
            </div>
          </div>

          {/* Breakdown */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">פלט</h3>
            {!b ? (
              <Loader />
            ) : (
              <BreakdownCard breakdown={b} />
            )}
          </div>
        </div>
      </Section>
    </div>
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

function BreakdownCard({ breakdown }: { breakdown: any }) {
  const b = breakdown;
  if (b.method === "insufficient_data") {
    return (
      <div className="card border-amber-300 bg-amber-50">
        <div className="font-semibold text-amber-900">חסר מידע לחישוב</div>
        <div className="text-sm text-amber-800 mt-1">
          חסרות מידות קרטון ו-CBM. הזן מידות + כמות קרטונים, או לפחות CBM.
        </div>
      </div>
    );
  }
  if (b.method === "cbm_fallback") {
    return (
      <div className="card border-blue-300 bg-blue-50">
        <div className="font-semibold text-blue-900">חישוב לפי CBM (fallback)</div>
        <div className="text-sm text-blue-800 mt-1">
          ⌈{b.cartons_total != null ? `${b.cartons_total} קרטונים, ` : ""}{(b.notes || "").replace("Calculated by CBM fallback.", "")}
        </div>
        <div className="mt-3 text-3xl font-bold text-blue-900">
          {b.estimated_pallets_final} משטחים
        </div>
        <div className="text-xs text-blue-700 mt-1">
          המלצה משטח: לא נקבע (חסרות מידות) — Calculated by CBM fallback
        </div>
      </div>
    );
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <PalletDetailCard
          title="Euro 120×80"
          detail={b.euro}
          isRecommended={b.recommended_pallet_type === "euro"}
        />
        <PalletDetailCard
          title="תעשייתי 120×100"
          detail={b.industrial}
          isRecommended={b.recommended_pallet_type === "industrial"}
        />
      </div>
      <div className="card mt-3 border-emerald-300 bg-emerald-50">
        <div className="text-xs text-emerald-700">המלצה סופית</div>
        <div className="text-2xl font-bold text-emerald-900 mt-1">
          {b.estimated_pallets_final ?? "—"} משטחים
          {b.recommended_pallet_type && (
            <span className="text-base font-semibold mr-2">
              ({b.recommended_pallet_type === "euro" ? "Euro" : "תעשייתי"})
            </span>
          )}
        </div>
      </div>
      <div className="text-xs text-slate-500 mt-2 whitespace-pre-line">{b.notes}</div>
    </>
  );
}

function PalletDetailCard({
  title, detail, isRecommended,
}: {
  title: string;
  detail: any;
  isRecommended: boolean;
}) {
  const ok = detail && detail.pallets_needed != null;
  return (
    <div className={clsx("card", isRecommended ? "border-emerald-400 bg-emerald-50" : "")}>
      <div className="flex items-center justify-between">
        <div className="font-semibold">{title}</div>
        {isRecommended && <span className="badge-green">מומלץ</span>}
      </div>
      {ok ? (
        <>
          <div className="text-sm text-slate-600 mt-2">
            {detail.cartons_per_layer} בשכבה × {detail.layers} שכבות = <b>{detail.cartons_per_pallet}</b> קרטונים/משטח
          </div>
          {detail.total_loaded_height_cm != null && (
            <div className="text-xs text-slate-500 mt-1">
              גובה כולל בפועל: <b>{Math.round(detail.total_loaded_height_cm)}</b> ס״מ
              {" "}
              <span className="text-slate-400">
                ({detail.pallet_height_cm} משטח + {Math.round(detail.cartons_stack_height_cm ?? 0)} קרטונים)
              </span>
            </div>
          )}
          <div className="text-2xl font-bold mt-2">{detail.pallets_needed} משטחים</div>
        </>
      ) : (
        <div className="text-sm text-amber-800 mt-2">
          {detail?.note || "לא ניתן לחשב"}
        </div>
      )}
    </div>
  );
}
