/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Chat's own mock switch — see `lib/chat/transport.ts`. Admin has no mock. */
  readonly VITE_CHAT_USE_MOCK?: string;
  /**
   * Base poll cadence for the admin panel, in ms. Defaults to 20000. Individual
   * panels multiply it — health checks 3×, Qdrant reads 2× — so lowering this
   * speeds every panel up proportionally. Values under 2000 are ignored.
   */
  readonly VITE_ADMIN_POLL_MS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
