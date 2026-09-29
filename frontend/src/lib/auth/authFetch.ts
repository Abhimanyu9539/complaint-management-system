/**
 * `fetch` with the signed-in agent's access token attached.
 *
 * A 401 means the API no longer accepts the session, so this signs out and the
 * auth provider sends the user back to the login page. The response is still
 * returned, so callers handle the failure the way they handle any other.
 */

import { supabase } from './supabase';

export async function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (supabase) {
    // `getSession` refreshes an expired access token before returning it.
    const { data } = await supabase.auth.getSession();
    if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`);
  }

  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 && supabase) {
    console.warn(`auth: ${input} returned 401; signing out`);
    await supabase.auth.signOut({ scope: 'local' });
  }
  return response;
}
