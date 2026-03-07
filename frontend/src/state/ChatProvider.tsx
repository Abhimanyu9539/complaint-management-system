import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from 'react';
import { useChatStream } from '@/hooks/useChatStream';
import { newId } from '@/lib/id';
import { transport, useMock } from '@/lib/chat/transport';
import type { ChatMessage, SessionMeta } from '@/lib/chat/types';
import { chatReducer, initialChatState } from './chatReducer';

interface ChatContextValue {
  sessions: SessionMeta[];
  sessionsLoaded: boolean;
  activeSessionId: string | null;
  messages: ChatMessage[];
  pendingUserMessage: ChatMessage | null;
  streamingText: string;
  status: 'idle' | 'streaming' | 'error';
  error: string | null;
  isMock: boolean;
  sendMessage(text: string): void;
  stopStreaming(): void;
  selectSession(id: string): void;
  newChat(): void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

function titleFromMessage(message: string): string {
  const trimmed = message.trim().replace(/\s+/g, ' ');
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed || 'New conversation';
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const chatStream = useChatStream(transport);
  const messagesCache = useRef(new Map<string, ChatMessage[]>());
  const activeSessionIdRef = useRef<string | null>(null);
  activeSessionIdRef.current = state.activeSessionId;

  useEffect(() => {
    let cancelled = false;
    transport.listSessions().then((sessions) => {
      if (!cancelled) dispatch({ type: 'SESSIONS_LOADED', sessions });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectSession = useCallback(
    (id: string) => {
      if (id === activeSessionIdRef.current) return;
      if (chatStream.status === 'streaming') chatStream.stop();

      const cached = messagesCache.current.get(id);
      if (cached) {
        dispatch({ type: 'SESSION_SELECTED', sessionId: id, messages: cached });
        return;
      }
      transport.getMessages(id).then((messages) => {
        messagesCache.current.set(id, messages);
        dispatch({ type: 'SESSION_SELECTED', sessionId: id, messages });
      });
    },
    [chatStream],
  );

  const newChat = useCallback(() => {
    if (chatStream.status === 'streaming') chatStream.stop();
    dispatch({ type: 'NEW_CHAT' });
  }, [chatStream]);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || chatStream.status === 'streaming') return;

      const userMessage: ChatMessage = {
        id: newId(),
        role: 'user',
        content: trimmed,
        createdAt: new Date().toISOString(),
      };
      const sessionIdAtSend = activeSessionIdRef.current;
      dispatch({ type: 'USER_MESSAGE_SENT', message: userMessage });

      chatStream.start(
        { sessionId: sessionIdAtSend, message: trimmed },
        {
          onDone: async ({ text: answerText, citations, sessionId, interrupted }) => {
            const assistantMessage: ChatMessage = {
              id: newId(),
              role: 'assistant',
              content: answerText,
              citations,
              createdAt: new Date().toISOString(),
              interrupted,
            };

            const finalSessionId = sessionId ?? sessionIdAtSend;
            if (!finalSessionId || !answerText) return;

            await transport.saveTurn(finalSessionId, userMessage, assistantMessage);

            const priorMessages = messagesCache.current.get(finalSessionId) ?? [];
            const nextMessages = [...priorMessages, userMessage, assistantMessage];
            messagesCache.current.set(finalSessionId, nextMessages);

            const refreshedSessions = await transport.listSessions();
            const sessionMeta = refreshedSessions.find((s) => s.id === finalSessionId) ?? {
              id: finalSessionId,
              title: titleFromMessage(userMessage.content),
              createdAt: userMessage.createdAt,
              updatedAt: assistantMessage.createdAt,
            };

            dispatch({
              type: 'TURN_COMMITTED',
              sessionId: finalSessionId,
              userMessage,
              assistantMessage,
              session: sessionMeta,
            });
          },
        },
      );
    },
    [chatStream],
  );

  const value = useMemo<ChatContextValue>(
    () => ({
      sessions: state.sessions,
      sessionsLoaded: state.sessionsLoaded,
      activeSessionId: state.activeSessionId,
      messages: state.messages,
      pendingUserMessage: state.pendingUserMessage,
      streamingText: chatStream.streamingText,
      status: chatStream.status,
      error: chatStream.error,
      isMock: useMock,
      sendMessage,
      stopStreaming: chatStream.stop,
      selectSession,
      newChat,
    }),
    [state, chatStream, sendMessage, selectSession, newChat],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within a ChatProvider');
  return ctx;
}
