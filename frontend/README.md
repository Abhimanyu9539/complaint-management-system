# Resolvr — frontend

React 19 + Vite + TypeScript + Tailwind v4. Three areas: the **complaint
workbench** at `/`, the agent **chat** at `/chat`, and the **admin panel** at
`/admin`.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
npm run lint     # oxlint
```

## Routes

| Path | What it is |
| --- | --- |
| `/` | **The main page.** The complaint workbench: a queue organised by status, and — for the selected ticket — its real progress, a simulated draft, and simulated evidence. |
| `/chat` | Chat — the agent-facing assistant |
| `/ticket` | **Customer-facing.** Submit a complaint. Public, standalone. |
| `/admin` | Dashboard: health, KPIs, ingest queue, document counts, storage |
| `/admin/tickets` | The complaint queue as a searchable, paged table; escalate to a department or resolve |
| `/admin/ingestion` | Trigger ingestion runs; browse and retry the ingest history |
| `/admin/activity` | Agent graph executions, routing confidence, latency |
| `/admin/stats` | Throughput, processing times, corpus distribution, escalation rate |

`/` and `/admin/tickets` do the same two actions (escalate, resolve) for
different jobs: the workbench triages one ticket at a time — a queue rail plus
`J`/`K` navigation — while `/admin/tickets` searches, filters and paginates
past the workbench's 100-ticket ceiling. Both share one implementation of the
action logic (`hooks/useTicketActions.ts`) and one mirror of the backend's
state machine (`lib/tickets/transitions.ts`) so they cannot drift.

The admin panel, chat and `/ticket` are each `React.lazy`-loaded as their own
chunk; the workbench at `/` is not, since it is the landing page.

`/ticket` deliberately does **not** mount `ChatProvider`. That provider fires
`listSessions()` on mount, and a customer arriving to complain must not pay for
an agent's chat history. The workbench doesn't mount it either, for the same
reason. The provider now lives inside `/chat` only.

Filters and pagination on `/admin/tickets`, `/admin/ingestion` and
`/admin/activity` live in the query string, so a filtered view is shareable and
the back button steps through filter states. The workbench's status filter,
search and selected ticket (`?ticket=`) follow the same convention.

## Environment

`.env.local`:

| Variable | Default | Effect |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend origin. The admin panel always calls it — there is no mock fallback. |
| `VITE_CHAT_USE_MOCK` | `true` | Chat's own switch, independent of the admin panel. `false` requires a running chat backend, which does not exist yet (`/api/v1/chat`, `/sessions` are 404 today). |
| `VITE_ADMIN_POLL_MS` | `20000` | Admin base poll cadence. Panels multiply it — health 3×, Qdrant reads 2×. Values under 2000 are ignored. |

### The admin panel is real-only

`lib/admin/transport.ts` has no mock path — every `/admin` panel reads live
Supabase and Qdrant state, and a request failure surfaces as a connection
error rather than substituting fake data. Two surfaces have no backend yet
(the agent activity log and the API-usage counter — the RAG graph and a
request-log middleware, respectively) and render an honest empty state
instead of a "Simulated" badge over fabricated rows.

See `backend/docs/admin-api.md` for which endpoints exist and what those two
must eventually return.

Chat is the one area that still has a mock, because it has no backend at all —
see `VITE_CHAT_USE_MOCK` above.

### `/ticket` is never mocked

`lib/tickets/transport.ts` has no mock path at all, unlike `lib/admin`. A
customer whose complaint was quietly simulated has lost it. With no
`VITE_API_BASE_URL` set, the form shows a banner saying it is not connected and
the submit fails with a message, rather than pretending to succeed.

`/admin/tickets` and the workbench at `/` both read the same real rows for the
same reason: a simulated queue in front of a real one would hide genuine
complaints behind a badge nobody investigates.

**The ticket routes need migration `0017_tickets_web_intake.sql`** applied to
Supabase. Until then every ticket endpoint returns 503 and the server log names
the missing column — which means the workbench, now the landing page, opens to
an error state until the migration is applied.

### The workbench's Draft and Evidence panes are simulated

There is no classifier, retriever or drafter — `backend/src/cms/rag/` holds only
the query-analysis node, no retriever exists yet, and `drafts`/`dept_responses`
have no writer. Rather than an empty state, those two panes render a deterministic,
per-ticket fixture (`lib/tickets/simulated.ts`) behind a **Simulated** banner,
so the intended shape of the finished product is visible today.

Three rules keep that honest:

- **"Send to customer" is permanently disabled.** There is no send endpoint —
  a simulated draft is structurally incapable of reaching a customer.
- **Escalate and Resolve are real** (the same `useTicketActions` the rest of
  the app uses) and render outside the simulated banner's border, so a real
  action is never visually confused with a fake one.
- **Department names always come from the live `/admin/departments` list.**
  The fixture only ever picks an id from that list; it never invents a name.

When the drafting pipeline lands (`lld.md` §6.3, `0013_drafts.sql`), `DraftPane`
and `EvidencePane` keep their markup — only the import changes, from
`lib/tickets/simulated` to a transport call.

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
