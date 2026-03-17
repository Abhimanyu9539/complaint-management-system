import { CircleCheck, Play, TriangleAlert } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Panel';
import { Select } from '@/components/ui/Select';
import { usePanelData } from '@/hooks/usePanelData';
import { adminTransport } from '@/lib/admin/transport';
import type { DocStatus, DocType, TriggerIngestionRequest } from '@/lib/admin/types';

interface TriggerIngestionCardProps {
  /** Called after a run is accepted, so the jobs table picks it up immediately. */
  onTriggered(): void;
}

type Mode = TriggerIngestionRequest['mode'];

interface Outcome {
  ok: boolean;
  message: string;
}

/** A short suffix on the picker label, so an operator can see which of the
 * seed corpus's files are actually in the index without opening the jobs table. */
const STATUS_LABELS: Record<DocStatus, string> = {
  pending: 'registered, not indexed',
  processing: 'in progress',
  indexed: 'indexed',
  failed: 'last run failed',
  deleting: 'deleting',
};

function statusLabel(status: DocStatus | null): string {
  return status === null ? 'not ingested' : STATUS_LABELS[status];
}

/** Manual ingestion trigger. Queues a real job — see `backend/docs/admin-api.md` §4. */
export function TriggerIngestionCard({ onTriggered }: TriggerIngestionCardProps) {
  const [docType, setDocType] = useState<DocType>('case');
  const [mode, setMode] = useState<Mode>('seed');
  const [sourceRef, setSourceRef] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  // Bumped on every accepted trigger so the (otherwise `once: true`) picker
  // re-fetches — without this, the status suffix goes stale the moment an
  // operator triggers a file: the job finishes but the dropdown still says
  // "not ingested".
  const [refreshNonce, setRefreshNonce] = useState(0);

  // Only fetched when the picker is actually shown — a seed re-run does not
  // need a document list.
  const options = usePanelData(
    `document-options-${docType}`,
    (signal) => adminTransport.listDocumentOptions(docType, signal),
    { once: true, enabled: mode === 'document', deps: [docType, refreshNonce] },
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
          sourceRef: mode === 'document' ? sourceRef : undefined,
        },
        controller.signal,
      );
      setOutcome({
        ok: response.data.accepted,
        message: response.data.message,
      });
      if (response.data.accepted) {
        onTriggered();
        setRefreshNonce((n) => n + 1);
      }
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
  }, [docType, mode, sourceRef, onTriggered]);

  const canSubmit = mode === 'seed' || sourceRef !== '';

  return (
    <Panel
      title="Trigger ingestion"
      eyebrow="Manual run"
      description="Re-index the whole seed corpus, or one file from the server's seed directory."
    >
      <div className="flex flex-col gap-3">
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
              { value: 'document', label: 'One document from the corpus' },
            ]}
          />
          {mode === 'document' && (
            <Select
              label="Seed document"
              value={sourceRef}
              disabled={options.status === 'loading'}
              onChange={setSourceRef}
              options={[
                { value: '', label: options.status === 'loading' ? 'Loading…' : 'Select a seed document' },
                ...(options.data ?? []).map((option) => ({
                  value: option.sourceRef,
                  label: `${option.title} · ${statusLabel(option.status)}`,
                })),
              ]}
              className="sm:col-span-2"
            />
          )}
        </div>

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
            <span className="text-[11.5px] text-text-faint">Pick a seed document first.</span>
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
            <p className="min-w-0 flex-1">{outcome.message}</p>
          </div>
        )}
      </div>
    </Panel>
  );
}
