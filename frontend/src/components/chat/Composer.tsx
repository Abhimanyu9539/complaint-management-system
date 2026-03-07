import { useState, type KeyboardEvent } from 'react';
import { ArrowUp, Square } from 'lucide-react';
import { useAutosizeTextarea } from '@/hooks/useAutosizeTextarea';
import { useChat } from '@/state/ChatProvider';

export function Composer() {
  const { sendMessage, stopStreaming, status } = useChat();
  const [value, setValue] = useState('');
  const textareaRef = useAutosizeTextarea(value);
  const isStreaming = status === 'streaming';

  const submit = () => {
    if (!value.trim() || isStreaming) return;
    sendMessage(value);
    setValue('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-border bg-bg px-4 pt-3 pb-4 md:px-0">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-bg-elevated px-3 py-2 shadow-sm transition-colors focus-within:border-border-strong">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask about a policy, error code, or how to route a complaint…"
            className="max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent py-1 text-[14px] leading-relaxed text-text placeholder:text-text-faint focus:outline-none"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={stopStreaming}
              aria-label="Stop generating"
              title="Stop generating"
              className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-text text-bg transition-opacity hover:opacity-85"
            >
              <Square size={13} strokeWidth={2.5} fill="currentColor" />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!value.trim()}
              aria-label="Send message"
              title="Send message"
              className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-accent-text transition-opacity enabled:hover:opacity-90 disabled:opacity-35"
            >
              <ArrowUp size={15} strokeWidth={2.5} />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[11px] text-text-faint">
          Enter to send · Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}
