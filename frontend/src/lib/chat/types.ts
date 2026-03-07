export interface Citation {
  doc_id: string;
  chunk_id: string;
  title: string;
  snippet: string;
  /**
   * Optional passthrough fields. When the backend can mint a Supabase Storage
   * signed URL at answer time it should set `document_url` and the UI links
   * straight to it; otherwise the UI resolves it lazily via
   * `ChatTransport.getDocument`.
   */
  document_url?: string | null;
  storage_path?: string | null;
  doc_type?: string | null;
  department?: string | null;
}

/**
 * The `documents` row behind a citation. `url` is a short-lived Supabase
 * Storage signed URL for the original file — null when the document has no
 * stored object or the backend cannot sign one.
 */
export interface SourceDocument {
  id: string;
  title: string;
  doc_type: string | null;
  department: string | null;
  storage_path: string | null;
  url: string | null;
  status?: string | null;
}

export type ChatEvent =
  | { type: 'token'; text: string }
  | { type: 'citations'; citations: Citation[] }
  | { type: 'done'; message_id: string; langsmith_run_id: string | null; session_id?: string }
  | { type: 'error'; message: string };

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  createdAt: string;
  interrupted?: boolean;
}

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface StreamChatRequest {
  sessionId: string | null;
  message: string;
}

export interface ChatTransport {
  streamChat(req: StreamChatRequest, signal: AbortSignal): AsyncGenerator<ChatEvent>;
  listSessions(): Promise<SessionMeta[]>;
  getMessages(sessionId: string): Promise<ChatMessage[]>;
  /**
   * Resolves the source document behind a citation so the user can open the
   * original policy or case. Returns null when it cannot be resolved — the UI
   * degrades to showing the retrieved snippet only.
   */
  getDocument(docId: string): Promise<SourceDocument | null>;
  /** Mock-only persistence hook; real backend persists server-side, so this is a no-op there. */
  saveTurn(sessionId: string, user: ChatMessage, assistant: ChatMessage): Promise<void>;
}
