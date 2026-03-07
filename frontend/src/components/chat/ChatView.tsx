import { TriangleAlert } from 'lucide-react';
import { useChat } from '@/state/ChatProvider';
import { EmptyState } from './EmptyState';
import { MessageList } from './MessageList';
import { Composer } from './Composer';

export function ChatView() {
  const { messages, pendingUserMessage, status, error } = useChat();
  const isEmpty = messages.length === 0 && !pendingUserMessage;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {status === 'error' && error && (
        <div className="mx-4 mt-3 flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-[13px] text-danger">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </div>
      )}

      {isEmpty ? <EmptyState /> : <MessageList />}
      <Composer />
    </div>
  );
}
