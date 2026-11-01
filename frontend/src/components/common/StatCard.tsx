interface Props {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'warn' | 'danger' | 'good';
}

const toneClass: Record<NonNullable<Props['tone']>, string> = {
  default: 'text-slate-900',
  warn: 'text-amber-600',
  danger: 'text-red-600',
  good: 'text-emerald-600',
};

export default function StatCard({ label, value, hint, tone = 'default' }: Props) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${toneClass[tone]}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
    </div>
  );
}
