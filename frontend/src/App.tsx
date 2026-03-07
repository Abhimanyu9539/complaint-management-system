import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { ChatProvider } from '@/state/ChatProvider';

function App() {
  return (
    <ChatProvider>
      <AppShell>
        <ChatView />
      </AppShell>
    </ChatProvider>
  );
}

export default App;
