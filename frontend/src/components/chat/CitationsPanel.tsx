import { useEffect, useRef } from 'react';
import { Library, PanelRightClose, Pin } from 'lucide-react';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import { useActiveCitations } from '@/hooks/useActiveCitations';
import { useCitationsPanel } from '@/state/CitationsPanelProvider';
import type { Citation } from '@/lib/chat/types';
import { SourceDocumentLink } from './SourceDocumentLink';

function docTypeLabel(docType: Citation['doc_type']): string {
  return docType === 'policy' ? 'Policy' : 'Resolved case';
}

export function CitationsPanelContent() {
  const { close, focusedChunkId, clearPin } = useCitationsPanel();
  const { citations, pinned, sourceLabel } = useActiveCitations();
  const cardRefs = useRef(new Map<string, HTMLDivElement>());

  useEffect(() => {
    if (!focusedChunkId) return;
    cardRefs.current.get(focusedChunkId)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [focusedChunkId, citations]);

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex h-13 shrink-0 items-center justify-between gap-2 border-b border-border px-3">
        <div className="flex min-w-0 items-center gap-2 pl-1">
          <Library size={ICON_SIZE} strokeWidth={1.75} className="shrink-0 text-accent" />
          <span className="text-[13px] font-semibold text-text">Sources</span>
          <span className="rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-text-muted">
            {citations.length}
          </span>
        </div>
        <IconButton
          onClick={close}
          aria-label="Collapse sources panel"
          title="Collapse sources panel"
        >
          <PanelRightClose size={ICON_SIZE} strokeWidth={1.75} />
        </IconButton>
      </div>

      {sourceLabel && (
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2">
          <span className="text-[11px] text-text-faint">{sourceLabel}</span>
          {pinned && (
            <button
              type="button"
              onClick={clearPin}
              className="flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-medium text-accent transition-opacity hover:opacity-80"
            >
              <Pin size={9} strokeWidth={2.5} />
              Unpin
            </button>
          )}
        </div>
      )}

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <div className="flex flex-col gap-2.5">
          {citations.map((citation, index) => {
            const focused = citation.chunk_id === focusedChunkId;
            return (
              <div
                key={citation.chunk_id}
                ref={(el) => {
                  if (el) cardRefs.current.set(citation.chunk_id, el);
                  else cardRefs.current.delete(citation.chunk_id);
                }}
                className={`rounded-xl border bg-bg-elevated p-3 transition-colors ${
                  focused ? 'border-accent ring-1 ring-accent' : 'border-border'
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-accent-text">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] leading-snug font-semibold text-text">
                      {citation.title}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[9.5px] font-medium text-accent">
                        {docTypeLabel(citation.doc_type)}
                      </span>
                      <span className="font-mono text-[9.5px] text-text-faint">
                        {citation.chunk_id}
                      </span>
                    </div>
                  </div>
                </div>

                <blockquote className="mt-2.5 border-l-2 border-border-strong pl-2.5 text-[12px] leading-relaxed text-text-muted">
                  {citation.snippet}
                </blockquote>

                <SourceDocumentLink citation={citation} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
