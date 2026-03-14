import { ChevronsUpDown, Gauge, Inbox, MessageCircle, MessageSquarePlus } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router';
import { ICON_SIZE } from '@/components/ui/IconButton';
import { PalettePicker } from './PalettePicker';
import { ThemeToggle } from './ThemeToggle';

interface Destination {
  to: string;
  label: string;
  description: string;
  icon: typeof Inbox;
}

const DESTINATIONS: Destination[] = [
  { to: '/', label: 'Workbench', description: 'Triage the complaint queue', icon: Inbox },
  { to: '/chat', label: 'Chat', description: 'Ask the agent about a complaint', icon: MessageCircle },
  { to: '/admin', label: 'Admin', description: 'Dashboards, ingestion, activity, stats', icon: Gauge },
  { to: '/ticket', label: 'Intake', description: 'Customer complaint form', icon: MessageSquarePlus },
];

function matchDestination(pathname: string): Destination {
  if (pathname === '/') return DESTINATIONS[0];
  return (
    DESTINATIONS.find((d) => d.to !== '/' && (pathname === d.to || pathname.startsWith(`${d.to}/`))) ??
    DESTINATIONS[0]
  );
}

interface SidebarFooterProps {
  /** Whether this surface is serving simulated data. */
  mocked: boolean;
  /** `title` text explaining why, shown on the mock badge. */
  mockedReason?: string;
  /** Closes the mobile drawer this sidebar is rendered inside, if any. */
  onNavigate?(): void;
}

/**
 * The bottom row shared by every sidebar: a single trigger that opens a popover
 * with the four area destinations, the colour picker, and the connection badge —
 * replacing what used to be three bare links plus a whole extra row per sidebar.
 */
export function SidebarFooter({ mocked, mockedReason, onNavigate }: SidebarFooterProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const firstLinkRef = useRef<HTMLAnchorElement | null>(null);
  const { pathname } = useLocation();
  const active = matchDestination(pathname);

  useEffect(() => {
    if (!open) return;

    const trigger = triggerRef.current;
    firstLinkRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      trigger?.focus?.();
    };
  }, [open]);

  const close = () => {
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div className="relative border-t border-border px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <button
          ref={triggerRef}
          type="button"
          aria-haspopup="true"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2 text-[12px] font-medium text-text-muted transition-colors hover:bg-surface-hover hover:text-text"
        >
          <active.icon size={ICON_SIZE} strokeWidth={1.75} />
          {active.label}
          <ChevronsUpDown size={14} strokeWidth={1.75} className="text-text-faint" />
        </button>

        <ThemeToggle />
      </div>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40"
          />
          <div
            role="dialog"
            aria-label="Switch area"
            className="absolute right-3 bottom-full left-3 z-50 mb-2 overflow-hidden rounded-xl border border-border bg-bg-elevated shadow-xl"
            style={{ animation: 'fade-in-up 0.15s ease-out' }}
          >
            <nav aria-label="Switch area" className="flex flex-col gap-0.5 p-1.5">
              {DESTINATIONS.map((destination, index) => (
                <NavLink
                  key={destination.to}
                  ref={index === 0 ? firstLinkRef : undefined}
                  to={destination.to}
                  end={destination.to === '/'}
                  onClick={close}
                  className={({ isActive }) =>
                    `flex items-start gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors ${
                      isActive
                        ? 'bg-accent-soft text-accent'
                        : 'text-text-muted hover:bg-surface-hover hover:text-text'
                    }`
                  }
                >
                  <destination.icon size={ICON_SIZE} strokeWidth={1.75} className="mt-0.5 shrink-0" />
                  <span className="min-w-0">
                    <span className="block truncate">{destination.label}</span>
                    <span className="block truncate text-[11px] font-normal text-text-faint">
                      {destination.description}
                    </span>
                  </span>
                </NavLink>
              ))}
            </nav>

            <div className="border-t border-border">
              <PalettePicker />
            </div>

            <div className="border-t border-border px-4 py-3">
              {mocked ? (
                <span
                  title={mockedReason}
                  className="rounded-full bg-warn-soft px-2.5 py-1 text-[11px] font-medium text-warn"
                >
                  Mock mode
                </span>
              ) : (
                <span className="text-[11px] text-text-faint">Connected</span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
