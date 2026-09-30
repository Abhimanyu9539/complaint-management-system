import { CircleAlert, Inbox, MessageSquareQuote, Send, TriangleAlert } from 'lucide-react';
import { useRef, useState } from 'react';
import { Link, Navigate, useLocation, type Location } from 'react-router';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { Button } from '@/components/ui/Button';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { TextInput } from '@/components/ui/TextInput';
import { authConfigured } from '@/lib/auth/supabase';
import { useAuth } from '@/state/AuthProvider';
import { BrandMark } from '@/components/layout/BrandMark';

const FEATURES = [
  {
    icon: Inbox,
    title: 'One queue',
    text: 'New complaints arrive sorted by category and severity.',
  },
  {
    icon: MessageSquareQuote,
    title: 'Answers with sources',
    text: 'Ask the assistant and check the policy it cites.',
  },
  {
    icon: Send,
    title: 'Escalate in one step',
    text: 'Send a question to the right department and track the reply.',
  },
];

type FieldErrors = { email?: string; password?: string };

/** A refused Google sign-in comes back with the reason in the query string or the hash. */
function readRedirectError(location: Location): string | null {
  const params = new URLSearchParams(location.search);
  const hash = new URLSearchParams(location.hash.slice(1));
  const code = params.get('error_code') ?? hash.get('error_code');
  if (code === 'signup_disabled') {
    return 'This Google account is not registered. Ask an admin to add you.';
  }
  return params.get('error_description') ?? hash.get('error_description');
}

/**
 * Agent sign-in: email and password, or Google. Accounts are created by an admin
 * in Supabase; public signup is off, so an unknown Google account is refused and
 * comes back here with Supabase's error.
 */
export function LoginPage() {
  const { status, signInWithPassword, signInWithGoogle } = useAuth();
  const location = useLocation();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState<'password' | 'google' | null>(null);
  const [error, setError] = useState<string | null>(() => readRedirectError(location));

  if (status === 'loading') {
    return <div className="h-full w-full bg-bg" aria-busy="true" aria-label="Loading" />;
  }
  if (status !== 'signed_out') {
    const from = (location.state as { from?: Location } | null)?.from;
    return <Navigate to={from ? `${from.pathname}${from.search}` : '/'} replace />;
  }

  async function handlePassword() {
    const found: FieldErrors = {};
    if (!email.trim()) found.email = 'Enter your email address.';
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      found.email = 'Enter a valid email address.';
    }
    if (!password) found.password = 'Enter your password.';

    setFieldErrors(found);
    setError(null);
    // Focus the first field that needs fixing, so its error is read out.
    if (found.email || found.password) {
      (found.email ? emailRef : passwordRef).current?.focus();
      return;
    }

    setBusy('password');
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

  const disabled = busy !== null || !authConfigured;

  return (
    <div className="flex h-full min-h-0 bg-bg">
      <BrandPanel />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-13 shrink-0 items-center gap-2 px-4">
          <BrandMark className="lg:hidden" />
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </header>

        <main className="flex min-h-0 flex-1 overflow-y-auto">
          <div className="m-auto flex w-full max-w-sm flex-col gap-6 px-4 py-8 sm:px-6">
            <div>
              <h1 className="font-display text-[26px] leading-tight font-medium text-text">Sign in</h1>
              <p className="mt-1.5 text-[13px] leading-relaxed text-text-muted">
                Use your work account to open the workbench.
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

            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-soft px-3.5 py-3"
              >
                <CircleAlert size={16} strokeWidth={1.75} className="mt-px shrink-0 text-danger" />
                <p className="text-[12px] leading-relaxed text-danger">{error}</p>
              </div>
            )}

            <Button
              onClick={() => void handleGoogle()}
              loading={busy === 'google'}
              disabled={disabled}
              icon={<GoogleMark />}
            >
              Continue with Google
            </Button>

            <div className="flex items-center gap-3 text-[12px] text-text-muted">
              <span className="h-px flex-1 bg-border" />
              or use email
              <span className="h-px flex-1 bg-border" />
            </div>

            <form
              className="flex flex-col gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                void handlePassword();
              }}
              noValidate
            >
              <TextInput
                ref={emailRef}
                label="Email"
                type="email"
                value={email}
                onChange={(value) => {
                  setEmail(value);
                  setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }}
                error={fieldErrors.email}
                placeholder="you@company.com"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
              />
              <PasswordInput
                ref={passwordRef}
                label="Password"
                value={password}
                onChange={(value) => {
                  setPassword(value);
                  setFieldErrors((prev) => ({ ...prev, password: undefined }));
                }}
                error={fieldErrors.password}
                autoComplete="current-password"
                required
              />

              <Button
                type="submit"
                variant="primary"
                loading={busy === 'password'}
                disabled={disabled}
                className="mt-1"
              >
                {busy === 'password' ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>

            <div className="flex flex-col gap-1 border-t border-border pt-5 text-[12px] leading-relaxed text-text-muted">
              <p>No account? An admin creates agent accounts.</p>
              <p>
                Customer with a complaint?{' '}
                <Link
                  to="/ticket"
                  className="font-medium text-accent underline-offset-2 hover:underline"
                >
                  Send it here
                </Link>
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

/** Desktop only: what the workbench is for, beside the form. */
function BrandPanel() {
  return (
    <aside className="hidden w-[44%] max-w-xl shrink-0 flex-col justify-between border-r border-border bg-surface-2 bg-[radial-gradient(circle_at_0%_0%,var(--accent-soft),transparent_60%)] p-10 lg:flex">
      <BrandMark />

      <div>
        <p className="max-w-sm font-display text-[30px] leading-tight font-medium text-text">
          Every complaint, triaged and answered.
        </p>
        <ul className="mt-8 flex flex-col gap-5">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <li key={title} className="flex gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
                <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-text">{title}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-text-muted">{text}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-[12px] text-text-muted">For support agents and admins.</p>
    </aside>
  );
}

/** Google's "G", which their sign-in branding asks for on the button. */
function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" width="16" height="16" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.6 20.1H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.7-.4-3.9z"
      />
      <path
        fill="#FF3D00"
        d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2c-2 1.5-4.5 2.4-7.2 2.4-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.7-.4-3.9z"
      />
    </svg>
  );
}
