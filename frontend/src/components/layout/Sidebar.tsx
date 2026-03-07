import { PanelLeftClose, SquarePen } from 'lucide-react';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import { useChat } from '@/state/ChatProvider';
import { PalettePicker } from './PalettePicker';
import { SessionItem } from './SessionItem';
import { ThemeToggle } from './ThemeToggle';

interface SidebarProps {
  /** Closes the mobile drawer (also fired after selecting a session). */
  onCloseMobile?: () => void;
  /** Collapses the persistent desktop sidebar. */
  onCollapse?: () => void;
}

export function Sidebar({ onCloseMobile, onCollapse }: SidebarProps) {
  const { sessions, activeSessionId, sessionsLoaded, selectSession, newChat, isMock } = useChat();

  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex h-13 shrink-0 items-center justify-between gap-2 border-b border-border px-3">
        <div className="flex min-w-0 items-center gap-2 pl-1">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-accent-text">
            <span className="font-display text-[13px] leading-none">C</span>
          </div>
          <span className="truncate font-display text-[14px] font-medium text-text">
            Complaint Assistant
          </span>
        </div>
        <IconButton
          onClick={onCollapse ?? onCloseMobile}
          aria-label="Collapse conversations"
          title="Collapse conversations"
        >
          <PanelLeftClose size={ICON_SIZE} strokeWidth={1.75} />
        </IconButton>
      </div>

      <div className="p-3">
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

      <div className="border-t border-border">
        <PalettePicker />
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
