export interface Citation {
  doc_id: string;
  /**
   * Which corpus `doc_id` resolves in — `cases` or `policies`. Required: with
   * cases and policies stored (and retrieved) as separate collections, there is
   * no single id space left to resolve a bare `doc_id` against.
   */
  doc_type: 'case' | 'policy';
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
  department?: string | null;
}

/**
 * The `cases` or `policies` row behind a citation. `url` is a short-lived
 * Supabase Storage signed URL for the original file — null when the document
 * has no stored object or the backend cannot sign one.
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
   * original policy or case. `docType` picks which corpus to look in — cases
   * and policies are separate collections now, so the id alone isn't enough.
   * Returns null when it cannot be resolved — the UI degrades to showing the
   * retrieved snippet only.
   */
  getDocument(docId: string, docType: 'case' | 'policy'): Promise<SourceDocument | null>;
  /** Mock-only persistence hook; real backend persists server-side, so this is a no-op there. */
  saveTurn(sessionId: string, user: ChatMessage, assistant: ChatMessage): Promise<void>;
}
