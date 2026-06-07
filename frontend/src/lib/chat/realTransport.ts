import { parseSSEStream } from './sse';
import type {
  ChatEvent,
  ChatMessage,
  ChatTransport,
  Citation,
  SessionMeta,
  SourceDocument,
  StreamChatRequest,
} from './types';

// The sidebar index only: which conversations exist and what to call them.
// Message bodies are never kept here — see `saveTurn` for why.
const SESSIONS_KEY = 'cms.sessions.v1';

function loadSessions(): SessionMeta[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: SessionMeta[]): void {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
  } catch {
    // storage unavailable — the sidebar just won't survive a reload
  }
}

function titleFor(message: string): string {
  const trimmed = message.trim().replace(/\s+/g, ' ');
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed || 'New conversation';
}

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

    // Transcripts live server-side, in the graph's Mongo checkpointer. The
    // *index* of which sessions exist is local, because listing them on the
    // server would mean listing every anonymous user's — there is no auth yet
    // to scope it to one person. Swap this for a `GET /chat/sessions` when
    // there is.
    async listSessions(): Promise<SessionMeta[]> {
      return loadSessions().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    },

    async getMessages(sessionId: string): Promise<ChatMessage[]> {
      try {
        const res = await fetch(
          `${baseUrl}/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
        );
        if (!res.ok) {
          console.warn(`getMessages(${sessionId}): backend responded ${res.status}`);
          return [];
        }
        const rows = await res.json();
        if (!Array.isArray(rows)) return [];
        return rows.map((row) => ({
          id: row.id,
          role: row.role as 'user' | 'assistant',
          content: row.content ?? '',
          citations: (row.citations ?? []) as Citation[],
          createdAt: row.created_at ?? '',
        }));
      } catch (err) {
        console.warn(`getMessages(${sessionId}): request failed`, err);
        return [];
      }
    },

    async deleteSession(sessionId: string): Promise<boolean> {
      try {
        const res = await fetch(
          `${baseUrl}/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`,
          { method: 'DELETE' },
        );
        if (!res.ok) {
          console.warn(`deleteSession(${sessionId}): backend responded ${res.status}`);
          return false;
        }
      } catch (err) {
        console.warn(`deleteSession(${sessionId}): request failed`, err);
        return false;
      }
      // Only drop it from the index once the server has, so a failed delete
      // never hides a transcript that is still stored.
      saveSessions(loadSessions().filter((s) => s.id !== sessionId));
      return true;
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

    async saveTurn(sessionId: string, userMessage: ChatMessage): Promise<void> {
      // Index only. The message bodies are already stored server-side by
      // `record_turn`, and writing them here too would drift: stopping a stream
      // mid-answer still fires this, but the server stored nothing for that
      // turn, so the local copy would be a message the transcript denies.
      const sessions = loadSessions();
      const existing = sessions.find((s) => s.id === sessionId);
      const updatedAt = new Date().toISOString();

      if (existing) {
        existing.updatedAt = updatedAt;
      } else {
        sessions.unshift({
          id: sessionId,
          title: titleFor(userMessage.content),
          createdAt: userMessage.createdAt,
          updatedAt,
        });
      }
      saveSessions(sessions);
    },
  };
}

export { createRealTransport };
