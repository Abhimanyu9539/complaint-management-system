import { ConfidenceChip } from '@/components/ui/StatusPill';
import { MockBadge } from '@/components/ui/MockBadge';
import { simulatedEvidence } from '@/lib/tickets/simulated';
import type { Ticket } from '@/lib/tickets/types';

interface EvidencePaneProps {
  ticket: Ticket;
  departmentIds: string[];
  departmentLabel(id: string | null): string;
}

/**
 * Predicted department, cited historical cases and policy context — simulated,
 * same caveat as `DraftPane`. Department *names* are the one real thing here:
 * they resolve through `departmentLabel`, backed by the live
 * `/admin/departments` list, never a hardcoded fixture name.
 */
export function EvidencePane({ ticket, departmentIds, departmentLabel }: EvidencePaneProps) {
  const evidence = simulatedEvidence(ticket, departmentIds);

  return (
    <div className="flex flex-col gap-4 p-4">
      <MockBadge
        variant="banner"
        reason="Simulated — same caveat as the draft. Department names are real; the routing decision and similarity scores are not."
      />

      <section className="rounded-lg border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Predicted department
        </h3>
        {evidence.predictedDeptId ? (
          <>
            <div className="flex items-center gap-2 text-[13px] font-medium text-text">
              {departmentLabel(evidence.predictedDeptId)}
              <ConfidenceChip value={evidence.confidence} />
            </div>
            {evidence.alternativeDeptId && (
              <p className="mt-1 text-[11.5px] text-text-muted">
                Also considered: {departmentLabel(evidence.alternativeDeptId)}
              </p>
            )}
          </>
        ) : (
          <p className="text-[12px] text-text-faint">Departments have not loaded yet.</p>
        )}
      </section>

      <section className="rounded-lg border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Cited historical cases
        </h3>
        {evidence.noMatch ? (
          <p className="rounded-lg bg-warn-soft px-3 py-2 text-[12px] leading-relaxed text-warn">
            No case above the similarity threshold. The draft is a cautious holding reply, not a
            resolution.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {evidence.cases.map((citedCase) => (
              <details key={citedCase.id} className="rounded-lg border border-border px-2.5 py-2">
                <summary className="flex cursor-pointer items-center gap-2 text-[12px] text-text">
                  <span className="font-mono text-text-muted">#{citedCase.id}</span>
                  <span className="ml-auto rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-text-muted">
                    {citedCase.similarity.toFixed(2)}
                  </span>
                </summary>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-text-muted">
                  "{citedCase.snippet}"
                </p>
                <p className="mt-1.5 rounded bg-surface-2 px-2 py-1.5 text-[11.5px] leading-relaxed text-text">
                  <span className="font-medium text-ok">Resolution:</span> {citedCase.resolution}
                </p>
              </details>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Policy context
        </h3>
        <p className="text-[12px] leading-relaxed text-text-muted">
          <span className="font-mono text-[11px] text-accent">{evidence.policyRef}</span> —{' '}
          {evidence.policyText}
        </p>
      </section>
    </div>
  );
}
