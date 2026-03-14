import { Suspense, lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router';
import { WorkbenchPage } from '@/pages/WorkbenchPage';
import { NotFoundRoute } from '@/pages/NotFoundRoute';
import { ThemeProvider } from '@/state/ThemeProvider';

/**
 * The admin panel carries the chart primitives, four page trees and the whole
 * admin transport — none of which a workbench user ever loads. `lazy` needs a
 * default export and the house style is named exports, so the mapping happens
 * here rather than by adding a default export to the module.
 */
const AdminRoutes = lazy(() =>
  import('@/components/admin/AdminRoutes').then((module) => ({ default: module.AdminRoutes })),
);

/**
 * The customer complaint form. Lazy for the same reason as the admin panel: it
 * pulls in the form primitives, and neither the workbench nor chat needs them.
 *
 * Mounted as a sibling of `/` — a customer arriving here is not a workbench
 * operator, and must not pay for the admin ticket transport this route's
 * neighbour does not use either.
 */
const TicketFormPage = lazy(() =>
  import('@/pages/TicketFormPage').then((module) => ({ default: module.TicketFormPage })),
);

/**
 * The agent chat. No longer the landing page — see `WorkbenchPage`, which took
 * `/` because the thing this system exists for is triaging complaints, not
 * talking to an assistant. Lazy for the same reason the admin panel is: chat
 * pulls in `react-markdown`, `remark-gfm` and its own transport, none of which
 * the workbench or the customer form need.
 *
 * Chat's providers live inside this route so they mount only on `/chat`.
 * `ChatProvider` fires `transport.listSessions()` on mount; hoisting it to the
 * app root would make every other page load fetch a session list that nothing
 * renders there.
 *
 * The accepted cost is that navigating away from `/chat` and back unmounts the
 * provider, discarding its in-memory message cache and re-fetching sessions.
 * Nothing is lost — sessions and messages are persisted either server-side or
 * in localStorage — and the alternative reintroduces exactly the fetch this
 * arrangement avoids.
 */
const ChatRoute = lazy(() =>
  import('@/pages/ChatRoute').then((module) => ({ default: module.ChatRoute })),
);

/** Shown while a lazy chunk downloads. Deliberately quiet — it is brief. */
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
            <Route path="/" element={<WorkbenchPage />} />
            <Route path="/chat" element={<ChatRoute />} />
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
