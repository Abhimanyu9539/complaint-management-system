import { PanelLeft } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { ICON_SIZE, IconButton } from '@/components/ui/IconButton';
import type { AsyncData } from '@/hooks/useAsyncData';
import type { Page } from '@/lib/admin/types';
import type { Ticket } from '@/lib/tickets/types';
import { QueueRail } from './QueueRail';

interface WorkbenchShellProps {
  queue: AsyncData<Page<Ticket>>;
  statusFilter: string;
  onStatusFilterChange(value: string): void;
  search: string;
  onSearchChange(value: string): void;
  selectedId: string | null;
  onSelect(id: string): void;
  departmentLabel(id: string | null): string;
  children: ReactNode;
}

/**
 * The complaint workbench's shell: a slim topbar, the queue rail (318px on
 * `md` and up, a scrim drawer below it — the same responsive pattern
 * `AppShell` and `AdminShell` already use), and the bench.
 */
export function WorkbenchShell({
  queue,
  statusFilter,
  onStatusFilterChange,
  search,
  onSearchChange,
  selectedId,
  onSelect,
  departmentLabel,
  children,
}: WorkbenchShellProps) {
  const [mobileQueueOpen, setMobileQueueOpen] = useState(false);

  const railProps = {
    queue,
    statusFilter,
    onStatusFilterChange,
    search,
    onSearchChange,
    selectedId,
    onSelect,
    departmentLabel,
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex h-13 shrink-0 items-center gap-2 border-b border-border px-3">
        <IconButton
          onClick={() => setMobileQueueOpen(true)}
          aria-label="Open queue"
          className="md:hidden"
        >
          <PanelLeft size={ICON_SIZE} strokeWidth={1.75} />
        </IconButton>

        <div className="flex min-w-0 items-center gap-2 pl-1">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-accent-text">
            <span className="font-display text-[13px] leading-none">R</span>
          </div>
          <span className="truncate font-display text-[14px] font-medium text-text">Resolvr</span>
        </div>

        <span className="flex-1" />

        <span className="hidden text-[11.5px] text-text-faint sm:inline">
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px]">
            J
          </kbd>
          /
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px]">
            K
          </kbd>{' '}
          next / previous ticket
        </span>
      </header>

      <div className="flex min-h-0 flex-1 md:grid md:grid-cols-[318px_1fr]">
        <aside className="hidden min-h-0 overflow-hidden border-r border-border md:block">
          <QueueRail {...railProps} />
        </aside>

        {mobileQueueOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <button
              type="button"
              aria-label="Close queue"
              onClick={() => setMobileQueueOpen(false)}
              className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
            />
            <div className="absolute inset-y-0 left-0 w-[88%] max-w-80 border-r border-border shadow-xl">
              <QueueRail {...railProps} onCloseMobile={() => setMobileQueueOpen(false)} />
            </div>
          </div>
        )}

        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
