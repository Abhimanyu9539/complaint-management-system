import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { ChatProvider } from '@/state/ChatProvider';
import { CitationsPanelProvider } from '@/state/CitationsPanelProvider';

/**
 * `/chat` — the agent-facing assistant.
 *
 * A separate module from `App.tsx` (rather than a function declared inline)
 * specifically so it can be the target of a `React.lazy` import — see the
 * docblock on `ChatRoute` in `App.tsx` for why chat's providers live here and
 * mount only on this route.
 */
export function ChatRoute() {
  return (
    <ChatProvider>
      <CitationsPanelProvider>
        <AppShell>
          <ChatView />
        </AppShell>
      </CitationsPanelProvider>
    </ChatProvider>
  );
}
