import { PanelLeft } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Outlet } from 'react-router';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import { AdminSidebar } from './AdminSidebar';

/**
 * Layout route for every admin page.
 *
 * Mirrors `AppShell`'s structure — a persistent 260px rail on `md` and up, a
 * scrim-dismissible slide-over below it — so the two areas of the app feel like
 * one product. The admin side has no third rail, so the grid is simpler.
 *
 * Unlike the chat shell, the content column here *does* scroll: dashboards are
 * long, and the fixed-viewport rule that suits a message list would force every
 * panel into a nested scroll container.
 */
export function AdminShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex h-full flex-col overflow-hidden md:grid md:grid-cols-[260px_1fr]">
      <aside className="hidden min-h-0 overflow-hidden border-r border-border md:block">
        <AdminSidebar />
      </aside>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileNavOpen(false)}
            className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
          />
          <div className="absolute inset-y-0 left-0 w-[85%] max-w-72 border-r border-border shadow-xl">
            <AdminSidebar onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
          <Outlet context={{ openMobileNav: () => setMobileNavOpen(true) }} />
        </div>
      </main>
    </div>
  );
}

interface AdminPageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  onOpenNav?: () => void;
}

/**
 * The sticky per-page header rail.
 *
 * Each page renders its own so the actions (a day-range select, the live
 * indicator) belong to the page rather than being threaded down through the
 * layout route.
 */
export function AdminPageHeader({ title, description, actions, onOpenNav }: AdminPageHeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex min-h-13 shrink-0 items-center gap-2 border-b border-border bg-bg/95 px-4 py-2 backdrop-blur">
      {onOpenNav && (
        <IconButton onClick={onOpenNav} aria-label="Open navigation" className="md:hidden">
          <PanelLeft size={ICON_SIZE} strokeWidth={1.75} />
        </IconButton>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[14px] font-semibold text-text">{title}</h1>
        {description && (
          <p className="truncate text-[11.5px] text-text-muted">{description}</p>
        )}
      </div>
      {actions}
    </header>
  );
}
