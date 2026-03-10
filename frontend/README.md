# Resolvr — frontend

React 19 + Vite + TypeScript + Tailwind v4. Two areas: the agent **chat** at `/`
and the **admin panel** at `/admin`.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
npm run lint     # oxlint
```

## Routes

| Path | What it is |
| --- | --- |
| `/` | Chat — the agent-facing assistant |
| `/ticket` | **Customer-facing.** Submit a complaint. Public, standalone. |
| `/admin` | Dashboard: health, KPIs, ingest queue, document counts, storage |
| `/admin/tickets` | The complaint queue; escalate to a department or resolve |
| `/admin/ingestion` | Trigger ingestion runs; browse and retry the ingest history |
| `/admin/activity` | Agent graph executions, routing confidence, latency |
| `/admin/stats` | Throughput, processing times, corpus distribution, escalation rate |

The admin panel and `/ticket` are each `React.lazy`-loaded as their own chunk, so
a chat user downloads neither the charts nor the form primitives.

`/ticket` deliberately does **not** mount `ChatProvider`. That provider fires
`listSessions()` on mount, and a customer arriving to complain must not pay for
an agent's chat history. The same rule keeps chat's providers inside `/`.

Filters and pagination on `/admin/tickets`, `/admin/ingestion` and
`/admin/activity` live in the query string, so a filtered view is shareable and
the back button steps through filter states.

## Environment

`.env.local`, or leave everything unset to run fully mocked:

| Variable | Default | Effect |
| --- | --- | --- |
| `VITE_API_BASE_URL` | *(unset)* | Backend origin. Unset ⇒ mock mode. |
| `VITE_USE_MOCK` | `false` | `true` forces mock mode even with a base URL set. |
| `VITE_ADMIN_POLL_MS` | `20000` | Admin base poll cadence. Panels multiply it — health 3×, Qdrant reads 2×. Values under 2000 are ignored. |

### Mock mode is not all-or-nothing on `/admin`

The chat transport is mock **or** real. The admin transport is genuinely mixed:
twelve endpoints read live Supabase and Qdrant state, while the ingestion
*trigger* and the agent activity log have no backend at all — the pipeline is
CLI-driven and the RAG graph has not been built.

So even against a real backend, parts of the admin panel are simulated. Every
payload carries a `mocked` flag and those parts render a **Simulated** badge
explaining why. That is deliberate: showing zeros instead would make a missing
subsystem indistinguishable from an idle one.

See `backend/docs/admin-api.md` for which endpoints are live and what the rest
must eventually return.

### `/ticket` is never mocked

`lib/tickets/transport.ts` has no mock path at all, unlike `lib/admin`. A
customer whose complaint was quietly simulated has lost it. With no
`VITE_API_BASE_URL` set, the form shows a banner saying it is not connected and
the submit fails with a message, rather than pretending to succeed.

`/admin/tickets` reads the same real rows for the same reason: a simulated queue
in front of a real one would hide genuine complaints behind a badge nobody
investigates.

**The ticket routes need migration `0017_tickets_web_intake.sql`** applied to
Supabase. Until then every ticket endpoint returns 503 and the server log names
the missing column.

## Deploying — SPA history fallback is required

`BrowserRouter` means the server must return `index.html` for any unmatched
path, or a hard refresh on `/admin/ingestion` 404s. `vite dev` and
`vite preview` do this already; a plain static host does not.

- **nginx:** `try_files $uri $uri/ /index.html;`
- **Netlify:** `/*  /index.html  200` in `_redirects`
- **Vercel / Cloudflare Pages / S3+CloudFront:** configure the SPA / 404-to-index rewrite

## Conventions

Worth knowing before adding to this codebase:

- **Design tokens only — never a hard-coded hex.** Colours come from CSS custom
  properties in `src/index.css` (`bg-surface`, `text-text-muted`, `bg-ok-soft`,
  `stroke-accent`, …). Six palettes × light/dark all work for free as a result.
- **Never build a Tailwind class by interpolation.** `` `bg-${tone}-soft` ``
  produces a class that was never compiled. `TONE_CLASSES` in `src/lib/status.ts`
  maps to complete literal strings for this reason.
- **Charts read colour through Tailwind utilities, not `getComputedStyle`.** A
  palette switch flips a `data-palette` attribute with no React re-render, so
  read values go stale. Note also that `fill="var(--accent)"` as a bare SVG
  presentation attribute renders black — use a class, or `style`.
- `import type` is mandatory (`verbatimModuleSyntax`), and TS enums are
  forbidden (`erasableSyntaxOnly`) — use union string literals.
- Named exports for components; `interface XProps` declared locally.
- Data fetching goes through `usePanelData` / `useAsyncData`, which handle
  polling, abort, backoff, tab-visibility and error retention. Don't hand-roll a
  `useEffect` fetch.
