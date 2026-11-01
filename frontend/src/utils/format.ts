export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}

export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? 'n/a' : `${(value * 100).toFixed(1)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? 'n/a' : value.toFixed(digits);
}
