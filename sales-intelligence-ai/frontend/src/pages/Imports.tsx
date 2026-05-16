import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';

const STATUS_TONES: Record<string, string> = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  partial: 'bg-amber-50 text-amber-700 border-amber-200',
  failed: 'bg-rose-50 text-rose-700 border-rose-200',
  skipped: 'bg-slate-50 text-slate-600 border-slate-200',
};

export function Imports() {
  const [status, setStatus] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [running, setRunning] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    setStatus(await api.importStatus().catch(() => null));
    setLogs(await api.importLogs().catch(() => []));
  };

  useEffect(() => {
    refresh();
  }, []);

  const onRun = async () => {
    setRunning(true);
    try {
      await api.runImport();
      await refresh();
    } finally {
      setRunning(false);
    }
  };

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    setRunning(true);
    try {
      await fetch('/api/imports/upload', { method: 'POST', body: fd });
      await refresh();
    } finally {
      setRunning(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-ink">Imports</h1>
        <div className="flex items-center gap-2">
          <input ref={fileRef} type="file" onChange={onUpload}
                 className="text-xs text-muted" accept=".xlsx,.xls,.xlsm,.csv,.tsv" />
          <button
            disabled={running}
            onClick={onRun}
            className="text-sm bg-accent text-white px-3 py-1.5 rounded-md disabled:opacity-50"
          >
            {running ? 'Running…' : 'Run import on folder'}
          </button>
        </div>
      </div>

      {status && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm space-y-1">
          <div>
            <span className="text-muted">Folder:</span>{' '}
            <code className="text-xs">{status.comax_reports_dir}</code>
          </div>
          <div>
            <span className="text-muted">Pending files in folder:</span>{' '}
            <span className="num">{status.pending_files}</span>
          </div>
          <div>
            <span className="text-muted">Last successful import:</span>{' '}
            <span className="num">{status.last_successful_import ?? '—'}</span>
          </div>
          {Object.keys(status.by_report_type || {}).length > 0 && (
            <div className="pt-2">
              <div className="text-muted text-xs mb-1">Most recent per report type:</div>
              <ul className="text-xs">
                {Object.entries(status.by_report_type).map(([k, v]: any) => (
                  <li key={k}>
                    <code>{k}</code> · <span className="num">{v ?? '—'}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-200 text-sm font-bold">
          Recent imports
        </div>
        <table className="w-full text-sm">
          <thead className="text-muted text-xs">
            <tr>
              <th className="text-start font-normal px-4 py-2">When</th>
              <th className="text-start font-normal px-4 py-2">File</th>
              <th className="text-start font-normal px-4 py-2">Type</th>
              <th className="text-end font-normal px-4 py-2">Detected</th>
              <th className="text-end font-normal px-4 py-2">Imported</th>
              <th className="text-end font-normal px-4 py-2">Failed</th>
              <th className="text-start font-normal px-4 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-t border-slate-100">
                <td className="px-4 py-2 num text-xs">{l.imported_at?.replace('T', ' ').slice(0, 19)}</td>
                <td className="px-4 py-2">{l.file_name}</td>
                <td className="px-4 py-2 text-xs"><code>{l.report_type}</code></td>
                <td className="px-4 py-2 text-end num">{l.rows_detected}</td>
                <td className="px-4 py-2 text-end num">{l.rows_imported}</td>
                <td className="px-4 py-2 text-end num">{l.rows_failed}</td>
                <td className="px-4 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded border ${STATUS_TONES[l.status] || ''}`}>
                    {l.status}
                  </span>
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan={7} className="text-center text-muted py-6">No imports yet. Drop a file in the folder and click "Run import".</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
