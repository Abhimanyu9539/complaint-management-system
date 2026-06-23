import { TONE_CLASSES, severityLabel, severityTone } from '@/lib/status';
import type { TicketSeverity } from '@/lib/tickets/types';

const BARS: Record<TicketSeverity, number> = { low: 2, normal: 3, high: 4, critical: 4 };

interface SeverityBadgeProps {
  severity: TicketSeverity;
  /** Icon only — the label stays available to screen readers and on hover. */
  iconOnly?: boolean;
}

/**
 * Severity as signal bars + label. A different shape from the status pill, so
 * the two columns never blur together even where their hues overlap.
 */
export function SeverityBadge({ severity, iconOnly = false }: SeverityBadgeProps) {
  const tone = TONE_CLASSES[severityTone(severity)];
  const label = severityLabel(severity);
  const filled = BARS[severity] ?? 0;

  return (
    <span
      title={`${label} severity`}
      className={`inline-flex shrink-0 items-center gap-1.5 text-[11.5px] font-semibold whitespace-nowrap ${tone.text}`}
    >
      <svg width="14" height="12" viewBox="0 0 14 12" aria-hidden="true">
        {[0, 1, 2, 3].map((index) => (
          <rect
            key={index}
            x={index * 3.6}
            y={9 - index * 3}
            width="2.6"
            height={3 + index * 3}
            rx="0.8"
            className={index < filled ? tone.fill : 'fill-border-strong'}
          />
        ))}
      </svg>
      <span className={iconOnly ? 'sr-only' : undefined}>{label}</span>
    </span>
  );
}
