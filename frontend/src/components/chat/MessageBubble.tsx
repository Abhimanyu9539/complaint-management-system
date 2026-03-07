import { Sparkles, TriangleAlert, User } from 'lucide-react';
import type { ChatMessage } from '@/lib/chat/types';
import { CitationChips } from './CitationChips';
import { Markdown } from './Markdown';
import { TypingCursor } from './TypingCursor';

interface MessageBubbleProps {
  message: ChatMessage;
  streaming?: boolean;
}

export function MessageBubble({ message, streaming }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end gap-3 px-4 md:px-0">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-accent px-4 py-2.5 text-[14.5px] leading-relaxed text-accent-text shadow-sm">
          {message.content}
        </div>
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-muted">
          <User size={14} strokeWidth={2} />
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex gap-3 px-4 md:px-0"
      style={{ animation: 'fade-in-up 0.25s ease-out' }}
    >
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
        <Sparkles size={14} strokeWidth={2} />
      </div>
      <div className="min-w-0 max-w-[80%] flex-1">
        <div className="rounded-2xl rounded-tl-sm bg-surface px-4 py-3 shadow-sm ring-1 ring-border">
          <Markdown content={message.content} />
          {streaming && <TypingCursor />}
        </div>
        {!streaming && message.citations && message.citations.length > 0 && (
          <CitationChips messageId={message.id} citations={message.citations} />
        )}
        {message.interrupted && (
          <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-text-faint">
            <TriangleAlert size={12} strokeWidth={2} />
            Response stopped
          </div>
        )}
      </div>
    </div>
  );
}
