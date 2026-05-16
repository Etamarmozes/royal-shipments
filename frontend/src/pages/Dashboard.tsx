import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  dashboardKpis, dashboardPalletKpis, listContainers, listShipments,
  listEmailUpdates, gmailStatus, gmailSync, processFetchedEmails,
  listAlerts, listDocuments, gmailConnectUrl,
} from "../api/endpoints";
import { downloadAuthed } from "../utils/fileAccess";
import { Loader } from "../components/common";
import ArrivalsTimeline from "../components/ArrivalsTimeline";
import { Icon } from "../components/Icon";
import { fmtDate, fmtDateTime, fmtNumber } from "../utils/format";
import clsx from "clsx";

const DAYS_AHEAD = 30;

export default function Dashboard() {
  const qc = useQueryClient();
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: dashboardKpis });
  const palletKpis = useQuery({ queryKey: ["pallet-kpis"], queryFn: dashboardPalletKpis });
  const containers = useQuery({ queryKey: ["containers"], queryFn: () => listContainers() });
  const ships = useQuery({
    queryKey: ["shipments-active"],
    queryFn: () => listShipments({ archived: false, limit: 500 }),
  });
  const emails = useQuery({ queryKey: ["recent-emails"], queryFn: () => listEmailUpdates({}) });
  const gmail = useQuery({ queryKey: ["gmail-status"], queryFn: gmailStatus });
  const docs = useQuery({ queryKey: ["unassigned-docs"], queryFn: () => listDocuments({ unassigned: true }) });

  const sync = useMutation({ mutationFn: gmailSync, onSuccess: () => qc.invalidateQueries() });
  const parseFetched = useMutation({ mutationFn: processFetchedEmails, onSuccess: () => qc.invalidateQueries() });

  // Build "30 days ahead arrivals" sorted by best ETA available
  const arrivals = useMemo(() => {
    const todayStr = new Date().toISOString().slice(0, 10);
    const end = new Date();
    end.setDate(end.getDate() + DAYS_AHEAD);
    const endStr = end.toISOString().slice(0, 10);
    const rows: Array<{
      eta: string; container_number?: string | null; container_id?: number;
      shipment_id: number; shp_id?: string | null; supplier?: string | null;
      category?: string | null; goods?: string | null; pallets?: number | null;
      delay: boolean; eta_changed?: boolean; needs_review?: boolean;
      last_update_source?: string | null; updated_at?: string | null;
      etd?: string | null;
    }> = [];

    for (const c of containers.data || []) {
      const s = (ships.data?.items || []).find((x) => x.id === c.shipment_id);
      if (!s || s.archived) continue;
      // Best date: warehouse → port → israel → etd
      const best = c.eta_warehouse || s.eta_warehouse
        || c.eta_port || s.eta_port
        || c.eta_israel || s.eta_israel
        || s.etd;
      if (!best) continue;
      if (best < todayStr || best > endStr) continue;
      rows.push({
        eta: best,
        container_number: c.container_number,
        container_id: c.id,
        shipment_id: s.id,
        shp_id: s.shp_id,
        supplier: s.supplier,
        category: c.effective_category || s.category || null,
        goods: s.goods_description,
        pallets: c.estimated_pallets_final,
        delay: !!s.delay_status,
        last_update_source: s.last_update_source,
        updated_at: s.updated_at,
      });
    }
    rows.sort((a, b) => (a.eta < b.eta ? -1 : 1));
    return rows;
  }, [containers.data, ships.data]);

  // Containers with NO ETA at all
  const missingEtaContainers = useMemo(
    () => (containers.data || []).filter((c) => !c.effective_eta_israel && !c.actual_arrival_warehouse),
    [containers.data]
  );

  return (
    <div className="max-w-7xl mx-auto pb-24">
      {/* Hero */}
      <header className="mb-8">
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-slate-900">
          תמונת מצב משלוחים
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
          <span>{fmtDateTime(new Date().toISOString())}</span>
          <span className="text-slate-300">•</span>
          <span>
            סנכרון אחרון: {kpis.data?.last_email_sync_at ? fmtDateTime(kpis.data.last_email_sync_at) : "לא בוצע"}
          </span>
          <span className="text-slate-300">•</span>
          {gmail.data?.connected ? (
            <span className="inline-flex items-center gap-1 text-emerald-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500" /> Gmail מחובר
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-amber-700">
              <span className="w-2 h-2 rounded-full bg-amber-500" /> Gmail לא מחובר
            </span>
          )}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {gmail.data?.disabled ? (
            <button className="btn-secondary opacity-60 cursor-not-allowed" disabled
                    title={gmail.data.disabled_reason}>
              Gmail כבוי
            </button>
          ) : gmail.data?.connected ? (
            <button className="btn-primary" onClick={() => sync.mutate()} disabled={sync.isPending}>
              {sync.isPending ? "מסנכרן..." : "Sync Gmail"}
            </button>
          ) : (
            <a className="btn-primary" href={gmailConnectUrl()}>חבר Gmail</a>
          )}
          <button
            className="btn-secondary"
            onClick={() => parseFetched.mutate()}
            disabled={parseFetched.isPending}
          >
            {parseFetched.isPending ? "מנתח..." : "נתח מיילים שנכנסו"}
          </button>
          <button
            className="btn-secondary"
            onClick={() => downloadAuthed("/export/excel", "royal_linen_shipments.xlsx")}
          >
            ייצוא לאקסל
          </button>
        </div>
      </header>

      {/* Clean-system hero — only when DB looks empty (no active shipments, no containers).
          Gives Itamar / Adi an obvious "next step" right after a reset. */}
      {!kpis.isLoading && !ships.isLoading && !containers.isLoading
       && (kpis.data?.active_shipments ?? 0) === 0
       && (containers.data?.length ?? 0) === 0 && (
        <div className="rounded-xl border-2 border-dashed border-brand-200 bg-brand-50/40 p-6 mb-6 text-center">
          <div className="flex items-center justify-center mb-3">
            <Icon name="check" size={36} className="text-emerald-500" />
          </div>
          <div className="text-lg font-bold text-slate-800">המערכת נקייה</div>
          <div className="text-sm text-slate-600 mt-1 max-w-xl mx-auto">
            אין כרגע משלוחים פעילים, מכולות, מסמכים או התראות.
            {gmail.data?.disabled && <> סנכרון Gmail כבוי. </>}
            הצעד הבא: ייבוא Excel ראשון של ICL / Eli Line.
          </div>
          <div className="mt-4 inline-flex flex-wrap items-center justify-center gap-2">
            <Link to="/import-excel" className="btn-primary inline-flex items-center gap-2">
              <Icon name="excel" size={16}/>
              <span>ייבוא Excel</span>
            </Link>
            <Link to="/help/supplier" className="btn-secondary inline-flex items-center gap-2">
              <Icon name="info" size={16}/>
              <span>מדריך לספקים</span>
            </Link>
          </div>
          <div className="mt-3 text-xs text-slate-500 inline-flex flex-wrap items-center justify-center gap-2">
            <span className="inline-flex items-center gap-1"><Icon name="carton" size={12}/> 0 משלוחים</span>
            <span className="text-slate-300">•</span>
            <span className="inline-flex items-center gap-1"><Icon name="container" size={12}/> 0 מכולות</span>
            <span className="text-slate-300">•</span>
            <span className="inline-flex items-center gap-1"><Icon name="document" size={12}/> 0 מסמכים</span>
            <span className="text-slate-300">•</span>
            <span className="inline-flex items-center gap-1"><Icon name="alert" size={12}/> 0 התראות</span>
          </div>
        </div>
      )}

      {/* Gmail disabled / disconnected banner — work continues, only auto-sync is paused */}
      {gmail.data && (gmail.data.disabled || !gmail.data.connected) && (
        <div className={clsx(
          "rounded-xl border px-4 py-3 mb-4 text-sm flex items-start gap-2",
          gmail.data.disabled
            ? "bg-slate-50 border-slate-200 text-slate-700"
            : "bg-amber-50 border-amber-200 text-amber-800"
        )}>
          <Icon name={gmail.data.disabled ? "lock" : "alert"} size={18} className="mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold">
              {gmail.data.disabled
                ? "Gmail מנותק זמנית"
                : "Gmail לא מחובר"}
            </div>
            <div className="text-xs mt-0.5">
              {gmail.data.disabled_reason
                || "סנכרון אוטומטי מהמייל מושבת. המערכת ממשיכה לעבוד במצב ידני — ניתן להוסיף, לערוך, ולקלוט סחורה רגיל."}
            </div>
          </div>
        </div>
      )}

      {/* Clickable KPIs — 2 cols on phone, 4 on tablet, 8 on desktop */}
      <section className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-8 gap-3 mb-8">
        <KpiLink label="מכולות בדרך" value={kpis.data?.total_containers_in_transit ?? 0} to="/containers-in-transit" />
        <KpiLink label="משטחים 30 יום" value={palletKpis.data?.pallets_next_7_days ?? 0} to="/forecast-daily" tone="info" hint="(שבוע)" />
        <KpiLink label="מגיע השבוע" value={palletKpis.data?.containers_next_7_days ?? 0} to="/containers-in-transit" />
        <KpiLink label="עיכובים" value={kpis.data?.delayed_shipments ?? 0} to="/shipments?delay=1"
          tone={kpis.data?.delayed_shipments ? "danger" : "default"} />
        <KpiLink label="חסר מידע" value={palletKpis.data?.containers_missing_carton_dimensions ?? 0}
          to="/containers-in-transit" tone="warning" />
        <KpiLink label="חסרים מסמכים" value={docs.data?.length ?? 0} to="/documents"
          tone={(docs.data?.length || 0) > 0 ? "warning" : "default"} />
        <KpiLink label="קטגוריות בדרך" value={uniqueCategories(arrivals)} to="/categories" tone="info" />
        <KpiLink label="עודכן אוטו׳ היום" value={kpis.data?.auto_applied_email_updates_today ?? 0}
          to="/email-updates" tone="success" />
      </section>

      {/* Visual Timeline */}
      <Block
        title="Timeline הגעות — 30 יום קדימה"
        subtitle="ETD → נמל → ארץ → מחסן"
        action={<Link to="/containers-in-transit" className="text-brand-600 text-sm">למסך מכולות בדרך →</Link>}
      >
        {containers.isLoading || ships.isLoading ? <Loader /> : (
          <ArrivalsTimeline
            shipments={ships.data?.items || []}
            containers={containers.data || []}
            daysAhead={DAYS_AHEAD}
          />
        )}
      </Block>

      {/* 30-day arrivals list */}
      <Block
        title="סטטוס הגעות — 30 יום קדימה"
        subtitle="הקרוב למעלה. Date / Container / Supplier / Category / Pallets / Status"
      >
        {arrivals.length === 0 ? (
          <div className="text-sm text-slate-500 py-3">אין הגעות ב-30 הימים הקרובים</div>
        ) : (
          <>
          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {arrivals.slice(0, 30).map((r) => (
              <Link
                key={`${r.shipment_id}-${r.container_id}`}
                to={`/shipments/${r.shipment_id}`}
                className="block bg-white border border-slate-200 rounded-xl p-3 active:bg-slate-50"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-semibold text-brand-700">{r.shp_id}</div>
                    {r.container_number && (
                      <div className="text-[11px] font-mono text-slate-500 truncate">{r.container_number}</div>
                    )}
                    <div className="text-xs text-slate-700 truncate mt-1">{r.supplier || "—"}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-[10px] text-slate-500">תאריך</div>
                    <div className="font-medium text-sm">{fmtDate(r.eta)}</div>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {r.category && <span className="badge-blue">{r.category}</span>}
                  {r.pallets != null && <span className="text-xs text-slate-600">{r.pallets} משטחים</span>}
                  {r.delay ? <span className="badge-red">עיכוב</span> : <span className="badge-green">תקין</span>}
                  {r.last_update_source === "email" && <span className="badge-blue text-[9px]">email</span>}
                </div>
              </Link>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr className="border-b border-slate-100">
                  <th className="text-right py-2 px-3 font-medium">תאריך</th>
                  <th className="text-right py-2 px-3 font-medium">SHP / מכולה</th>
                  <th className="text-right py-2 px-3 font-medium">ספק</th>
                  <th className="text-right py-2 px-3 font-medium">קטגוריה</th>
                  <th className="text-right py-2 px-3 font-medium">משטחים</th>
                  <th className="text-right py-2 px-3 font-medium">סטטוס</th>
                  <th className="text-right py-2 px-3 font-medium">עדכון אחרון</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {arrivals.slice(0, 30).map((r) => (
                  <tr key={`${r.shipment_id}-${r.container_id}`} className="hover:bg-slate-50">
                    <td className="py-2 px-3 font-medium text-slate-900">{fmtDate(r.eta)}</td>
                    <td className="py-2 px-3">
                      <Link to={`/shipments/${r.shipment_id}`} className="text-brand-600 font-medium">
                        {r.shp_id}
                      </Link>
                      {r.container_number && (
                        <span className="text-xs text-slate-500 mr-2 font-mono">{r.container_number}</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-slate-700">{r.supplier || "—"}</td>
                    <td className="py-2 px-3">
                      {r.category ? (
                        <span className="badge-blue">{r.category}</span>
                      ) : (
                        <span className="text-slate-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="py-2 px-3 tabular-nums">{r.pallets ?? "—"}</td>
                    <td className="py-2 px-3">
                      {r.delay ? (
                        <span className="badge-red">עיכוב</span>
                      ) : (
                        <span className="badge-green">תקין</span>
                      )}
                    </td>
                    <td className="py-2 px-3 text-xs text-slate-500">
                      {r.updated_at ? fmtDate(r.updated_at) : "—"}
                      {r.last_update_source === "email" && (
                        <span className="badge-blue mr-1 text-[9px]">email</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </Block>

      {/* Missing ETA */}
      {missingEtaContainers.length > 0 && (
        <Block title="חסר תאריך" subtitle="מכולות בלי ETA — לא נכנסות לטיימליין">
          <ul className="divide-y divide-slate-100">
            {missingEtaContainers.map((c) => (
              <li key={c.id} className="py-2 flex items-center justify-between text-sm">
                <Link to={`/containers/${c.id}`} className="font-mono text-brand-600">
                  {c.container_number}
                </Link>
                <span className="text-slate-500">
                  {c.shipment_shp_id} • {c.supplier}
                </span>
              </li>
            ))}
          </ul>
        </Block>
      )}

      {/* Email activity */}
      <Block
        title="עדכוני מייל אחרונים"
        action={<Link to="/email-updates" className="text-brand-600 text-sm">לכל המיילים →</Link>}
      >
        <ul className="divide-y divide-slate-100">
          {(emails.data || []).slice(0, 5).map((u) => (
            <li key={u.id} className="py-2 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs text-slate-500">
                  {fmtDateTime(u.received_at)} • {u.sender}
                </div>
                <div className="text-sm font-medium text-slate-800 truncate">{u.subject}</div>
              </div>
              <div className="shrink-0 text-xs">
                {u.auto_applied ? <span className="badge-green">עודכן אוטומטית</span>
                  : u.needs_review ? <span className="badge-red">דורש בדיקה</span>
                  : u.detection_type === "new_shipment" ? <span className="badge-purple">משלוח חדש</span>
                  : <span className="badge-gray">{u.status}</span>}
              </div>
            </li>
          ))}
          {!emails.data?.length && <li className="py-3 text-center text-slate-500 text-sm">אין מיילים</li>}
        </ul>
      </Block>
    </div>
  );
}

function uniqueCategories(rows: Array<{ category?: string | null }>): number {
  const set = new Set(rows.map((r) => r.category).filter(Boolean));
  return set.size;
}

function KpiLink({
  label, value, to, tone = "default", hint,
}: {
  label: string;
  value: number | string;
  to: string;
  tone?: "default" | "info" | "success" | "warning" | "danger";
  hint?: string;
}) {
  const ring = {
    default: "border-slate-200 hover:border-slate-300",
    info: "border-blue-200 hover:border-blue-300",
    success: "border-emerald-200 hover:border-emerald-300",
    warning: "border-amber-300 hover:border-amber-400",
    danger: "border-red-300 hover:border-red-400",
  }[tone];
  const valColor = {
    default: "text-slate-900",
    info: "text-blue-700",
    success: "text-emerald-700",
    warning: "text-amber-800",
    danger: "text-red-700",
  }[tone];
  return (
    <Link
      to={to}
      className={clsx(
        "bg-white rounded-2xl border p-4 transition group",
        ring,
      )}
    >
      <div className="text-[11px] font-medium text-slate-500 tracking-wide">{label}</div>
      <div className={clsx("text-3xl font-semibold mt-1 tabular-nums", valColor)}>
        {typeof value === "number" ? fmtNumber(value) : value}
      </div>
      {hint && <div className="text-xs text-slate-400 mt-1">{hint}</div>}
    </Link>
  );
}

function Block({
  title, subtitle, action, children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 mb-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
