import type { ReactNode } from 'react';
import { Link, Navigate, useLocation } from 'react-router';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { useAuth } from '@/state/AuthProvider';

interface RequireAuthProps {
  /** Only admins may see this route. Agents get a refusal, not a redirect. */
  role?: 'admin';
  children: ReactNode;
}

/** Renders its route only for a signed-in agent the API accepts; sends anyone else to `/login`. */
export function RequireAuth({ role, children }: RequireAuthProps) {
  const { status, me, error, signOut, retry } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <div className="h-full w-full bg-bg" aria-busy="true" aria-label="Loading" />;
  }
  if (status === 'signed_out') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (status === 'error' || !me) {
    return (
      <AccessProblem title="You can't use the workbench yet" message={error ?? ''} onRetry={retry}>
        <Button size="sm" onClick={() => void signOut()}>
          Sign out
        </Button>
      </AccessProblem>
    );
  }
  if (role === 'admin' && me.role !== 'admin') {
    return (
      <AccessProblem
        title="Admins only"
        message="The admin panel is for admins. Ask an admin if you need access."
      >
        <Link
          to="/"
          className="inline-flex h-8 items-center rounded-lg border border-border bg-bg-elevated px-2.5 text-[12px] font-medium text-text shadow-sm transition-colors hover:border-border-strong hover:bg-surface-hover"
        >
          Back to workbench
        </Link>
      </AccessProblem>
    );
  }
  return children;
}

interface AccessProblemProps {
  title: string;
  message: string;
  onRetry?(): void;
  children: ReactNode;
}

function AccessProblem({ title, message, onRetry, children }: AccessProblemProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-bg p-6">
      <ErrorState title={title} message={message} onRetry={onRetry} />
      {children}
    </div>
  );
}
