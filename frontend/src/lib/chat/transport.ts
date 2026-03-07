import { createMockTransport } from './mockTransport';
import { createRealTransport } from './realTransport';
import type { ChatTransport } from './types';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const useMock = import.meta.env.VITE_USE_MOCK === 'true' || !apiBaseUrl;

export const transport: ChatTransport = useMock
  ? createMockTransport()
  : createRealTransport(apiBaseUrl!);
