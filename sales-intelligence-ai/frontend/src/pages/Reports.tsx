import { useEffect, useState } from 'react';
import { api } from '../services/api';

const TOPICS = [
  { v: 'ceo_summary', l: 'CEO summary' },
  { v: 'brand_comparison', l: 'Brand comparison' },
  { v: 'store_ranking', l: 'Store ranking' },
  { v: 'action_plan', l: 'Action plan' },
];

const FORMATS = ['png', 'jpg', 'pdf'];
const LAYOUTS = ['desktop', 'whatsapp', 'ceo_one_pager'];

export function Reports() {
  const [topic, setTopic] = useState('ceo_summary');
  const [format, setFormat] = useState('png');
  const [layout, setLayout] = useState('desktop');
  const [brandA, setBrandA] = useState('Keds');
  const [brandB, setBrandB] = useState('Adidas');
  const [period, setPeriod] = useState('this_month');
  const [generating, setGenerating] = useState(false);
  const [reports, setReports] = useState<any[]>([]);

  const refresh = async () => setReports(await api.listReports().catch(() => []));

  useEffect(() => { refresh(); }, []);

  const onGenerate = async () => {
    setGenerating(true);
    try {
      await api.generateReport({
        topic,
        format,
        layout,
        date_range: period,
        params: topic === 'brand_comparison' ? { brand_a: brandA, brand_b: brandB } : {},
      });
      await refresh();
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-ink">Reports</h1>

      <div className="rounded-xl border border-slate-200 bg-white p-4 grid md:grid-cols-3 gap-3">
        <label className="text-sm">
          <div className="text-muted text-xs mb-1">Topic</div>
          <select value={topic} onChange={(e) => setTopic(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5">
            {TOPICS.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <div className="text-muted text-xs mb-1">Format</div>
          <select value={format} onChange={(e) => setFormat(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5">
            {FORMATS.map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <div className="text-muted text-xs mb-1">Layout</div>
          <select value={layout} onChange={(e) => setLayout(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5">
            {LAYOUTS.map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <div className="text-muted text-xs mb-1">Period</div>
          <select value={period} onChange={(e) => setPeriod(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-2 py-1.5">
            <option value="last_7_days">Last 7 days</option>
            <option value="this_month">This month</option>
            <option value="last_30_days">Last 30 days</option>
            <option value="last_90_days">Last 90 days</option>
          </select>
        </label>
        {topic === 'brand_comparison' && (
          <>
            <label className="text-sm">
              <div className="text-muted text-xs mb-1">Brand A</div>
              <input value={brandA} onChange={(e) => setBrandA(e.target.value)}
                     className="w-full rounded-md border border-slate-300 px-2 py-1.5" />
            </label>
            <label className="text-sm">
              <div className="text-muted text-xs mb-1">Brand B</div>
              <input value={brandB} onChange={(e) => setBrandB(e.target.value)}
                     className="w-full rounded-md border border-slate-300 px-2 py-1.5" />
            </label>
          </>
        )}
        <div className="md:col-span-3 flex justify-end">
          <button
            disabled={generating}
            onClick={onGenerate}
            className="bg-accent text-white text-sm px-4 py-2 rounded-md disabled:opacity-50"
          >
            {generating ? 'Generating…' : 'Generate report'}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-200 text-sm font-bold">
          Generated reports
        </div>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr>
              <th className="text-start font-normal px-4 py-2">When</th>
              <th className="text-start font-normal px-4 py-2">Title</th>
              <th className="text-start font-normal px-4 py-2">Type</th>
              <th className="text-start font-normal px-4 py-2">Format</th>
              <th className="text-start font-normal px-4 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="px-4 py-2 num text-xs">{r.generated_at?.replace('T', ' ').slice(0, 19)}</td>
                <td className="px-4 py-2">{r.title}</td>
                <td className="px-4 py-2 text-xs"><code>{r.report_type}</code></td>
                <td className="px-4 py-2"><code>{r.format}</code></td>
                <td className="px-4 py-2">
                  <a href={api.reportDownloadUrl(r.id)} target="_blank" rel="noreferrer"
                     className="text-accent text-xs">Download</a>
                </td>
              </tr>
            ))}
            {reports.length === 0 && (
              <tr><td colSpan={5} className="text-center text-muted py-6">
                No reports yet — generate one above.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
