import { useEffect, useState, type ReactNode } from 'react';
import { PanelLeft, PanelRight, SquarePen } from 'lucide-react';
import { CitationsPanelContent } from '@/components/chat/CitationsPanel';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import { useActiveCitations } from '@/hooks/useActiveCitations';
import { useChat } from '@/state/ChatProvider';
import { useCitationsPanel } from '@/state/CitationsPanelProvider';
import { Sidebar } from './Sidebar';

const NAV_KEY = 'cms.nav.open';

function readStoredNavOpen(): boolean {
  try {
    const raw = localStorage.getItem(NAV_KEY);
    return raw === null ? true : raw === 'true';
  } catch {
    return true;
  }
}

export function AppShell({ children }: { children: ReactNode }) {
  // Desktop rails are persisted; the mobile drawers are session-only so a fresh
  // load never opens over a phone screen.
  const [navOpen, setNavOpen] = useState(readStoredNavOpen);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { sessions, activeSessionId, newChat } = useChat();
  const { isOpen, isMobileOpen, expand, openMobile, close } = useCitationsPanel();
  const { citations } = useActiveCitations();

  useEffect(() => {
    try {
      localStorage.setItem(NAV_KEY, String(navOpen));
    } catch {
      // storage unavailable — sidebar state just won't persist
    }
  }, [navOpen]);

  const activeTitle =
    sessions.find((session) => session.id === activeSessionId)?.title ?? 'New conversation';

  // The sources rail is only meaningful once an answer has cited something.
  const hasSources = citations.length > 0;
  const showSourcesRail = hasSources && isOpen;

  const gridCols = navOpen
    ? showSourcesRail
      ? 'md:grid-cols-[272px_1fr] lg:grid-cols-[272px_1fr_340px]'
      : 'md:grid-cols-[272px_1fr]'
    : showSourcesRail
      ? 'md:grid-cols-[1fr] lg:grid-cols-[1fr_340px]'
      : 'md:grid-cols-[1fr]';

  return (
    <div className={`flex h-full flex-col overflow-hidden md:grid ${gridCols}`}>
      {navOpen && (
        <aside className="hidden min-h-0 overflow-hidden border-r border-border md:block">
          <Sidebar onCollapse={() => setNavOpen(false)} />
        </aside>
      )}

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
            className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
          />
          <div className="absolute inset-y-0 left-0 w-[85%] max-w-72 border-r border-border shadow-xl">
            <Sidebar onCloseMobile={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-13 shrink-0 items-center gap-1.5 border-b border-border px-3">
          <IconButton
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open conversations"
            className="md:hidden"
          >
            <PanelLeft size={ICON_SIZE} strokeWidth={1.75} />
          </IconButton>

          {!navOpen && (
            <>
              <IconButton
                onClick={() => setNavOpen(true)}
                aria-label="Show conversations"
                title="Show conversations"
                className="hidden md:inline-flex"
              >
                <PanelLeft size={ICON_SIZE} strokeWidth={1.75} />
              </IconButton>
              <IconButton
                onClick={newChat}
                aria-label="New chat"
                title="New chat"
                className="hidden md:inline-flex"
              >
                <SquarePen size={ICON_SIZE} strokeWidth={1.75} />
              </IconButton>
            </>
          )}

          <h1 className="min-w-0 flex-1 truncate px-1 text-[13px] font-medium text-text">
            {activeTitle}
          </h1>

          {/* Below lg the rail is replaced by a slide-over, so the button stays.
              On desktop the rail carries its own header, so this only appears
              when the rail is collapsed — mirroring the conversations sidebar. */}
          {hasSources && (
            <>
              <IconButton
                withLabel
                onClick={openMobile}
                aria-label="Show sources"
                title="Show sources"
                className="lg:hidden"
              >
                <PanelRight size={ICON_SIZE} strokeWidth={1.75} />
                <span className="hidden sm:inline">Sources</span>
                <span className="rounded-full bg-accent px-1.5 text-[10px] font-semibold text-accent-text">
                  {citations.length}
                </span>
              </IconButton>

              {!isOpen && (
                <IconButton
                  withLabel
                  onClick={expand}
                  aria-label="Show sources"
                  title="Show sources"
                  className="hidden lg:inline-flex"
                >
                  <PanelRight size={ICON_SIZE} strokeWidth={1.75} />
                  <span>Sources</span>
                  <span className="rounded-full bg-accent px-1.5 text-[10px] font-semibold text-accent-text">
                    {citations.length}
                  </span>
                </IconButton>
              )}
            </>
          )}
        </header>

        {children}
      </main>

      {showSourcesRail && (
        <aside className="hidden min-h-0 overflow-hidden border-l border-border lg:block">
          <CitationsPanelContent />
        </aside>
      )}

      {hasSources && isMobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close sources panel"
            onClick={close}
            className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
          />
          <div className="absolute inset-y-0 right-0 w-[88%] max-w-sm border-l border-border shadow-xl">
            <CitationsPanelContent />
          </div>
        </div>
      )}
    </div>
  );
}
