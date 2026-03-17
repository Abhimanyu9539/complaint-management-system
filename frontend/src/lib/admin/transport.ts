import { createRealAdminTransport } from './realTransport';
import type { AdminTransport } from './types';

/**
 * The admin panel is real-only — no mock fallback. Unlike chat, which has a
 * genuine offline demo mode, every admin surface reads live operational state
 * (job counts, ticket queues, Qdrant point counts): a simulated dashboard is
 * actively misleading for the one audience this panel serves.
 *
 * Defaults to uvicorn's own default port so a missing env var still points
 * somewhere plausible and fails as a visible connection error rather than
 * silently substituting fake data.
 */
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

export const adminTransport: AdminTransport = createRealAdminTransport(apiBaseUrl);
