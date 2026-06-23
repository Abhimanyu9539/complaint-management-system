import { ConfidenceChip, StatusPill } from '@/components/ui/StatusPill';
import { severityLabel, severityTone } from '@/lib/status';
import type { Ticket, TicketDraft } from '@/lib/tickets/types';

interface EvidencePaneProps {
  ticket: Ticket;
  draft: TicketDraft | null;
  departmentLabel(id: string | null): string;
}

// Intake §7: below this the top department is a guess. Same boundary as `confidenceTone`.
const ROUTING_FLOOR = 0.6;

function percent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Predicted department, the similar past cases the drafter was given (cited ones
 * marked), and the policy the draft cited — all written by the ticket graph. Department names resolve through `departmentLabel`, backed by
 * the live `/admin/departments` list.
 */
export function EvidencePane({ ticket, draft, departmentLabel }: EvidencePaneProps) {
  // Every similar case the drafter was given, not only the cited ones: the reply
  // to the customer rarely cites a case, but the agent still wants the precedent.
  const pastCases = draft?.retrievedCases ?? [];
  const citedPolicies = draft?.policyRefs.filter((ref) => ref.cited) ?? [];
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

      <section className="rounded-lg border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Similar past cases
        </h3>
        {draft?.noMatch && (
          <p className="mb-2 rounded-lg bg-warn-soft px-3 py-2 text-[12px] leading-relaxed text-warn">
            No policy matched this complaint. The draft is a holding reply, not a resolution.
          </p>
        )}
        {!draft ? (
          <p className="text-[12px] text-text-faint">Not drafted yet.</p>
        ) : pastCases.length === 0 ? (
          <p className="text-[12px] text-text-faint">No similar past case was found.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {pastCases.map((pastCase) => (
              <details key={pastCase.chunkId} className="rounded-lg border border-border px-2.5 py-2">
                <summary className="flex cursor-pointer items-center gap-2 text-[12px] text-text">
                  <span className="font-mono text-[11px] text-accent">[{pastCase.marker}]</span>
                  <span className="min-w-0 truncate">{pastCase.title}</span>
                  {pastCase.cited && (
                    <span className="shrink-0 rounded bg-accent-soft px-1.5 py-0.5 text-[10.5px] font-medium text-accent">
                      cited
                    </span>
                  )}
                  <span
                    title="Hybrid search score. It ranks cases for this ticket only; it is not a similarity."
                    className="ml-auto rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-text-muted"
                  >
                    {pastCase.score.toFixed(2)}
                  </span>
                </summary>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-text-muted">
                  "{pastCase.snippet}"
                </p>
                {pastCase.resolution && (
                  <p className="mt-1.5 rounded bg-surface-2 px-2 py-1.5 text-[11.5px] leading-relaxed text-text">
                    <span className="font-medium text-ok">Resolution:</span> {pastCase.resolution}
                  </p>
                )}
              </details>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-border bg-surface p-3">
        <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
          Policy context
        </h3>
        {citedPolicies.length === 0 ? (
          <p className="text-[12px] text-text-faint">
            {draft ? 'The draft cites no policy.' : 'Not drafted yet.'}
          </p>
        ) : (
          <div className="flex flex-col gap-2.5">
            {citedPolicies.map((ref) => (
              <div key={ref.chunkId} className="text-[12px] leading-relaxed text-text-muted">
                <p className="flex items-center gap-2 text-text">
                  <span className="font-mono text-[11px] text-accent">[{ref.marker}]</span>
                  <span className="min-w-0 truncate">{ref.section || ref.title}</span>
                  <span
                    title="Reranker score, 0–1."
                    className="ml-auto rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-text-muted"
                  >
                    {ref.score.toFixed(2)}
                  </span>
                </p>
                <p className="mt-1 text-[11.5px]">{ref.snippet}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
