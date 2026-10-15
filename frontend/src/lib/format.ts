/** Currency/number/date formatting helpers (single source of truth for the UI). */

export const CURRENCY = 'EUR';

const currencyFmt = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: CURRENCY,
  maximumFractionDigits: 2,
});

export function formatCurrency(value: number | string | null | undefined): string {
  const n = typeof value === 'string' ? Number(value) : value;
  if (n == null || Number.isNaN(n)) return '—';
  return currencyFmt.format(n);
}

export function formatNumber(value: number | string | null | undefined): string {
  const n = typeof value === 'string' ? Number(value) : value;
  if (n == null || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-IE');
}

export function formatRoas(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}x`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString('en-IE', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('en-IE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** yyyy-mm-dd in local time, for <input type="date"> values and API params. */
export function toDateInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** ISO datetime -> value for <input type="datetime-local"> (local time). */
export function toDateTimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** <input type="datetime-local"> value -> ISO string for the API. */
export function dateTimeLocalToISO(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}
