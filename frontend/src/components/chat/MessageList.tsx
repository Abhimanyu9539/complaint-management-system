import { ArrowDown } from 'lucide-react';
import { useChat } from '@/state/ChatProvider';
import { useAutoScroll } from '@/hooks/useAutoScroll';
import { MessageBubble } from './MessageBubble';
import { ThinkingDots } from './TypingCursor';

export function MessageList() {
  const { messages, pendingUserMessage, streamingText, status } = useChat();
  const { containerRef, pinnedToBottom, handleScroll, scrollToBottom } = useAutoScroll(
    `${messages.length}:${streamingText.length}:${pendingUserMessage?.id ?? ''}`,
  );

  const isStreaming = status === 'streaming';

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="scrollbar-thin h-full overflow-y-auto"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {pendingUserMessage && (
            <MessageBubble key={pendingUserMessage.id} message={pendingUserMessage} />
          )}

          {isStreaming &&
            (streamingText ? (
              <MessageBubble
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingText,
                  createdAt: new Date().toISOString(),
                }}
                streaming
              />
            ) : (
              <div className="flex gap-3 px-4 md:px-0">
                <div className="mt-0.5 h-7 w-7 shrink-0 rounded-full bg-accent-soft" />
                <div className="rounded-2xl rounded-tl-sm bg-surface px-4 py-3 shadow-sm ring-1 ring-border">
                  <ThinkingDots />
                </div>
              </div>
            ))}
        </div>
      </div>

      {!pinnedToBottom && (
        <button
          type="button"
          onClick={() => scrollToBottom()}
          className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-border bg-bg-elevated px-3 py-1.5 text-[12px] font-medium text-text-muted shadow-md transition-colors hover:text-text"
        >
          <ArrowDown size={13} strokeWidth={2} />
          Jump to latest
        </button>
      )}
    </div>
  );
}
