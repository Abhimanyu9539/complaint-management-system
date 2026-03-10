import { Link } from 'react-router';
import { FileQuestion } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';

export function NotFoundRoute() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState
        icon={<FileQuestion size={22} strokeWidth={1.5} />}
        title="Page not found"
        description="That address does not match anything in this app."
        action={
          <Link
            to="/"
            className="inline-flex items-center rounded-lg border border-border bg-bg-elevated px-3 py-2 text-[13px] font-medium text-text shadow-sm transition-colors hover:border-border-strong hover:bg-surface-hover"
          >
            Back to chat
          </Link>
        }
      />
    </div>
  );
}
