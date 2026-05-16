import { useEffect, useState } from 'react';
import { api } from '../services/api';

function ageStr(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function DataFreshness() {
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    api.health().then(setS).catch(() => {});
  }, []);
  if (!s) return null;
  const tone =
    !s.last_sales_date
      ? 'bg-rose-50 text-rose-700 border-rose-200'
      : 'bg-emerald-50 text-emerald-700 border-emerald-200';
  return (
    <div className={`text-xs px-3 py-1.5 rounded-md border ${tone}`}>
      Sales: <span className="num">{ageStr(s.last_sales_date)}</span> · Inventory:{' '}
      <span className="num">{ageStr(s.last_inventory_date)}</span>
      {!s.ai_configured && <span className="ms-2 text-amber-700">· AI key not set</span>}
    </div>
  );
}
