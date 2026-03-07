import { Sparkles } from 'lucide-react';
import { SUGGESTED_PROMPTS } from '@/lib/chat/mockData';
import { useChat } from '@/state/ChatProvider';

export function EmptyState() {
  const { sendMessage } = useChat();

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto px-4 py-10">
      <div className="w-full max-w-2xl text-center">
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          <Sparkles size={22} strokeWidth={1.75} />
        </div>
        <h1 className="font-display text-[26px] font-medium text-text">
          How can I help with a complaint?
        </h1>
        <p className="mx-auto mt-2 max-w-md text-[14px] text-text-muted">
          Ask about a policy, an error code, or how to route a case — I'll ground the answer
          in the knowledge base and cite my sources.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => sendMessage(prompt)}
              className="rounded-xl border border-border bg-bg-elevated px-4 py-3 text-left text-[13px] leading-snug text-text-muted shadow-sm transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-text"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
