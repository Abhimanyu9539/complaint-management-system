/**
 * The Supabase client, used for sign-in only. Every data read goes through the
 * API, which checks the access token this client holds.
 *
 * Null when the two env values are missing, so the public complaint form still
 * loads in a build without sign-in configured.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;

export const authConfigured = Boolean(url && publishableKey);

// PKCE: the Google redirect returns a one-time code, not tokens in the URL.
export const supabase: SupabaseClient | null = authConfigured
  ? createClient(url!, publishableKey!, { auth: { flowType: 'pkce' } })
  : null;
