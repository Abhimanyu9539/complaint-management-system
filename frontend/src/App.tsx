import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { ChatProvider } from '@/state/ChatProvider';
import { CitationsPanelProvider } from '@/state/CitationsPanelProvider';
import { ThemeProvider } from '@/state/ThemeProvider';

function App() {
  return (
    <ThemeProvider>
      <ChatProvider>
        <CitationsPanelProvider>
          <AppShell>
            <ChatView />
          </AppShell>
        </CitationsPanelProvider>
      </ChatProvider>
    </ThemeProvider>
  );
}

export default App;
