import { createMockTransport } from './mockTransport';
import { createRealTransport } from './realTransport';
import type { ChatTransport } from './types';

/**
 * Chat switches on its own flag, independent of the admin panel's
 * `VITE_API_BASE_URL`. The real transport now has a backend — `POST
 * /api/v1/chat` runs the RAG graph — but it also needs a seeded corpus behind
 * it, so UI work still wants the mock. Defaults to mocked when the flag is
 * unset, which keeps a fresh checkout working with no backend at all.
 */
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const useMock = import.meta.env.VITE_CHAT_USE_MOCK !== 'false';

export const transport: ChatTransport =
  useMock || !apiBaseUrl ? createMockTransport() : createRealTransport(apiBaseUrl);
