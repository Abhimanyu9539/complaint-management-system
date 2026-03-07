import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { ChatProvider } from '@/state/ChatProvider';
import { ThemeProvider } from '@/state/ThemeProvider';

function App() {
  return (
    <ThemeProvider>
      <ChatProvider>
        <AppShell>
          <ChatView />
        </AppShell>
      </ChatProvider>
    </ThemeProvider>
  );
}

export default App;
