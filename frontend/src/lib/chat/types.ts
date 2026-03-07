export interface Citation {
  doc_id: string;
  chunk_id: string;
  title: string;
  snippet: string;
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
  /** Mock-only persistence hook; real backend persists server-side, so this is a no-op there. */
  saveTurn(sessionId: string, user: ChatMessage, assistant: ChatMessage): Promise<void>;
}
