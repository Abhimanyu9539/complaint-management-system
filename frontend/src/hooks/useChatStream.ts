import { useCallback, useRef, useState } from 'react';
import type { ChatTransport, Citation, StreamChatRequest } from '@/lib/chat/types';

export type ChatStreamStatus = 'idle' | 'streaming' | 'error';

interface StartOptions {
  onDone(result: {
    text: string;
    citations: Citation[];
    messageId: string | null;
    sessionId: string | null;
    interrupted: boolean;
  }): void;
}

export function useChatStream(transport: ChatTransport) {
  const [streamingText, setStreamingText] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [status, setStatus] = useState<ChatStreamStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const start = useCallback(
    (req: StreamChatRequest, { onDone }: StartOptions) => {
      const controller = new AbortController();
      abortRef.current = controller;

      setStreamingText('');
      setCitations([]);
      setError(null);
      setStatus('streaming');

      let text = '';
      let finalCitations: Citation[] = [];
      let messageId: string | null = null;
      let sessionId: string | null = req.sessionId;

      (async () => {
        try {
          for await (const event of transport.streamChat(req, controller.signal)) {
            switch (event.type) {
              case 'token':
                text += event.text;
                setStreamingText(text);
                break;
              case 'citations':
                finalCitations = event.citations;
                setCitations(finalCitations);
                break;
              case 'done':
                messageId = event.message_id;
                sessionId = event.session_id ?? sessionId;
                break;
              case 'error':
                setError(event.message);
                setStatus('error');
                onDone({ text, citations: finalCitations, messageId, sessionId, interrupted: true });
                return;
            }
          }
          setStatus('idle');
          onDone({ text, citations: finalCitations, messageId, sessionId, interrupted: false });
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') {
            setStatus('idle');
            onDone({ text, citations: finalCitations, messageId, sessionId, interrupted: true });
            return;
          }
          setError(err instanceof Error ? err.message : 'Something went wrong.');
          setStatus('error');
          onDone({ text, citations: finalCitations, messageId, sessionId, interrupted: true });
        }
      })();
    },
    [transport],
  );

  return { start, stop, streamingText, citations, status, error };
}
