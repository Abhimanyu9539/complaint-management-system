import { ConfidenceChip, StatusPill } from '@/components/ui/StatusPill';
import { MockBadge } from '@/components/ui/MockBadge';
import { severityLabel, severityTone } from '@/lib/status';
import { simulatedEvidence } from '@/lib/tickets/simulated';
import type { Ticket } from '@/lib/tickets/types';

interface EvidencePaneProps {
  ticket: Ticket;
  departmentLabel(id: string | null): string;
}

// Intake §7: below this the top department is a guess. Same boundary as `confidenceTone`.
const ROUTING_FLOOR = 0.6;

function percent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Predicted department — real, written by the ticket graph — then cited cases
 * and policy context, which are still simulated (same caveat as `DraftPane`).
 * Department names resolve through `departmentLabel`, backed by the live
 * `/admin/departments` list.
 */
export function EvidencePane({ ticket, departmentLabel }: EvidencePaneProps) {
  const evidence = simulatedEvidence(ticket);
  const runnerUps = ticket.deptCandidates.slice(1);
  const lowConfidence = ticket.deptConfidence !== null && ticket.deptConfidence < ROUTING_FLOOR;

  return (
    <div className="flex flex-col gap-4 p-4">
      <section className="rounded-lg border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Predicted department
        </h3>
        {ticket.predictedDept ? (
          <>
            <div className="flex items-center gap-2 text-[13px] font-medium text-text">
              {departmentLabel(ticket.predictedDept)}
              <ConfidenceChip value={ticket.deptConfidence} />
            </div>
            {runnerUps.length > 0 && (
              <p className="mt-1 text-[11.5px] text-text-muted">
                Also considered:{' '}
                {runnerUps
                  .map((candidate) => `${departmentLabel(candidate.department)} (${percent(candidate.score)})`)
                  .join(' · ')}
              </p>
            )}
            {lowConfidence && (
              <p className="mt-1 text-[11.5px] text-warn">Low confidence — routing needs your judgement.</p>
            )}
            {ticket.suggestedSeverity && (
              <div className="mt-2 flex items-center gap-2 text-[11.5px] text-text-muted">
                Suggested severity
                <StatusPill
                  label={severityLabel(ticket.suggestedSeverity)}
                  tone={severityTone(ticket.suggestedSeverity)}
                />
              </div>
            )}
          </>
        ) : (
          <p className="text-[12px] text-text-faint">Not classified yet.</p>
        )}
      </section>

      <MockBadge
        variant="banner"
        reason="Simulated — same caveat as the draft. The cited cases and policy are placeholders until retrieval runs for tickets."
      />

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
