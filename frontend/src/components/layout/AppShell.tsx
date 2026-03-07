import { useState, type ReactNode } from 'react';
import { PanelLeft } from 'lucide-react';
import { Sidebar } from './Sidebar';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="h-full md:grid md:grid-cols-[272px_1fr]">
      <aside className="hidden border-r border-border md:block">
        <Sidebar />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
          />
          <div className="absolute inset-y-0 left-0 w-[85%] max-w-72 border-r border-border shadow-xl">
            <Sidebar onCloseMobile={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <main className="flex min-w-0 flex-col">
        <div className="flex items-center gap-2 border-b border-border px-3 py-2 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-text-muted hover:bg-surface-hover hover:text-text"
            aria-label="Open sidebar"
          >
            <PanelLeft size={18} strokeWidth={1.75} />
          </button>
          <span className="font-display text-[14px] font-medium text-text">Complaint Assistant</span>
        </div>
        {children}
      </main>
    </div>
  );
}
