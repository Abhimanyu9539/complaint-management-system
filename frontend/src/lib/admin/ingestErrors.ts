/**
 * Turns a raw pipeline exception string into something an operator can act on.
 *
 * The ingestion pipeline persists failures as `f"{type(exc).__name__}: {exc}"`,
 * truncated to 2000 characters, so the exception class name is always the first
 * token and is reliably parseable. That is what makes this mapping possible
 * without guessing from prose.
 *
 * Humanising must never *hide*: every call site keeps the raw string available
 * in a collapsed disclosure. The goal is to put the likely fix on screen, not
 * to decide on the reader's behalf that the original is unimportant.
 */

export interface HumanisedError {
  /** What went wrong, in one sentence. */
  cause: string;
  /** What to do about it. */
  action: string;
}

interface Rule {
  /** Matched against the whole raw string, case-insensitively. */
  test: RegExp;
  cause: string;
  action: string;
}

const RULES: Rule[] = [
  {
    test: /^LookupError|disappeared before ingest/i,
    cause: 'The document row disappeared before the ingest finished.',
    action: 'It was most likely deleted mid-run. Safe to ignore.',
  },
  {
    test: /AuthenticationError|PermissionDeniedError|Incorrect API key/i,
    cause: 'The embedding provider rejected the credentials.',
    action: 'Check OPENAI_API_KEY in the backend environment, then re-run.',
  },
  {
    test: /RateLimitError|rate limit/i,
    cause: 'The embedding provider throttled the request.',
    action:
      'Re-run when the limit resets — the content-hash check means unchanged documents cost nothing.',
  },
  {
    test: /(UnexpectedResponse|doesn.t exist).*(404|Collection)/is,
    cause: 'The Qdrant collection does not exist.',
    action: 'Run `uv run cms-create-collections`, then re-run the ingest.',
  },
  {
    test: /ResponseHandlingException|ReadTimeout|timed out/i,
    cause: 'Qdrant did not respond within the timeout.',
    action: 'The collection may be cold or the URL wrong. Check /health/deps first.',
  },
  {
    test: /row-level security|APIError|PostgrestError|42501/i,
    cause: 'Supabase rejected the write.',
    action: 'Usually an RLS policy or a schema mismatch — check the migration state.',
  },
  {
    test: /ConnectionError|ConnectTimeout|Name or service not known/i,
    cause: 'A dependency was unreachable from the backend.',
    action: 'Check that Supabase and Qdrant are up and the URLs are right.',
  },
];

export function humaniseIngestError(raw: string | null): HumanisedError | null {
  if (!raw?.trim()) return null;

  for (const rule of RULES) {
    if (rule.test.test(raw)) {
      return { cause: rule.cause, action: rule.action };
    }
  }

  // Unrecognised: show the first line verbatim rather than inventing a
  // paraphrase. A wrong summary is worse than an unpolished true one.
  const firstLine = raw.split('\n')[0].trim();
  return {
    cause: firstLine.length > 200 ? `${firstLine.slice(0, 200)}…` : firstLine,
    action: 'Retry once, then check the backend log for the full traceback.',
  };
}
