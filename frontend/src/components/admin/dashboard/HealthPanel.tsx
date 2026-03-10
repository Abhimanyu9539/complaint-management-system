import { Activity } from 'lucide-react';
import { AsyncBoundary } from '@/components/ui/AsyncBoundary';
import { EmptyState } from '@/components/ui/EmptyState';
import { MockBadge } from '@/components/ui/MockBadge';
import { Panel } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatusPill } from '@/components/ui/StatusPill';
import { usePanelData } from '@/hooks/usePanelData';
import { formatRelativeTime } from '@/lib/format';
import { TONE_CLASSES, healthTone } from '@/lib/status';
import { adminTransport } from '@/lib/admin/transport';

/**
 * Dependency health, from `/health/deps`.
 *
 * Polls at 3× the base cadence: this endpoint makes an outbound HTTP call to
 * Supabase auth and a Qdrant handshake on every hit, so treating it like a
 * cheap read would put real load on both just to keep a green dot green.
 */
export function HealthPanel() {
  const { data, status, error, errorDetail, failureCount, refresh, mocked, note } = usePanelData(
    'health',
    (signal) => adminTransport.getSystemHealth(signal),
    { intervalFactor: 3 },
  );

  return (
    <Panel
      title="System health"
      eyebrow="Dependencies"
      actions={
        <>
          {mocked && <MockBadge reason={note ?? 'Simulated health check.'} />}
          {data && (
            <StatusPill
              label={data.overall === 'ok' ? 'All systems go' : 'Degraded'}
              tone={healthTone(data.overall)}
            />
          )}
        </>
      }
    >
      <AsyncBoundary
        status={status}
        error={error}
        errorDetail={errorDetail}
        failureCount={failureCount}
        isEmpty={!data || data.services.length === 0}
        onRetry={refresh}
        empty={<EmptyState icon={<Activity size={18} strokeWidth={1.5} />} title="No health data." />}
        skeleton={
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-16" />
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {data?.services.map((service) => {
            const tone = healthTone(service.status);
            return (
              <div
                key={service.name}
                className="flex min-w-0 flex-col gap-1 rounded-lg border border-border bg-bg-elevated px-3 py-2.5"
              >
                <div className="flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    className={`h-2 w-2 shrink-0 rounded-full ${TONE_CLASSES[tone].dot}`}
                  />
                  <span className="min-w-0 truncate text-[12px] font-medium text-text">
                    {service.name}
                  </span>
                </div>
                <span
                  // The failure string from the backend is the most useful thing
                  // on this whole panel when something is broken, so it is shown
                  // rather than collapsed into the word "error".
                  title={service.detail ?? undefined}
                  className={`truncate text-[11px] ${service.status === 'ok' ? 'text-text-faint' : TONE_CLASSES[tone].text}`}
                >
                  {service.status === 'ok' ? 'Reachable' : (service.detail ?? 'Unreachable')}
                </span>
              </div>
            );
          })}
        </div>
        {data && (
          <p className="mt-2 text-[11px] text-text-faint">
            Checked {formatRelativeTime(data.checkedAt)}
          </p>
        )}
      </AsyncBoundary>
    </Panel>
  );
}
