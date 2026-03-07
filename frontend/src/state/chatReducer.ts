import type { ChatMessage, SessionMeta } from '@/lib/chat/types';

export interface ChatState {
  sessions: SessionMeta[];
  activeSessionId: string | null;
  messages: ChatMessage[];
  pendingUserMessage: ChatMessage | null;
  sessionsLoaded: boolean;
}

export type ChatAction =
  | { type: 'SESSIONS_LOADED'; sessions: SessionMeta[] }
  | { type: 'SESSION_SELECTED'; sessionId: string; messages: ChatMessage[] }
  | { type: 'NEW_CHAT' }
  | { type: 'USER_MESSAGE_SENT'; message: ChatMessage }
  | {
      type: 'TURN_COMMITTED';
      sessionId: string;
      userMessage: ChatMessage;
      assistantMessage: ChatMessage;
      session: SessionMeta;
    };

export const initialChatState: ChatState = {
  sessions: [],
  activeSessionId: null,
  messages: [],
  pendingUserMessage: null,
  sessionsLoaded: false,
};

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SESSIONS_LOADED':
      return { ...state, sessions: action.sessions, sessionsLoaded: true };

    case 'SESSION_SELECTED':
      return {
        ...state,
        activeSessionId: action.sessionId,
        messages: action.messages,
        pendingUserMessage: null,
      };

    case 'NEW_CHAT':
      return { ...state, activeSessionId: null, messages: [], pendingUserMessage: null };

    case 'USER_MESSAGE_SENT':
      return { ...state, pendingUserMessage: action.message };

    case 'TURN_COMMITTED': {
      const existingIndex = state.sessions.findIndex((s) => s.id === action.sessionId);
      const sessions =
        existingIndex === -1
          ? [action.session, ...state.sessions]
          : [
              action.session,
              ...state.sessions.slice(0, existingIndex),
              ...state.sessions.slice(existingIndex + 1),
            ];

      return {
        ...state,
        sessions,
        activeSessionId: action.sessionId,
        messages: [...state.messages, action.userMessage, action.assistantMessage],
        pendingUserMessage: null,
      };
    }

    default:
      return state;
  }
}
