import { Check, Copy, RotateCw } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { IconButton } from '@/components/ui/IconButton';
import { JobStatusPill } from '@/components/ui/StatusPill';
import { formatCount, formatDuration, formatTimestamp, titleCase } from '@/lib/format';
import { humaniseIngestError } from '@/lib/admin/ingestErrors';
import type { IngestionJob } from '@/lib/admin/types';

interface JobDrawerProps {
  job: IngestionJob | null;
  onClose(): void;
  onRetry?(job: IngestionJob): void;
  retrying?: boolean;
}

export function JobDrawer({ job, onClose, onRetry, retrying = false }: JobDrawerProps) {
  const humanised = humaniseIngestError(job?.error ?? null);

  return (
    <Drawer
      open={job !== null}
      onClose={onClose}
      title={job?.documentTitle ?? job?.documentId ?? 'Job'}
      actions={job && <JobStatusPill status={job.status} />}
      footer={
        job && onRetry && job.status === 'failed' ? (
          <Button
            variant="primary"
            onClick={() => onRetry(job)}
            loading={retrying}
            icon={<RotateCw size={14} strokeWidth={2} />}
            className="w-full"
          >
            Retry this ingest
          </Button>
        ) : undefined
      }
    >
      {job && (
        <div className="flex flex-col gap-5">
          <Field label="Type" value={titleCase(job.docType)} />
          <Field label="Document id" value={job.documentId} mono />
          <Field label="Job id" value={job.id} mono />

          <section>
            <SectionLabel>Timeline</SectionLabel>
            <dl className="flex flex-col gap-1.5">
              <TimelineRow label="Created" value={formatTimestamp(job.createdAt)} />
              <TimelineRow label="Started" value={formatTimestamp(job.startedAt)} />
              <TimelineRow label="Finished" value={formatTimestamp(job.finishedAt)} />
              <TimelineRow
                label="Duration"
                value={formatDuration(job.durationMs)}
                emphasis
              />
            </dl>
          </section>

          <section>
            <SectionLabel>Output</SectionLabel>
            <div className="flex gap-6">
              <Metric label="Chunks written" value={formatCount(job.chunkCount)} />
              <Metric label="Vector points" value={formatCount(job.pointCount)} />
            </div>
            {job.status === 'done' && job.chunkCount !== job.pointCount && (
              <p className="mt-2 rounded-lg bg-warn-soft px-2.5 py-1.5 text-[11.5px] text-warn">
                Chunks and points disagree. Postgres is written before Qdrant, so this run wrote
                rows it never vectorised.
              </p>
            )}
          </section>

          {job.langsmithRunId && (
            <section>
              <SectionLabel>Trace</SectionLabel>
              <CopyableValue value={job.langsmithRunId} />
            </section>
          )}

          {job.error && humanised && (
            <section>
              <SectionLabel>Failure</SectionLabel>
              <div className="rounded-lg border border-danger/30 bg-danger-soft p-3">
                <p className="text-[12.5px] font-medium text-danger">{humanised.cause}</p>
                <p className="mt-1 text-[12px] leading-relaxed text-danger/90">
                  {humanised.action}
                </p>
              </div>
              {/* The raw string is always reachable. A humanised summary that
                  replaced the original would make an unrecognised failure mode
                  undiagnosable. */}
              <details className="mt-2">
                <summary className="cursor-pointer text-[11px] text-text-faint hover:text-text-muted">
                  Raw error
                </summary>
                <pre className="mt-1.5 max-w-full overflow-x-auto rounded-lg border border-border bg-surface-2 p-2 font-mono text-[11px] whitespace-pre-wrap text-text-muted">
                  {job.error}
                </pre>
              </details>
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h3 className="mb-2 text-[10px] font-semibold tracking-[0.08em] text-text-faint uppercase">
      {children}
    </h3>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="shrink-0 text-[11px] text-text-faint">{label}</span>
      <span className={`min-w-0 truncate text-[12.5px] text-text ${mono ? 'font-mono' : ''}`}>
        {value}
      </span>
    </div>
  );
}

function TimelineRow({
  label,
  value,
  emphasis = false,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-[11px] text-text-faint">{label}</dt>
      <dd
        className={`font-mono text-[12px] tabular-nums ${emphasis ? 'font-semibold text-text' : 'text-text-muted'}`}
      >
        {value}
      </dd>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[18px] font-semibold text-text tabular-nums">{value}</p>
      <p className="text-[11px] text-text-faint">{label}</p>
    </div>
  );
}

/** A monospace value with a copy button — run ids exist to be pasted elsewhere. */
function CopyableValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard
      ?.writeText(value)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => {
        // Clipboard blocked (insecure origin, or permission denied). The value
        // is on screen and selectable, so this degrades to manual copying.
        console.warn('Clipboard write failed; the value is still selectable.');
      });
  };

  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-2.5 py-1.5">
      <code className="min-w-0 flex-1 truncate font-mono text-[11.5px] text-text-muted">
        {value}
      </code>
      <IconButton onClick={copy} aria-label="Copy" title="Copy" className="h-6 w-6">
        {copied ? (
          <Check size={12} strokeWidth={2.5} className="text-ok" />
        ) : (
          <Copy size={12} strokeWidth={2} />
        )}
      </IconButton>
    </div>
  );
}
