import { createMockTransport } from './mockTransport';
import { createRealTransport } from './realTransport';
import type { ChatTransport } from './types';

/**
 * Chat switches on its own flag, independent of the admin panel's
 * `VITE_API_BASE_URL` — the backend does not serve `/api/v1/chat` or
 * `/sessions` yet, so admin going live must not silently point chat at routes
 * that 404. Defaults to mocked until a chat backend exists.
 */
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const useMock = import.meta.env.VITE_CHAT_USE_MOCK !== 'false';

export const transport: ChatTransport =
  useMock || !apiBaseUrl ? createMockTransport() : createRealTransport(apiBaseUrl);
