/**
 * Display formatting for the admin panel.
 *
 * Every number an operator reads is formatted here rather than at the call
 * site, so "2.4s" never appears as "2.43s" three panels over. All of these are
 * pure and side-effect free — they are safe to call during render.
 */

/** Thousands-separated integer. `null`/`undefined` render as an em dash. */
export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString();
}

/**
 * A duration in milliseconds, scaled to the largest sensible unit.
 *
 * Ingest durations span four orders of magnitude — a content-hash skip is
 * ~40ms, a cold policy re-embed is minutes — so a fixed unit would render
 * either "0.04s" or "132000ms" somewhere. Precision drops as magnitude rises
 * because nobody needs milliseconds on a two-minute job.
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return '—';
  if (ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) {
    const seconds = ms / 1000;
    return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`;
  }
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  if (minutes < 60) return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

/**
 * Relative time, coarsened as it recedes.
 *
 * Used for "Updated 14s ago" and for job ages. Returns "just now" under five
 * seconds rather than "0s ago", which reads as a bug.
 */
export function formatRelativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '—';
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '—';

  const deltaMs = now - then;
  // Clock skew between the browser and the server can put a server timestamp a
  // few seconds in the future; "in 3s" would be alarming and meaningless.
  if (deltaMs < 5_000) return 'just now';

  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
}

/** Absolute timestamp for tables — local time, no year unless it differs. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';

  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: sameYear ? undefined : 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/** Date only — chart axes and day buckets. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * A 0–1 ratio as a percentage. `null` means "not measurable", which is a
 * different statement from 0% and must not collapse into it.
 */
export function formatPercent(ratio: number | null | undefined, digits = 0): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return '—';
  return `${(ratio * 100).toFixed(digits)}%`;
}

/**
 * Byte counts in binary units.
 *
 * Only ever used for *estimated* vector storage, which is why every call site
 * prefixes it with "est." — Qdrant reports no byte figure, so the number is
 * points × dims × 4 and excludes payloads, sparse vectors and the HNSW graph.
 */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—';
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

/** USD, with enough precision that a sub-cent per-run cost is not just "$0.00". */
export function formatCurrency(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || Number.isNaN(usd)) return '—';
  if (usd === 0) return '$0';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

/** Single-line truncation for table cells. Adds a real ellipsis, not "...". */
export function truncate(text: string, max: number): string {
  const collapsed = text.trim().replace(/\s+/g, ' ');
  return collapsed.length > max ? `${collapsed.slice(0, max)}…` : collapsed;
}

/** `case` → `Case`. Used for doc-type columns and filter labels. */
export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/[_-]/g, ' ');
}

/**
 * `finished_at − started_at` in ms, or null while the job is still open.
 *
 * A job row can have `finished_at` without `started_at` if it failed before
 * being claimed, so both are checked rather than assuming the pair.
 */
export function durationBetween(
  startIso: string | null | undefined,
  endIso: string | null | undefined,
): number | null {
  if (!startIso || !endIso) return null;
  const start = Date.parse(startIso);
  const end = Date.parse(endIso);
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  const delta = end - start;
  return delta >= 0 ? delta : null;
}
