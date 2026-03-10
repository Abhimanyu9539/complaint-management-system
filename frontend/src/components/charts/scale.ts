/**
 * Scale and path math for the hand-rolled charts. Pure, no React, no DOM.
 *
 * Isolated from the components so the arithmetic that produces SVG path data
 * can be reasoned about — and, when a chart renders blank, ruled out — without
 * involving rendering.
 */

export interface LinearScale {
  (value: number): number;
  domain: readonly [number, number];
  ticks(count: number): number[];
}

/** Maps a value from `domain` onto `range`. Handles inverted ranges (SVG y-axes). */
export function linearScale(
  domain: readonly [number, number],
  range: readonly [number, number],
): LinearScale {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  // A zero-width domain would divide by zero and emit NaN into every path
  // coordinate; pinning it to the range midpoint keeps the chart drawable.
  const span = d1 - d0 || 1;

  const scale = ((value: number) => r0 + ((value - d0) / span) * (r1 - r0)) as LinearScale;
  scale.domain = domain;
  scale.ticks = (count: number) => {
    if (count < 2) return [d0, d1];
    const step = (d1 - d0) / (count - 1);
    return Array.from({ length: count }, (_, index) => d0 + step * index);
  };

  return scale;
}

/** Evenly spaced bands across `range` — the x-axis for bar and categorical charts. */
export function bandScale(
  count: number,
  range: readonly [number, number],
  padding = 0.2,
): { at(index: number): number; bandwidth: number } {
  const [r0, r1] = range;
  const total = r1 - r0;
  const safeCount = Math.max(1, count);
  const step = total / safeCount;
  const bandwidth = Math.max(1, step * (1 - padding));

  return {
    at: (index: number) => r0 + step * index + (step - bandwidth) / 2,
    bandwidth,
  };
}

/**
 * Rounds an axis maximum up to a readable number: 137 → 150, 0.34 → 0.4, 7 → 8.
 *
 * Never returns 0. A zero maximum makes the y-scale degenerate, which produces
 * `NaN` in the `d` attribute — and an SVG path with NaN coordinates renders as
 * nothing at all, with only a console warning to go on. This guard is the
 * single most valuable line in the file.
 */
export function niceMax(max: number): number {
  if (!Number.isFinite(max) || max <= 0) return 1;

  const magnitude = 10 ** Math.floor(Math.log10(max));
  const normalised = max / magnitude;

  const rounded = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10;
  return rounded * magnitude;
}

/** The largest value across several series, for a shared y-axis. */
export function maxOf(seriesValues: readonly (readonly number[])[]): number {
  let max = 0;
  for (const values of seriesValues) {
    for (const value of values) {
      if (Number.isFinite(value) && value > max) max = value;
    }
  }
  return max;
}

/** `M x0 y0 L x1 y1 …` for a polyline. Empty input yields an empty string. */
export function buildLinePath(points: readonly (readonly [number, number])[]): string {
  if (points.length === 0) return '';
  return points
    .map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${round(x)} ${round(y)}`)
    .join(' ');
}

/** The same line, closed down to `baselineY` — the filled area under a series. */
export function buildAreaPath(
  points: readonly (readonly [number, number])[],
  baselineY: number,
): string {
  if (points.length === 0) return '';
  const line = buildLinePath(points);
  const lastX = points[points.length - 1][0];
  const firstX = points[0][0];
  return `${line} L${round(lastX)} ${round(baselineY)} L${round(firstX)} ${round(baselineY)} Z`;
}

/**
 * Two decimals is well under a device pixel at any sane zoom, and it keeps the
 * `d` attribute short enough to read when debugging.
 */
function round(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * Evenly samples at most `max` labels, always keeping the first and last.
 *
 * Rendering every x label on a 90-day chart produces unreadable overlap; the
 * endpoints must survive because they are what anchor the range.
 */
export function thinLabels(labels: readonly string[], max: number): (string | null)[] {
  if (labels.length <= max || max < 2) return [...labels];

  const step = (labels.length - 1) / (max - 1);
  const keep = new Set<number>();
  for (let index = 0; index < max; index += 1) keep.add(Math.round(index * step));
  keep.add(0);
  keep.add(labels.length - 1);

  return labels.map((label, index) => (keep.has(index) ? label : null));
}

/** Percentile from an unsorted array. Null when there is nothing to measure. */
export function percentile(values: readonly number[], fraction: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.floor(sorted.length * fraction));
  return sorted[index];
}
