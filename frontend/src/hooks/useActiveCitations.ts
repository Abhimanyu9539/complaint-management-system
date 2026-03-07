import { useMemo } from 'react';
import type { Citation } from '@/lib/chat/types';
import { useChat } from '@/state/ChatProvider';
import { useCitationsPanel } from '@/state/CitationsPanelProvider';

interface ActiveCitations {
  citations: Citation[];
  pinned: boolean;
  sourceLabel: string | null;
}

/**
 * Resolves which message's sources the panel shows: an explicitly pinned
 * message if there is one, otherwise the answer currently being written, and
 * failing that the most recent answer that cited anything.
 */
export function useActiveCitations(): ActiveCitations {
  const { messages, streamingCitations, status } = useChat();
  const { pinnedMessageId } = useCitationsPanel();

  return useMemo(() => {
    if (pinnedMessageId) {
      const pinnedMessage = messages.find((m) => m.id === pinnedMessageId);
      if (pinnedMessage?.citations?.length) {
        return {
          citations: pinnedMessage.citations,
          pinned: true,
          sourceLabel: 'Pinned to an earlier answer',
        };
      }
    }

    if (status === 'streaming' && streamingCitations.length > 0) {
      return {
        citations: streamingCitations,
        pinned: false,
        sourceLabel: 'From the current answer',
      };
    }

    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const message = messages[i];
      if (message.role === 'assistant' && message.citations?.length) {
        return {
          citations: message.citations,
          pinned: false,
          sourceLabel: 'From the latest answer',
        };
      }
    }

    return { citations: [], pinned: false, sourceLabel: null };
  }, [messages, pinnedMessageId, streamingCitations, status]);
}
