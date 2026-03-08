import { newId } from '@/lib/id';
import { MOCK_ANSWERS, MOCK_DOCUMENTS, MOCK_FALLBACK_ANSWER } from './mockData';
import type {
  ChatEvent,
  ChatMessage,
  ChatTransport,
  Citation,
  SessionMeta,
  SourceDocument,
  StreamChatRequest,
} from './types';

const STORAGE_KEY = 'cms.mock.v1';

interface MockStore {
  sessions: SessionMeta[];
  messages: Record<string, ChatMessage[]>;
}

function loadStore(): MockStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { sessions: [], messages: {} };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return { sessions: [], messages: {} };
    return {
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions : [],
      messages: parsed.messages && typeof parsed.messages === 'object' ? parsed.messages : {},
    };
  } catch {
    return { sessions: [], messages: {} };
  }
}

function saveStore(store: MockStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // storage unavailable — mock sessions just won't persist across reloads
  }
}

function pickAnswer(message: string): { answer: string; citations: Citation[] } {
  for (const candidate of MOCK_ANSWERS) {
    if (candidate.match.test(message)) {
      return { answer: candidate.answer, citations: candidate.citations };
    }
  }
  return { answer: MOCK_FALLBACK_ANSWER, citations: [] };
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(abortError());
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(abortError());
      },
      { once: true },
    );
  });
}

function abortError(): DOMException {
  return new DOMException('Aborted', 'AbortError');
}

function titleFromMessage(message: string): string {
  const trimmed = message.trim().replace(/\s+/g, ' ');
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed || 'New conversation';
}

async function* streamChat(
  req: StreamChatRequest,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const { answer, citations } = pickAnswer(req.message);

  await delay(350 + Math.random() * 300, signal);

  const words = answer.match(/\S+\s*/g) ?? [answer];
  for (const word of words) {
    if (signal.aborted) throw abortError();
    yield { type: 'token', text: word };
    const burst = Math.random() < 0.08;
    await delay(burst ? 100 + Math.random() * 80 : 15 + Math.random() * 30, signal);
  }

  yield { type: 'citations', citations };

  const store = loadStore();
  let sessionId = req.sessionId;
  if (!sessionId) {
    sessionId = newId();
    const now = new Date().toISOString();
    store.sessions.unshift({
      id: sessionId,
      title: titleFromMessage(req.message),
      createdAt: now,
      updatedAt: now,
    });
    store.messages[sessionId] = [];
    saveStore(store);
  }

  yield {
    type: 'done',
    message_id: newId(),
    langsmith_run_id: null,
    session_id: sessionId,
  };
}

async function listSessions(): Promise<SessionMeta[]> {
  const store = loadStore();
  return [...store.sessions].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

async function getMessages(sessionId: string): Promise<ChatMessage[]> {
  const store = loadStore();
  return store.messages[sessionId] ?? [];
}

async function getDocument(docId: string, _docType: 'case' | 'policy'): Promise<SourceDocument | null> {
  // Mock ids are still globally unique via the `pol-`/`case-` prefix
  // convention, so a flat lookup is enough here — docType is unused, kept
  // only to satisfy the shared ChatTransport signature.
  const document = MOCK_DOCUMENTS[docId];
  if (!document) {
    console.warn(`getDocument(${docId}): no mock document registered`);
    return null;
  }
  return document;
}

async function saveTurn(sessionId: string, user: ChatMessage, assistant: ChatMessage): Promise<void> {
  const store = loadStore();
  if (!store.messages[sessionId]) store.messages[sessionId] = [];
  store.messages[sessionId].push(user, assistant);

  const session = store.sessions.find((s) => s.id === sessionId);
  const now = new Date().toISOString();
  if (session) {
    session.updatedAt = now;
  } else {
    store.sessions.unshift({
      id: sessionId,
      title: titleFromMessage(user.content),
      createdAt: now,
      updatedAt: now,
    });
  }
  saveStore(store);
}

export function createMockTransport(): ChatTransport {
  return { streamChat, listSessions, getMessages, getDocument, saveTurn };
}
