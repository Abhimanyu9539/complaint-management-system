import { createMockAdminTransport } from './mockTransport';
import { createRealAdminTransport } from './realTransport';
import type { AdminTransport } from './types';

/**
 * Mirrors `lib/chat/transport.ts` so both surfaces switch on the same two env
 * vars and there is one rule to remember: no `VITE_API_BASE_URL` means mock.
 *
 * Note that "not mocked" is weaker for admin than for chat. Even against a real
 * backend, six of the eleven transport methods have no route yet and keep
 * returning simulated data — `useMockAdmin` only says whether *any* live call
 * is attempted. Per-payload truth lives in `AdminResult.mocked`.
 */
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;

export const useMockAdmin = import.meta.env.VITE_USE_MOCK === 'true' || !apiBaseUrl;

export const adminTransport: AdminTransport = useMockAdmin
  ? createMockAdminTransport()
  : createRealAdminTransport(apiBaseUrl!);
