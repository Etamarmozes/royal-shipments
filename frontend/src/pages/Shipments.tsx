import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listShipments } from "../api/endpoints";
import { PageHeader, Loader, ErrorState, EmptyState } from "../components/common";
import { fmtDate, fmtDateTime, stageLabel } from "../utils/format";
import AuthedImage from "../components/AuthedImage";

export default function Shipments() {
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState<string>("");
  const [delayOnly, setDelayOnly] = useState(false);
  const [paperworkMissing, setPaperworkMissing] = useState(false);
  const [extraWorkOnly, setExtraWorkOnly] = useState(false);

  const params: Record<string, any> = { archived: false };
  if (search) params.search = search;
  if (stage) params.stage = Number(stage);
  if (delayOnly) params.delay = true;
  if (paperworkMissing) params.paperwork_missing = true;
  if (extraWorkOnly) params.extra_work_only = true;

  const q = useQuery({
    queryKey: ["shipments", params],
    queryFn: () => listShipments(params),
  });

  return (
    <div>
      <PageHeader
        title="משלוחים פעילים"
        subtitle="כל המשלוחים שנמצאים בתהליך"
        actions={
          <Link className="btn-primary" to="/shipments/new">
            משלוח חדש
          </Link>
        }
      />

      <div className="card mb-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        <div>
          <label className="label">חיפוש</label>
          <input
            className="input"
            placeholder="SHP / ספק / מכולה / בוקינג / BOL"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div>
          <label className="label">שלב</label>
          <select className="input" value={stage} onChange={(e) => setStage(e.target.value)}>
            <option value="">הכל</option>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
              <option key={n} value={n}>
                {stageLabel(n)}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 mt-7">
          <input type="checkbox" checked={delayOnly} onChange={(e) => setDelayOnly(e.target.checked)} />
          <span className="text-sm">בעיכוב בלבד</span>
        </label>
        <label className="flex items-center gap-2 mt-7">
          <input
            type="checkbox"
            checked={paperworkMissing}
            onChange={(e) => setPaperworkMissing(e.target.checked)}
          />
          <span className="text-sm">ניירת חסרה</span>
        </label>
        <label className="flex items-center gap-2 mt-7">
          <input
            type="checkbox"
            checked={extraWorkOnly}
            onChange={(e) => setExtraWorkOnly(e.target.checked)}
          />
          <span className="text-sm">תוספת עבודה</span>
        </label>
      </div>

      {q.isLoading ? (
        <Loader />
      ) : q.isError ? (
        <ErrorState error={q.error} />
      ) : !q.data || q.data.items.length === 0 ? (
        // No filters active → "system clean" framing.
        // Filters active → "no matches" framing.
        (search || stage || delayOnly || paperworkMissing || extraWorkOnly) ? (
          <EmptyState
            iconName="search"
            title="אין משלוחים תואמים לסינון"
            description="נסה להסיר חלק מהמסננים, או חפש בערך אחר."
          />
        ) : (
          <EmptyState
            iconName="carton"
            title="אין משלוחים פעילים"
            description="המערכת נקייה. כדי להתחיל — ייבא קובץ Excel של ספק / Eli Line / ICL."
            action={{ label: "ייבוא Excel", to: "/import-excel" }}
          />
        )
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="min-w-full table-dense">
            <thead>
              <tr>
                <th className="text-right w-12"></th>
                <th className="text-right">SHP</th>
                <th className="text-right">ספק</th>
                <th className="text-right">תיאור</th>
                <th className="text-right">מקור</th>
                <th className="text-right">שלב</th>
                <th className="text-right num">ETA לארץ</th>
                <th className="text-right num">מכולות</th>
                <th className="text-right">ניירת</th>
                <th className="text-right">סטטוס</th>
                <th className="text-right">תוספת</th>
                <th className="text-right num">עדכון אחרון</th>
              </tr>
            </thead>
            <tbody>
              {q.data.items.map((s) => (
                <tr key={s.id}>
                  <td>
                    {s.product_image_path ? (
                      <Link to={`/shipments/${s.id}`}>
                        <AuthedImage
                          path={`/shipments/${s.id}/product-image?t=${encodeURIComponent(s.updated_at || "")}`}
                          alt=""
                          className="w-9 h-9 rounded-md object-cover bg-slate-100"
                          fallback={<div className="w-9 h-9 rounded-md bg-slate-100" />}
                        />
                      </Link>
                    ) : (
                      <div className="w-9 h-9 rounded-md bg-slate-100" />
                    )}
                  </td>
                  <td className="font-semibold">
                    <Link className="text-brand-600 ltr-token" to={`/shipments/${s.id}`}>
                      {s.shp_id}
                    </Link>
                  </td>
                  <td>
                    <span className="cell-truncate" title={s.supplier || ""}>{s.supplier || "—"}</span>
                  </td>
                  <td className="text-slate-600">
                    <span className="cell-truncate" title={s.goods_description || ""}>
                      {s.goods_description || "—"}
                    </span>
                  </td>
                  <td className="text-slate-500 text-[11px]">{s.origin_country || "—"}</td>
                  <td>{stageLabel(s.current_stage)}</td>
                  <td className="num">{fmtDate(s.eta_israel)}</td>
                  <td className="num">{s.container_count || 0}</td>
                  <td>
                    {s.paperwork_complete ? (
                      <span className="badge-green">מלאה</span>
                    ) : (
                      <span className="badge-amber">חסרה</span>
                    )}
                  </td>
                  <td>
                    {s.delay_status ? <span className="badge-red">מתעכב</span> : <span className="text-slate-400">—</span>}
                  </td>
                  <td>
                    {s.extra_work_required ? <span className="badge-purple">נדרשת</span> : <span className="text-slate-400">—</span>}
                  </td>
                  <td className="num text-[11px] text-slate-500">
                    {fmtDateTime(s.updated_at)}
                    {s.last_update_source && (
                      <div className="text-[10px] text-slate-400">
                        מקור: {s.last_update_source}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
