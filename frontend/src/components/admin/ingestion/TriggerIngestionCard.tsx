import { CircleCheck, Play, TriangleAlert } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { MockBadge } from '@/components/ui/MockBadge';
import { Panel } from '@/components/ui/Panel';
import { Select } from '@/components/ui/Select';
import { usePanelData } from '@/hooks/usePanelData';
import { adminTransport } from '@/lib/admin/transport';
import type { DocType, TriggerIngestionRequest } from '@/lib/admin/types';

interface TriggerIngestionCardProps {
  /** Called after a run is accepted, so the jobs table picks it up immediately. */
  onTriggered(): void;
}

type Mode = TriggerIngestionRequest['mode'];

interface Outcome {
  ok: boolean;
  message: string;
}

/**
 * Manual ingestion trigger.
 *
 * The form is complete and the request it would send is exact, but there is no
 * POST route behind it yet: the pipeline is driven by the `cms-seed` CLI, and
 * calling `ingest_case` inline would hold a request worker for the length of an
 * embedding run. The banner says so plainly rather than letting the button
 * imply a capability the system does not have.
 *
 * In mock mode the simulated job does progress through queued → running → done,
 * so the states this form leads to are genuinely exercised.
 */
export function TriggerIngestionCard({ onTriggered }: TriggerIngestionCardProps) {
  const [docType, setDocType] = useState<DocType>('case');
  const [mode, setMode] = useState<Mode>('seed');
  const [documentId, setDocumentId] = useState('');
  const [force, setForce] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  // Only fetched when the picker is actually shown — a seed re-run does not
  // need a document list.
  const options = usePanelData(
    `document-options-${docType}`,
    (signal) => adminTransport.listDocumentOptions(docType, signal),
    { once: true, enabled: mode === 'document', deps: [docType] },
  );

  const submit = useCallback(async () => {
    setSubmitting(true);
    setOutcome(null);

    const controller = new AbortController();
    try {
      const response = await adminTransport.triggerIngestion(
        {
          docType,
          mode,
          documentId: mode === 'document' ? documentId : undefined,
          force,
        },
        controller.signal,
      );
      setOutcome({ ok: response.data.accepted, message: response.data.message });
      if (response.data.accepted) onTriggered();
    } catch (err) {
      // Rendered inline rather than as a toast: there are two mutations in this
      // whole panel, and a toast system for two call sites is a provider, a
      // portal, a timer queue and dismissal a11y for no gain.
      setOutcome({
        ok: false,
        message: err instanceof Error ? err.message : 'The request could not be sent.',
      });
    } finally {
      setSubmitting(false);
    }
  }, [docType, mode, documentId, force, onTriggered]);

  const canSubmit = mode === 'seed' || documentId !== '';

  return (
    <Panel
      title="Trigger ingestion"
      eyebrow="Manual run"
      description="Re-index the seed corpus or a single document."
    >
      <div className="flex flex-col gap-3">
        <MockBadge
          variant="banner"
          reason="Ingestion runs as a CLI job today (uv run cms-seed). This form simulates the request and shows the exact contract it will POST — see backend/docs/admin-api.md."
        />

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Select
            label="Document type"
            value={docType}
            onChange={(value) => setDocType(value as DocType)}
            options={[
              { value: 'case', label: 'Cases' },
              { value: 'policy', label: 'Policies' },
            ]}
          />
          <Select
            label="Scope"
            value={mode}
            onChange={(value) => setMode(value as Mode)}
            options={[
              { value: 'seed', label: 'Re-seed whole corpus' },
              { value: 'document', label: 'Single document' },
            ]}
          />
          {mode === 'document' && (
            <Select
              label="Document"
              value={documentId}
              disabled={options.status === 'loading'}
              onChange={setDocumentId}
              options={[
                { value: '', label: options.status === 'loading' ? 'Loading…' : 'Select a document' },
                ...(options.data ?? []).map((option) => ({
                  value: option.id,
                  label: option.title,
                })),
              ]}
              className="sm:col-span-2"
            />
          )}
        </div>

        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            checked={force}
            onChange={(event) => setForce(event.target.checked)}
            className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-[var(--accent)]"
          />
          <span className="min-w-0">
            <span className="text-[12.5px] font-medium text-text">Force re-index</span>
            <span className="block text-[11.5px] text-text-muted">
              Bypasses the content-hash check, so unchanged documents are embedded again. Costs a
              real embedding call per chunk.
            </span>
          </span>
        </label>

        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            onClick={submit}
            loading={submitting}
            disabled={!canSubmit}
            icon={<Play size={14} strokeWidth={2} />}
          >
            Start ingestion
          </Button>
          {!canSubmit && (
            <span className="text-[11.5px] text-text-faint">Pick a document first.</span>
          )}
        </div>

        {outcome && (
          <div
            role="status"
            className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-[12px] ${
              outcome.ok
                ? 'border-ok/30 bg-ok-soft text-ok'
                : 'border-danger/30 bg-danger-soft text-danger'
            }`}
          >
            {outcome.ok ? (
              <CircleCheck size={14} strokeWidth={2} className="mt-0.5 shrink-0" />
            ) : (
              <TriangleAlert size={14} strokeWidth={2} className="mt-0.5 shrink-0" />
            )}
            <p className="min-w-0">{outcome.message}</p>
          </div>
        )}
      </div>
    </Panel>
  );
}
