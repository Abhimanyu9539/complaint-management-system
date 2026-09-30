import { Link } from 'react-router';
import { FileQuestion } from 'lucide-react';
import { BrandMark } from '@/components/layout/BrandMark';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { EmptyState } from '@/components/ui/EmptyState';

/** `withHeader` is off inside the admin shell, which has its own navigation. */
export function NotFoundRoute({ withHeader = true }: { withHeader?: boolean }) {
  return (
    <div className="flex h-full flex-col bg-bg">
      {withHeader && (
        <header className="flex h-13 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
          <BrandMark />
          <ThemeToggle />
        </header>
      )}
      <div className="flex min-h-0 flex-1 items-center justify-center p-6">
        <EmptyState
          icon={<FileQuestion size={22} strokeWidth={1.5} />}
          title="Page not found"
          description="That address does not match anything in this app."
          action={
            <Link
              to="/"
              className="inline-flex items-center rounded-lg border border-border bg-bg-elevated px-3 py-2 text-[13px] font-medium text-text shadow-sm transition-colors hover:border-border-strong hover:bg-surface-hover"
            >
              Back to workbench
            </Link>
          }
        />
      </div>
    </div>
  );
}
