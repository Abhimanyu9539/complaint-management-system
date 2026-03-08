import { useState } from 'react';
import { ExternalLink, FileWarning, Loader2 } from 'lucide-react';
import { transport } from '@/lib/chat/transport';
import type { Citation } from '@/lib/chat/types';

type LinkState = 'idle' | 'loading' | 'unavailable';

const BASE_CLASS =
  'mt-2.5 inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium transition-colors';

/**
 * Opens the original document behind a citation. Uses `document_url` when the
 * answer already carried one, otherwise resolves it on demand through the
 * transport (which will hit `GET /cases/{id}` or `GET /policies/{id}`,
 * depending on `citation.doc_type`, once those endpoints ship).
 */
export function SourceDocumentLink({ citation }: { citation: Citation }) {
  const [state, setState] = useState<LinkState>('idle');

  if (citation.document_url) {
    return (
      <a
        href={citation.document_url}
        target="_blank"
        rel="noopener noreferrer"
        className={`${BASE_CLASS} text-accent hover:bg-accent-soft`}
      >
        <ExternalLink size={12} strokeWidth={2} />
        Open document
      </a>
    );
  }

  const handleOpen = async () => {
    setState('loading');
    try {
      const document = await transport.getDocument(citation.doc_id, citation.doc_type);
      if (document?.url) {
        window.open(document.url, '_blank', 'noopener,noreferrer');
        setState('idle');
        return;
      }
      console.warn(`SourceDocumentLink: no URL available for ${citation.doc_id}`);
      setState('unavailable');
    } catch (err) {
      console.warn(`SourceDocumentLink: failed to resolve ${citation.doc_id}`, err);
      setState('unavailable');
    }
  };

  if (state === 'unavailable') {
    return (
      <span
        className={`${BASE_CLASS} cursor-default text-text-faint`}
        title="This document has no stored file yet, or the documents API is not available."
      >
        <FileWarning size={12} strokeWidth={2} />
        Document unavailable
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={handleOpen}
      disabled={state === 'loading'}
      className={`${BASE_CLASS} text-accent hover:bg-accent-soft disabled:opacity-60`}
    >
      {state === 'loading' ? (
        <Loader2 size={12} strokeWidth={2} className="animate-spin" />
      ) : (
        <ExternalLink size={12} strokeWidth={2} />
      )}
      Open document
    </button>
  );
}
