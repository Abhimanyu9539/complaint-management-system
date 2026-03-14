import { Activity, ChartNoAxesColumn, Import, Inbox, LayoutDashboard } from 'lucide-react';
import { NavLink } from 'react-router';
import { SidebarFooter } from '@/components/layout/SidebarFooter';
import { ICON_SIZE } from '@/components/ui/IconButton';
import { useMockAdmin } from '@/lib/admin/transport';

interface AdminSidebarProps {
  /** Closes the mobile drawer after a navigation. */
  onNavigate?: () => void;
}

const NAV_ITEMS = [
  { to: '/admin', end: true, label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/tickets', end: false, label: 'Tickets', icon: Inbox },
  { to: '/admin/ingestion', end: false, label: 'Content ingestion', icon: Import },
  { to: '/admin/activity', end: false, label: 'Agent activity', icon: Activity },
  { to: '/admin/stats', end: false, label: 'System statistics', icon: ChartNoAxesColumn },
];

/**
 * The admin navigation rail.
 *
 * `NavLink`s here are the panel's tab bar. There is no separate Tabs component
 * anywhere in the admin panel for exactly this reason — these already give the
 * active state *and* a shareable URL, which a tab component would not.
 */
export function AdminSidebar({ onNavigate }: AdminSidebarProps) {
  return (
    <div className="flex h-full flex-col bg-surface">
      <div className="flex h-13 shrink-0 items-center gap-2 border-b border-border px-3">
        <div className="flex min-w-0 items-center gap-2 pl-1">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-accent-text">
            <span className="font-display text-[13px] leading-none">R</span>
          </div>
          <span className="truncate font-display text-[14px] font-medium text-text">Admin</span>
        </div>
      </div>

      <nav className="flex flex-col gap-0.5 p-2" aria-label="Admin sections">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors ${
                isActive
                  ? 'bg-accent-soft text-accent'
                  : 'text-text-muted hover:bg-surface-hover hover:text-text'
              }`
            }
          >
            <item.icon size={ICON_SIZE} strokeWidth={1.75} className="shrink-0" />
            <span className="truncate">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="min-h-0 flex-1" />

      <SidebarFooter
        mocked={useMockAdmin}
        mockedReason="No VITE_API_BASE_URL configured — every panel is showing simulated data."
        onNavigate={onNavigate}
      />
    </div>
  );
}
