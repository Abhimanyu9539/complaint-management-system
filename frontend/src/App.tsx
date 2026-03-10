import { Suspense, lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router';
import { AppShell } from '@/components/layout/AppShell';
import { ChatView } from '@/components/chat/ChatView';
import { NotFoundRoute } from '@/pages/NotFoundRoute';
import { ChatProvider } from '@/state/ChatProvider';
import { CitationsPanelProvider } from '@/state/CitationsPanelProvider';
import { ThemeProvider } from '@/state/ThemeProvider';

/**
 * The admin panel carries the chart primitives, four page trees and the whole
 * admin transport — none of which a chat user ever loads. `lazy` needs a
 * default export and the house style is named exports, so the mapping happens
 * here rather than by adding a default export to the module.
 */
const AdminRoutes = lazy(() =>
  import('@/components/admin/AdminRoutes').then((module) => ({ default: module.AdminRoutes })),
);

/**
 * The customer complaint form. Lazy for the same reason as the admin panel: it
 * pulls in the form primitives, and the chat route needs none of them.
 *
 * Mounted as a sibling of `/` rather than inside it — see `ChatRoute` below. A
 * customer arriving here is not a chat user, and must not pay for a session
 * list they will never see.
 */
const TicketFormPage = lazy(() =>
  import('@/pages/TicketFormPage').then((module) => ({ default: module.TicketFormPage })),
);

/**
 * Chat's providers live inside its route so they mount only on `/`.
 *
 * `ChatProvider` fires `transport.listSessions()` on mount; hoisting it to the
 * app root would make every admin page load fetch a session list that nothing
 * renders.
 *
 * The accepted cost is that navigating away from `/` and back unmounts the
 * provider, discarding its in-memory message cache and re-fetching sessions.
 * Nothing is lost — sessions and messages are persisted either server-side or
 * in localStorage — and the alternative reintroduces exactly the fetch this
 * arrangement avoids.
 */
function ChatRoute() {
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

/** Shown while the admin chunk downloads. Deliberately quiet — it is brief. */
function RouteFallback() {
  return <div className="h-full w-full bg-bg" aria-busy="true" aria-label="Loading" />;
}

function App() {
  return (
    <BrowserRouter>
      {/* ThemeProvider sits above the router: palette and dark mode are
          properties of the whole app, and remounting it on navigation would
          re-read localStorage and flash. */}
      <ThemeProvider>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<ChatRoute />} />
            <Route path="/ticket" element={<TicketFormPage />} />
            <Route path="/admin/*" element={<AdminRoutes />} />
            <Route path="*" element={<NotFoundRoute />} />
          </Routes>
        </Suspense>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
