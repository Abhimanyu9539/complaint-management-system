import { buildLinePath, linearScale, maxOf } from './scale';

interface SparklineProps {
  values: number[];
  /**
   * Required. A sparkline with no accessible name is decoration, and this one
   * is data — it is the only trend indicator on a stat card.
   */
  label: string;
  width?: number;
  height?: number;
  /** A Tailwind stroke utility. Resolves through var() in CSS, so palettes work. */
  strokeClass?: string;
}

/**
 * A fixed-size trend line for stat cards.
 *
 * No ResizeObserver here, unlike the full charts: this lives inside a card of
 * known size, so measuring would cost a layout pass for nothing.
 */
export function Sparkline({
  values,
  label,
  width = 72,
  height = 20,
  strokeClass = 'stroke-accent',
}: SparklineProps) {
  // One point cannot describe a trend, and drawing it would put a lone dot on
  // the card that reads as a rendering bug.
  if (values.length < 2) return null;

  const padding = 2;
  const max = maxOf([values]);
  const x = linearScale([0, values.length - 1], [padding, width - padding]);
  const y = linearScale([0, max], [height - padding, padding]);

  const path = buildLinePath(values.map((value, index) => [x(index), y(value)] as const));

  return (
    <svg
      width={width}
      height={height}
      role="img"
      aria-label={`${label}: ${values.length} points, latest ${values[values.length - 1]}`}
      className="shrink-0 overflow-visible"
    >
      <path
        d={path}
        fill="none"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={strokeClass}
      />
    </svg>
  );
}
