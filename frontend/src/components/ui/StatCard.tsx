import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import type { ReactNode } from 'react';
import type { AsyncStatus } from '@/hooks/useAsyncData';
import { TONE_CLASSES, type Tone } from '@/lib/status';
import { Sparkline } from '@/components/charts/Sparkline';
import { MockBadge } from './MockBadge';
import { Skeleton } from './Skeleton';

interface StatCardProps {
  label: string;
  value: string | number;
  /** Second line under the value: "of 43 total", "last 7 days". */
  hint?: string;
  /** Change against the previous window. `inverted` means a rise is bad. */
  delta?: { value: number; label: string; inverted?: boolean };
  icon?: ReactNode;
  /** 12–24 points. Rendered as a sparkline beside the value. */
  trend?: number[];
  /**
   * Stroke utility for the sparkline. Defaults to the palette accent, because a
   * trend line plots a *quantity* and `tone` describes the headline value, not
   * the series — "Success rate 98%" is `ok`, but the line under it is jobs per
   * day, and inheriting the tone painted it a fixed green in every palette.
   * Pass a ramp token only when the series itself is a status (a failure count).
   */
  trendClass?: string;
  tone?: Tone;
  status: AsyncStatus;
  /** Renders the Simulated chip in the corner. */
  mocked?: boolean;
  mockReason?: string;
}

export function StatCard({
  label,
  value,
  hint,
  delta,
  icon,
  trend,
  trendClass,
  tone = 'neutral',
  status,
  mocked = false,
  mockReason,
}: StatCardProps) {
  const toneClasses = TONE_CLASSES[tone];

  if (status === 'loading') {
    return (
      <div className="flex min-w-0 flex-col gap-2 rounded-xl border border-border bg-surface p-4 shadow-card">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
    );
  }

  // A rise is usually good, but not for a failure count — `inverted` flips the
  // colour without flipping the arrow, because the arrow describes the number
  // and the colour describes whether that is welcome.
  const deltaIsGood = delta ? (delta.inverted ? delta.value < 0 : delta.value > 0) : false;
  const deltaTone: Tone = delta?.value === 0 ? 'neutral' : deltaIsGood ? 'ok' : 'danger';

  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-border bg-surface p-4 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 truncate text-[11px] font-semibold tracking-[0.06em] text-text-faint uppercase">
          {label}
        </p>
        {mocked ? (
          <MockBadge reason={mockReason ?? 'Simulated value.'} />
        ) : (
          icon && <span className={`shrink-0 ${toneClasses.text}`}>{icon}</span>
        )}
      </div>

      <div className="mt-2 flex items-end justify-between gap-3">
        <p
          className={`min-w-0 truncate text-[26px] leading-none font-semibold tabular-nums ${tone === 'neutral' ? 'text-text' : toneClasses.text}`}
        >
          {value}
        </p>
        {trend && trend.length > 1 && (
          <Sparkline values={trend} label={`${label} trend`} strokeClass={trendClass} />
        )}
      </div>

      <div className="mt-2 flex min-w-0 items-center gap-2">
        {delta && (
          <span
            className={`inline-flex shrink-0 items-center gap-0.5 text-[11px] font-medium tabular-nums ${TONE_CLASSES[deltaTone].text}`}
          >
            {delta.value >= 0 ? (
              <ArrowUpRight size={12} strokeWidth={2.5} />
            ) : (
              <ArrowDownRight size={12} strokeWidth={2.5} />
            )}
            {Math.abs(delta.value)}
            <span className="ml-0.5 font-normal text-text-faint">{delta.label}</span>
          </span>
        )}
        {hint && <p className="min-w-0 truncate text-[11px] text-text-faint">{hint}</p>}
      </div>
    </div>
  );
}
