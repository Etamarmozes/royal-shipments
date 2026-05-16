import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { KpiCard } from '../components/KpiCard';
import { api } from '../services/api';

const PERIODS = [
  { v: 'today', l: 'Today' },
  { v: 'last_7_days', l: 'Last 7 days' },
  { v: 'this_month', l: 'This month' },
  { v: 'last_30_days', l: 'Last 30 days' },
  { v: 'last_90_days', l: 'Last 90 days' },
];

function fmt(n: number | null | undefined, suffix = '') {
  if (n == null) return '—';
  if (Math.abs(n) >= 1000) return Math.round(n).toLocaleString() + suffix;
  return (Math.round(n * 100) / 100).toLocaleString() + suffix;
}

export function Dashboard() {
  const [period, setPeriod] = useState('this_month');
  const [summary, setSummary] = useState<any>(null);
  const [top, setTop] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any>(null);

  useEffect(() => {
    api.summary(period).then(setSummary).catch(() => setSummary(null));
    api.topItems(period, 8).then(setTop).catch(() => setTop([]));
    api.stores(period).then(setStores).catch(() => setStores([]));
    api.alerts(period).then(setAlerts).catch(() => setAlerts(null));
  }, [period]);

  const delta = summary?.vs_previous_period?.delta_pct;
  const tone = delta == null ? 'neutral' : delta >= 0 ? 'good' : 'bad';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-ink">Dashboard</h1>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="text-sm rounded-md border border-slate-300 bg-white px-3 py-1.5"
        >
          {PERIODS.map((p) => (
            <option key={p.v} value={p.v}>{p.l}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Net sales"
          value={fmt(summary?.net_sales) + ' ₪'}
          sub={summary?.period_label}
          tone={tone}
        />
        <KpiCard
          label="Units"
          value={fmt(summary?.units)}
          sub={summary ? `Txns ${fmt(summary.transactions)}` : ''}
        />
        <KpiCard
          label="Avg price"
          value={fmt(summary?.avg_selling_price) + ' ₪'}
        />
        <KpiCard
          label="vs previous"
          value={delta == null ? '—' : `${delta > 0 ? '+' : ''}${delta}%`}
          sub={summary?.vs_previous_period?.previous_label}
          tone={tone}
        />
      </div>

      {alerts && (
        <section className="grid md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4">
            <div className="text-sm font-bold text-rose-800 mb-2">Alerts</div>
            <ul className="text-sm space-y-1.5">
              <li>▲ <span className="num">{alerts.fast_moving_low_stock_count}</span> fast-moving items at stockout risk</li>
              <li>▲ <span className="num">{alerts.slow_moving_high_stock_count}</span> slow-moving items tying up inventory</li>
              <li>▲ <span className="num">{alerts.stuck_items_count}</span> stuck items with no sales</li>
              {alerts.weak_stores?.length > 0 && (
                <li>▲ Weak stores: {alerts.weak_stores.map((s: any) => s.store_name).join(', ')}</li>
              )}
            </ul>
          </div>
          <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
            <div className="text-sm font-bold text-accent mb-2">Recommended actions</div>
            <ul className="text-sm space-y-2">
              {alerts.actions?.slice(0, 4).map((a: any, i: number) => (
                <li key={i}>
                  <div>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-accent/10 text-accent ms-2">
                      {a.priority}
                    </span>
                    ▶ {a.action} — {a.target}
                  </div>
                  <div className="text-xs text-muted ms-6">{a.why}</div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <section className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-bold mb-2">Top items</div>
          <table className="w-full text-sm">
            <thead className="text-muted text-xs">
              <tr>
                <th className="text-start font-normal py-1">Item</th>
                <th className="text-end font-normal py-1">Net ₪</th>
                <th className="text-end font-normal py-1">Share</th>
              </tr>
            </thead>
            <tbody>
              {top.map((it) => (
                <tr key={it.item_id} className="border-t border-slate-100">
                  <td className="py-1.5">
                    <div>{it.item_name}</div>
                    <div className="text-xs text-muted">{it.brand}</div>
                  </td>
                  <td className="py-1.5 text-end num">{fmt(it.value)}</td>
                  <td className="py-1.5 text-end num">{it.share_pct}%</td>
                </tr>
              ))}
              {top.length === 0 && (
                <tr><td colSpan={3} className="text-center text-muted py-4">No data yet</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-bold mb-2">Store ranking</div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stores} layout="vertical" margin={{ left: 60, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="store_name" width={100} />
              <Tooltip />
              <Bar dataKey="value" fill="#1e3a8a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
