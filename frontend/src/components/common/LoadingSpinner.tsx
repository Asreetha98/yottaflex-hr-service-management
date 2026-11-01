interface Props {
  label?: string;
}

export default function LoadingSpinner({ label = 'Loading' }: Props) {
  return (
    <div className="flex items-center justify-center gap-3 p-8 text-slate-500" role="status" aria-live="polite">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      <span className="text-sm">{label}…</span>
    </div>
  );
}
