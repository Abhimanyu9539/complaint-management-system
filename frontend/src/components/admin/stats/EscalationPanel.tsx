import { GitBranch } from 'lucide-react';
import { BarChart } from '@/components/charts/BarChart';
import { ChartFrame } from '@/components/charts/ChartFrame';
import { LineChart } from '@/components/charts/LineChart';
import { StackedBar } from '@/components/charts/StackedBar';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { usePanelData } from '@/hooks/usePanelData';
import { formatCount, formatDate, formatPercent } from '@/lib/format';
import { adminTransport } from '@/lib/admin/transport';

interface EscalationPanelProps {
  days: number;
}

/**
 * The north-star metric (cms.md §2): the share of complaints that retrieval and
 * a draft could not settle, where a specialist department had to be brought in.
 *
 * Two things here are deliberate and easy to get wrong on a rewrite:
 *
 * 1. **A null rate is not zero.** Before any ticket has resolved there is no
 *    rate, and `formatPercent(null)` renders an em dash. Showing 0% would put
 *    this system's best possible score on a system that has done nothing.
 * 2. **The corpus split is reported separately.** `cases.resolution_path`
 *    records how already-resolved complaints were resolved, and it is real
 *    measured data — but a case may have been minted from a ticket, so adding
 *    the two would double-count. Two figures, labelled, never summed.
 *
 * Colours follow the semantic ramp rather than the palette: direct/escalated is
 * a genuine status split, so `ok`/`warn` carry meaning that must survive a
 * palette change. See the rule on `Tone` in `lib/status.ts`.
 */
