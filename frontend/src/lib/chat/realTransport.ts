import { parseSSEStream } from './sse';
import type {
  ChatEvent,
  ChatMessage,
  ChatTransport,
  SessionMeta,
  SourceDocument,
  StreamChatRequest,
} from './types';

function createRealTransport(baseUrl: string): ChatTransport {
  async function* streamChat(
    req: StreamChatRequest,
    signal: AbortSignal,
  ): AsyncGenerator<ChatEvent> {
    let res: Response;
    try {
      res = await fetch(`${baseUrl}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ session_id: req.sessionId ?? undefined, message: req.message }),
        signal,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      yield { type: 'error', message: 'Could not reach the chat service.' };
      return;
    }

    if (!res.ok || !res.body) {
      yield { type: 'error', message: `Chat request failed (${res.status}).` };
      return;
    }

    yield* parseSSEStream(res.body);
  }

  return {
    streamChat,

    // Sessions are not persisted server-side: `chat_sessions` and `messages`
    // are both RLS'd to `auth.uid()` and there is no auth yet, so the backend
    // mints a session id per conversation and stores nothing against it. Both
    // of these return empty rather than calling a route that does not exist.
    // ChatProvider handles that — it keeps the current conversation in memory,
    // so the sidebar works for the life of the page and resets on reload.
    async listSessions(): Promise<SessionMeta[]> {
      return [];
    },

    async getMessages(): Promise<ChatMessage[]> {
      return [];
    },

    async getDocument(docId: string, docType: 'case' | 'policy'): Promise<SourceDocument | null> {
      // Cases and policies are separate tables (and separate Qdrant
      // collections) now, so there is no single `/documents/{id}` route —
      // `docType` picks which one to query.
      const collectionPath = docType === 'case' ? 'cases' : 'policies';
      try {
        const res = await fetch(`${baseUrl}/${collectionPath}/${docId}`);
        if (!res.ok) {
          console.warn(`getDocument(${docId}): backend responded ${res.status}`);
          return null;
        }
        const data = await res.json();
        return {
          id: data.id ?? docId,
          title: data.title ?? docId,
          doc_type: data.doc_type ?? docType,
          department: data.department ?? data.department_id ?? null,
          storage_path: data.storage_path ?? null,
          // Accept whichever name the endpoint settles on.
          url: data.url ?? data.signed_url ?? data.download_url ?? null,
          status: data.status ?? null,
        };
      } catch (err) {
        console.warn(`getDocument(${docId}): request failed`, err);
        return null;
      }
    },

    async saveTurn(): Promise<void> {
      // no-op: the real backend persists messages server-side during the chat stream
    },
  };
}

export { createRealTransport };
