type Tone = 'neutral' | 'good' | 'bad' | 'warn';

const tones: Record<Tone, string> = {
  neutral: 'border-slate-200 bg-white',
  good: 'border-emerald-200 bg-emerald-50',
  bad: 'border-rose-200 bg-rose-50',
  warn: 'border-amber-200 bg-amber-50',
};

export function KpiCard({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: Tone;
}) {
  return (
    <div className={`rounded-xl border ${tones[tone]} p-4 flex flex-col gap-1`}>
      <div className="text-xs text-muted uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-bold text-ink num">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}
