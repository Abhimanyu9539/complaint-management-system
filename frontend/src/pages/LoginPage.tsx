import { TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { Link, Navigate, useLocation, type Location } from 'react-router';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { Button } from '@/components/ui/Button';
import { TextInput } from '@/components/ui/TextInput';
import { authConfigured } from '@/lib/auth/supabase';
import { useAuth } from '@/state/AuthProvider';

/**
 * Agent sign-in: email and password, or Google. Accounts are created by an admin
 * in Supabase; public signup is off, so an unknown Google account is refused and
 * comes back here with Supabase's `error_description`.
 */
export function LoginPage() {
  const { status, signInWithPassword, signInWithGoogle } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<'password' | 'google' | null>(null);
  // A refused Google sign-in comes back with the reason in the query string or the hash.
  const [error, setError] = useState<string | null>(
    () =>
      new URLSearchParams(location.search).get('error_description') ??
      new URLSearchParams(location.hash.slice(1)).get('error_description'),
  );

  if (status === 'loading') {
    return <div className="h-full w-full bg-bg" aria-busy="true" aria-label="Loading" />;
  }
  if (status !== 'signed_out') {
    const from = (location.state as { from?: Location } | null)?.from;
    return <Navigate to={from ? `${from.pathname}${from.search}` : '/'} replace />;
  }

  async function handlePassword() {
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    setBusy('password');
    setError(null);
    const message = await signInWithPassword(email.trim(), password);
    setBusy(null);
    if (message) setError(message);
  }

  async function handleGoogle() {
    setBusy('google');
    setError(null);
    const message = await signInWithGoogle();
    // On success the browser is already leaving for Google.
    if (message) {
      setBusy(null);
      setError(message);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg">
      <header className="flex h-13 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent text-accent-text">
            <span className="font-display text-[13px] leading-none">R</span>
          </div>
          <span className="truncate font-display text-[14px] font-medium text-text">Workbench</span>
        </div>
        <ThemeToggle />
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-sm flex-col gap-5 p-4 pt-10 sm:p-6 sm:pt-16">
          <div>
            <h1 className="font-display text-[22px] leading-tight font-medium text-text">Sign in</h1>
            <p className="mt-1.5 text-[13px] leading-relaxed text-text-muted">
              For support agents. Customers can{' '}
              <Link to="/ticket" className="text-accent hover:underline">
                send a complaint here
              </Link>
              .
            </p>
          </div>

          {!authConfigured && (
            <div className="flex items-start gap-2.5 rounded-xl border border-warn/30 bg-warn-soft px-3.5 py-3">
              <TriangleAlert size={16} strokeWidth={1.75} className="mt-px shrink-0 text-warn" />
              <p className="text-[12px] leading-relaxed text-warn">
                Sign-in is not configured in this build. Set <code>VITE_SUPABASE_URL</code> and{' '}
                <code>VITE_SUPABASE_PUBLISHABLE_KEY</code>.
              </p>
            </div>
          )}

          <form
            className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4 shadow-card sm:p-5"
            onSubmit={(event) => {
              event.preventDefault();
              void handlePassword();
            }}
            noValidate
          >
            <TextInput
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              autoComplete="username"
              required
            />
            <TextInput
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              required
            />

            {error && (
              <p role="alert" className="text-[12px] leading-relaxed text-danger">
                {error}
              </p>
            )}

            <Button
              type="submit"
              variant="primary"
              loading={busy === 'password'}
              disabled={busy !== null || !authConfigured}
            >
              Sign in
            </Button>

            <div className="flex items-center gap-3 text-[11px] text-text-faint">
              <span className="h-px flex-1 bg-border" />
              or
              <span className="h-px flex-1 bg-border" />
            </div>

            <Button
              type="button"
              onClick={() => void handleGoogle()}
              loading={busy === 'google'}
              disabled={busy !== null || !authConfigured}
            >
              Continue with Google
            </Button>
          </form>
        </div>
      </main>
    </div>
  );
}
