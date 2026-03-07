import { PanelLeftClose, SquarePen } from 'lucide-react';
import { useChat } from '@/state/ChatProvider';
import { SessionItem } from './SessionItem';
import { ThemeToggle } from './ThemeToggle';

interface SidebarProps {
  onCloseMobile?: () => void;
}

export function Sidebar({ onCloseMobile }: SidebarProps) {
  const { sessions, activeSessionId, sessionsLoaded, selectSession, newChat, isMock } = useChat();

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-accent-text">
            <span className="font-display text-[15px] leading-none">C</span>
          </div>
          <span className="font-display text-[15px] font-medium text-text">Complaint Assistant</span>
        </div>
        <button
          type="button"
          onClick={onCloseMobile}
          className="rounded-md p-1.5 text-text-muted hover:bg-surface-hover hover:text-text md:hidden"
          aria-label="Close sidebar"
        >
          <PanelLeftClose size={16} strokeWidth={1.75} />
        </button>
      </div>

      <div className="px-3 pt-2 pb-3">
        <button
          type="button"
          onClick={() => {
            newChat();
            onCloseMobile?.();
          }}
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-bg-elevated px-3 py-2.5 text-[13px] font-medium text-text shadow-sm transition-colors hover:border-border-strong hover:bg-surface-hover"
        >
          <SquarePen size={15} strokeWidth={1.75} />
          New chat
        </button>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {!sessionsLoaded ? null : sessions.length === 0 ? (
          <p className="px-3 py-2 text-[12px] text-text-faint">
            Your conversations will show up here.
          </p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {sessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                active={session.id === activeSessionId}
                onSelect={() => {
                  selectSession(session.id);
                  onCloseMobile?.();
                }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-border px-4 py-3">
        {isMock ? (
          <span className="rounded-full bg-accent-soft px-2.5 py-1 text-[11px] font-medium text-accent">
            Mock mode
          </span>
        ) : (
          <span className="text-[11px] text-text-faint">Connected</span>
        )}
        <ThemeToggle />
      </div>
    </div>
  );
}
