import type { Citation } from '@/lib/chat/types';
import { useCitationsPanel } from '@/state/CitationsPanelProvider';

interface CitationChipsProps {
  messageId: string;
  citations: Citation[];
}

export function CitationChips({ messageId, citations }: CitationChipsProps) {
  const { showFor } = useCitationsPanel();

  if (citations.length === 0) return null;

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] font-medium text-text-faint">
        {citations.length === 1 ? '1 source' : `${citations.length} sources`}
      </span>
      {citations.map((citation, index) => (
        <button
          key={citation.chunk_id}
          type="button"
          onClick={() => showFor(messageId, citation.chunk_id)}
          title={citation.title}
          className="group flex max-w-[220px] items-center gap-1.5 rounded-full border border-border bg-surface-2 py-1 pr-2.5 pl-1 text-[11px] text-text-muted transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-text"
        >
          <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent text-[9px] font-semibold text-accent-text">
            {index + 1}
          </span>
          <span className="truncate">{citation.title}</span>
        </button>
      ))}
    </div>
  );
}
