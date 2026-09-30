import type { Session } from '@supabase/supabase-js';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { authFetch } from '@/lib/auth/authFetch';
import { supabase } from '@/lib/auth/supabase';

const apiBaseUrl =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

const NOT_CONFIGURED =
  'Sign-in is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.';

/** The signed-in agent as the API sees them (`GET /api/v1/me`). */
export interface Me {
  id: string;
  email: string;
  display_name: string | null;
  role: 'agent' | 'admin';
}

/**
 * `loading` until both the session and the profile are known. `error` is a
 * signed-in user the API will not serve: no agent profile, inactive, or the API
 * could not be reached.
 */
export type AuthStatus = 'loading' | 'signed_out' | 'ready' | 'error';

interface AuthContextValue {
  status: AuthStatus;
  me: Me | null;
  error: string | null;
  /** Resolves to a message the user can act on, or null on success. */
  signInWithPassword(email: string, password: string): Promise<string | null>;
  /** Leaves the page for Google; resolves only if the redirect could not start. */
  signInWithGoogle(): Promise<string | null>;
  signOut(): Promise<void>;
  /** Asks the API for the profile again, after an `error`. */
  retry(): void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // `undefined` until the stored session has been read.
  const [session, setSession] = useState<Session | null | undefined>(supabase ? undefined : null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (active) setSession(data.session);
    });
    // Only state is set here: Supabase warns against awaiting its own calls inside this callback.
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  const userId = session?.user.id ?? null;

  // Keyed on the user, not the session: a token refresh must not refetch the profile.
  useEffect(() => {
    setMe(null);
    setError(null);
    if (!userId) return;

    const controller = new AbortController();
    authFetch(`${apiBaseUrl}/api/v1/me`, { signal: controller.signal })
      .then(async (response) => {
        if (controller.signal.aborted) return;
        if (response.ok) {
          setMe((await response.json()) as Me);
        } else if (response.status === 403) {
          setError('Your account is not set up as an agent. Ask an admin to add you.');
        } else if (response.status !== 401) {
          // A 401 has already signed the user out (`authFetch`).
          setError(`Your sign-in could not be checked (${response.status}). Try again in a moment.`);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        console.warn('auth: could not load the profile', err);
        setError('Could not reach the API to check your sign-in.');
      });
    return () => controller.abort();
  }, [userId, attempt]);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    if (!supabase) return NOT_CONFIGURED;
    const { error: failure } = await supabase.auth.signInWithPassword({ email, password });
    if (!failure) return null;
    return failure.code === 'invalid_credentials' ? 'Incorrect email or password.' : failure.message;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!supabase) return NOT_CONFIGURED;
    const { error: failure } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/login` },
    });
    return failure ? failure.message : null;
  }, []);

  const signOut = useCallback(async () => {
    // `local`: this browser only. The default would end the agent's sessions everywhere.
    await supabase?.auth.signOut({ scope: 'local' });
  }, []);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  // A profile from the previous user counts as not loaded yet.
  const currentMe = me && me.id === userId ? me : null;
  let status: AuthStatus;
  if (session === undefined) status = 'loading';
  else if (session === null) status = 'signed_out';
  else if (currentMe) status = 'ready';
  else if (error) status = 'error';
  else status = 'loading';

  const value = useMemo<AuthContextValue>(
    () => ({ status, me: currentMe, error, signInWithPassword, signInWithGoogle, signOut, retry }),
    [status, currentMe, error, signInWithPassword, signInWithGoogle, signOut, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
