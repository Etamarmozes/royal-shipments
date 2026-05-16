const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function post<T>(path: string, body?: any): Promise<T> {
  const r = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  health: () => get<any>('/health'),
  summary: (period = 'this_month') =>
    get<any>(`/dashboard/summary?date_range=${period}`),
  topItems: (period = 'this_month', limit = 10) =>
    get<any[]>(`/dashboard/top-items?date_range=${period}&limit=${limit}`),
  bottomItems: (period = 'this_month', limit = 10) =>
    get<any[]>(`/dashboard/bottom-items?date_range=${period}&limit=${limit}`),
  stores: (period = 'this_month') =>
    get<any[]>(`/dashboard/stores?date_range=${period}`),
  alerts: (period = 'last_30_days') =>
    get<any>(`/dashboard/alerts?date_range=${period}`),
  inventoryRisks: () => get<any>('/dashboard/inventory-risks'),
  compareBrands: (a: string, b: string, period = 'this_month') =>
    get<any>(`/dashboard/compare-brands?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}&date_range=${period}`),
  importStatus: () => get<any>('/imports/status'),
  importLogs: () => get<any[]>('/imports/logs'),
  runImport: () => post<any>('/imports/run'),
  chat: (question: string) => post<any>('/ai/chat', { question }),
  generateReport: (req: any) => post<any>('/reports/generate', req),
  listReports: () => get<any[]>('/reports'),
  reportDownloadUrl: (id: number) => `${BASE}/reports/${id}/download`,
  dataStatus: () => get<any>('/data/status'),
};