export function EscalationPanel({ days }: EscalationPanelProps) {
  const escalation = usePanelData(
    'stats-escalation',
    (signal) => adminTransport.getEscalationSummary(days, signal),
    { intervalFactor: 2, deps: [days] },
  );

  const data = escalation.data;
  const resolvedTotal = (data?.resolvedDirect ?? 0) + (data?.resolvedEscalated ?? 0);
  const perDay = data?.perDay ?? [];
  const escalatingDepartments = (data?.byDepartment ?? []).filter(
    (entry) => entry.escalations > 0,
  );

  return (
    <>
      <Panel
        title="Escalation rate"
        eyebrow="North star"
        span={2}
        description="The share of resolved complaints that needed a specialist department. Lower is better."
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <div>
              <p className="text-[32px] leading-none font-semibold tabular-nums text-text">
                {formatPercent(data?.escalationRate, 1)}
              </p>
              <p className="mt-1.5 text-[11px] text-text-faint">
                {data?.escalationRate === null || data?.escalationRate === undefined
                  ? 'No ticket has been resolved yet, so there is no rate to report.'
                  : `${formatCount(data.resolvedEscalated)} of ${formatCount(resolvedTotal)} resolved complaints`}
              </p>
            </div>

            {(data?.openEscalated ?? 0) > 0 && (
              <div>
                <p className="text-[18px] leading-none font-semibold tabular-nums text-warn">
                  {formatCount(data?.openEscalated)}
                </p>
                <p className="mt-1 text-[11px] text-text-faint">
                  awaiting a department — no outcome yet, so excluded above
                </p>
              </div>
            )}
          </div>

          {resolvedTotal > 0 && (
            <StackedBar
              segments={[
                {
                  key: 'direct',
                  label: 'Resolved directly',
                  value: data?.resolvedDirect ?? 0,
                  className: 'bg-ok',
                },
                {
                  key: 'escalated',
                  label: 'Escalated to a department',
                  value: data?.resolvedEscalated ?? 0,
                  className: 'bg-warn',
                },
              ]}
            />
          )}

          <ChartFrame
            title="Resolutions per day"
            summary={`Complaints resolved per day over the last ${days} days, split by whether a department was involved.`}
            height={180}
            status={escalation.status}
            error={escalation.error}
            isEmpty={perDay.every((bucket) => (bucket.values.resolved ?? 0) === 0)}
            emptyLabel="No complaints have been resolved in this period."
            onRetry={escalation.refresh}
            legend={[
              { label: 'Resolved', swatchClass: 'bg-ok' },
              { label: 'Of which escalated', swatchClass: 'bg-warn' },
            ]}
            dataTable={{
              columns: ['Date', 'Resolved', 'Escalated'],
              rows: perDay.map((bucket) => [
                bucket.date,
                bucket.values.resolved ?? 0,
                bucket.values.escalated ?? 0,
              ]),
            }}
          >
            {(width) => (
              <LineChart
                width={width}
                height={180}
                labels={perDay.map((bucket) => formatDate(bucket.date))}
                series={[
                  {
                    key: 'resolved',
                    label: 'Resolved',
                    strokeClass: 'stroke-ok',
                    areaClass: 'fill-ok/10',
                    values: perDay.map((bucket) => bucket.values.resolved ?? 0),
                  },
                  {
                    key: 'escalated',
                    label: 'Escalated',
                    strokeClass: 'stroke-warn',
                    values: perDay.map((bucket) => bucket.values.escalated ?? 0),
                  },
                ]}
              />
            )}
          </ChartFrame>

          <CorpusSplit
            direct={data?.corpus.direct ?? 0}
            escalated={data?.corpus.escalated ?? 0}
          />
        </div>
      </Panel>

      <Panel title="Escalations by department" eyebrow="Routing">
        {escalatingDepartments.length === 0 ? (
          <EmptyState
            icon={<GitBranch size={18} strokeWidth={1.5} />}
            title="No escalations yet"
            description="When a ticket is handed to a department, it appears here."
          />
        ) : (
          <ChartFrame
            title="Escalations per department"
            summary="Which departments are being pulled in, and how often."
            height={Math.max(160, escalatingDepartments.length * 28 + 40)}
            status={escalation.status}
            error={escalation.error}
            isEmpty={false}
            onRetry={escalation.refresh}
            dataTable={{
              columns: ['Department', 'Escalations'],
              rows: escalatingDepartments.map((entry) => [entry.label, entry.escalations]),
            }}
          >
            {(width) => (
              <BarChart
                width={width}
                height={Math.max(160, escalatingDepartments.length * 28 + 40)}
                horizontal
                labels={escalatingDepartments.map((entry) => entry.label)}
                series={[
                  {
                    key: 'escalations',
                    label: 'Escalations',
                    // A quantity within an already-status-labelled panel, so it
                    // follows the palette. The direct/escalated distinction is
                    // carried by the chart above, not repeated here.
                    fillClass: 'fill-accent',
                    values: escalatingDepartments.map((entry) => entry.escalations),
                  },
                ]}
              />
            )}
          </ChartFrame>
        )}
      </Panel>
    </>
  );
}

/**
 * The resolved-case corpus, shown apart from the live ticket figures.
 *
 * This is `cases.resolution_path` — how the complaints already in the retrieval
 * corpus were resolved. Real measured data, and for a fresh install the only
 * escalation data that exists. Kept visually separate because a case may have
 * been minted from a ticket by the flywheel and a seeded case was never a
 * ticket at all, so summing the two would both double-count and invent.
 */
function CorpusSplit({ direct, escalated }: { direct: number; escalated: number }) {
  const total = direct + escalated;

  return (
    <div className="border-t border-border pt-3">
      <p className="mb-1.5 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
        Resolved case corpus
      </p>
      {total === 0 ? (
        <p className="text-[11.5px] leading-relaxed text-text-faint">
          No resolved cases are indexed. Run <code>uv run cms-seed</code> to load the seed corpus,
          which carries its own resolution paths.
        </p>
      ) : (
        <>
          <p className="mb-2 text-[11.5px] leading-relaxed text-text-muted">
            {formatPercent(escalated / total, 1)} of the {formatCount(total)} complaints already in
            the knowledge base needed a department. Counted separately from live tickets — a case
            can be minted from one, so the two must not be added.
          </p>
          <StackedBar
            segments={[
              { key: 'direct', label: 'Direct', value: direct, className: 'bg-ok' },
              { key: 'escalated', label: 'Escalated', value: escalated, className: 'bg-warn' },
            ]}
          />
        </>
      )}
    </div>
  );
}
