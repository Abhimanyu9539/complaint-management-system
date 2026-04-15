/**
 * Deterministic fixtures for the workbench's Draft and Evidence panes.
 *
 * The backend has no classifier, no retriever and no drafter yet — `rag/` holds
 * only the query-analysis node and `guardrails/` is an empty package. These panes
 * render a labelled simulation instead of an empty state so the intended shape
 * of the finished product is visible. Three containment rules make that safe:
 *
 *   1. Deterministic in `ticket.id` — the queue polls every 20s; a random
 *      draft would reshuffle itself out from under the operator mid-read.
 *   2. Templated from the ticket's own fields — a fixture picked wholesale
 *      would show a vacuum-cleaner reply on a billing complaint.
 *   3. Department names are never invented here — callers resolve the ids
 *      this module returns against the live `/admin/departments` list. The
 *      prototype's own hardcoded department names had already drifted from
 *      the real seed data, which is exactly the failure mode this avoids.
 *
 * When the drafting pipeline lands (lld.md §6.3, `0013_drafts.sql`), the panes
 * that call these keep their markup; only the import changes, from here to a
 * transport call reading `drafts.draft_text` / `.retrieved_cases` / `.policy_refs`.
 */

import type { Ticket } from './types';

function hashString(value: string): number {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return hash >>> 0;
}

function pick<T>(seed: number, pool: readonly T[]): T {
  return pool[seed % pool.length];
}

export interface SimulatedCitedCase {
  id: string;
  similarity: number;
  snippet: string;
  resolution: string;
}

export interface SimulatedDraft {
  text: string;
  noMatch: boolean;
}

export interface SimulatedEvidence {
  predictedDeptId: string | null;
  confidence: number | null;
  alternativeDeptId: string | null;
  cases: SimulatedCitedCase[];
  policyRef: string;
  policyText: string;
  noMatch: boolean;
}

const POLICY_POOL = [
  {
    ref: 'warranty §2.3',
    text: 'Hardware faults within the warranty period qualify for a free repair or replacement.',
  },
  {
    ref: 'billing §1.3',
    text: 'Duplicate authorisations are voided same-day once confirmed in the payment gateway.',
  },
  {
    ref: 'shipping §3.4',
    text: 'Delays over 5 days past the promised date qualify for a goodwill credit without approval.',
  },
  {
    ref: 'returns §7.0',
    text: 'Suspected tampering or contamination must be escalated before any replacement is promised.',
  },
] as const;

const CASE_SNIPPET_POOL = [
  'Customer reported the same fault within the first month of ownership…',
  'Similar complaint resolved by confirming the batch and dispatching a replacement…',
  'Matching billing discrepancy traced to a payment-gateway retry…',
  'Comparable delivery delay resolved with a goodwill credit and re-dispatch…',
] as const;

const CASE_RESOLUTION_POOL = [
  'Replacement issued under warranty; customer confirmed receipt.',
  'Duplicate charge voided; reversal confirmed within 4 business days.',
  'Re-dispatched via priority courier; 10% goodwill credit applied.',
  'Escalated to the department, which corrected the record directly.',
] as const;

function simulatedCases(seed: number, noMatch: boolean): SimulatedCitedCase[] {
  if (noMatch) return [];
  const count = 1 + (seed % 2); // 1 or 2 cited cases
  return Array.from({ length: count }, (_, index) => {
    const s = seed + index * 97;
    return {
      id: `C-${1000 + (s % 900)}`,
      similarity: 0.62 + (s % 34) / 100,
      snippet: pick(s, CASE_SNIPPET_POOL),
      resolution: pick(s + 1, CASE_RESOLUTION_POOL),
    };
  });
}

/** A deterministic, ticket-shaped draft reply. Never sendable — see `DraftPane`. */
export function simulatedDraft(ticket: Ticket): SimulatedDraft {
  const seed = hashString(ticket.id);
  const noMatch = seed % 5 === 0;
  const name = ticket.customerEmail ? ticket.customerEmail.split('@')[0] : 'there';

  if (noMatch) {
    return {
      noMatch: true,
      text:
        `Hi ${name},\n\n` +
        `Thank you for letting us know about "${ticket.subject}". So we can look into this ` +
        `properly, could you share a little more detail or a photo if you have one?\n\n` +
        `We'll come back to you with next steps as a priority.\n\nKind regards,\nCustomer Care`,
    };
  }

  const policy = pick(seed, POLICY_POOL);
  const caseId = `C-${1000 + (seed % 900)}`;
  return {
    noMatch: false,
    text:
      `Hi ${name},\n\n` +
      `Thank you for reaching out about "${ticket.subject}". Based on a similar case (${caseId}) ` +
      `and our policy (${policy.ref}), here is what we can do:\n\n` +
      `${policy.text}\n\n` +
      `We'll follow up shortly to confirm next steps.\n\nKind regards,\nCustomer Care`,
  };
}

/** Deterministic, ticket-shaped evidence — department ids only; names resolve via the live list. */
export function simulatedEvidence(
  ticket: Ticket,
  departmentIds: readonly string[],
): SimulatedEvidence {
  const seed = hashString(ticket.id);
  const noMatch = seed % 5 === 0;
  const policy = pick(seed, POLICY_POOL);
  const cases = simulatedCases(seed, noMatch);

  if (departmentIds.length === 0) {
    return {
      predictedDeptId: null,
      confidence: null,
      alternativeDeptId: null,
      cases,
      policyRef: policy.ref,
      policyText: policy.text,
      noMatch,
    };
  }

  const predicted = pick(seed, departmentIds);
  const remaining = departmentIds.filter((id) => id !== predicted);
  const alternative = remaining.length > 0 ? pick(seed + 13, remaining) : null;

  return {
    predictedDeptId: predicted,
    confidence: 0.55 + (seed % 40) / 100,
    alternativeDeptId: alternative,
    cases,
    policyRef: policy.ref,
    policyText: policy.text,
    noMatch,
  };
}
