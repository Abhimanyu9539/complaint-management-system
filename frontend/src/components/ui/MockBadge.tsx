import { FlaskConical } from 'lucide-react';

interface MockBadgeProps {
  /**
   * Why this data is simulated. Required, not optional: an unexplained
   * "Simulated" chip is worse than none — it tells the operator not to trust
   * the number without telling them what would make it trustworthy.
   */
  reason: string;
  variant?: 'chip' | 'banner';
  className?: string;
}

/**
 * The honesty marker.
 *
 * Parts of this panel have no backend yet. Rendering their placeholder values
 * unlabelled would present a simulation as a measurement, which an operator has
 * no way to detect. Every `AdminResult` carries a `mocked` flag for exactly
 * this, and this is where it surfaces.
 */
export function MockBadge({ reason, variant = 'chip', className = '' }: MockBadgeProps) {
  if (variant === 'banner') {
    return (
      <div
        className={`flex items-start gap-2 rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-[12px] leading-relaxed text-warn ${className}`}
      >
        <FlaskConical size={14} strokeWidth={1.75} className="mt-0.5 shrink-0" />
        <p className="min-w-0">{reason}</p>
      </div>
    );
  }

  return (
    <span
      title={reason}
      className={`inline-flex shrink-0 items-center gap-1 rounded-full bg-warn-soft px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap text-warn ${className}`}
    >
      <FlaskConical size={10} strokeWidth={2} aria-hidden="true" />
      Simulated
    </span>
  );
}
