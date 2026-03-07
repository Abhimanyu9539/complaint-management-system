import type { Citation, SourceDocument } from './types';

/**
 * Stands in for the Supabase `documents` table. `url` is null throughout
 * because mock mode has no Storage bucket to sign against — the real transport
 * returns a signed URL here and the UI unlocks the "Open document" action.
 */
export const MOCK_DOCUMENTS: Record<string, SourceDocument> = {
  'pol-warranty-001': {
    id: 'pol-warranty-001',
    title: 'Small Appliance Warranty Policy v2',
    doc_type: 'policy',
    department: 'warranty',
    storage_path: 'policies/small-appliance-warranty-v2.md',
    url: null,
    status: 'indexed',
  },
  'case-4521': {
    id: 'case-4521',
    title: 'Resolved Case #4521 — ProBlend 300 ERR-22',
    doc_type: 'case',
    department: 'warranty',
    storage_path: 'cases/case-4521.md',
    url: null,
    status: 'indexed',
  },
  'pol-safety-002': {
    id: 'pol-safety-002',
    title: 'Product Safety Escalation Policy',
    doc_type: 'policy',
    department: 'product_safety',
    storage_path: 'policies/product-safety-escalation.md',
    url: null,
    status: 'indexed',
  },
  'pol-shipping-004': {
    id: 'pol-shipping-004',
    title: 'Shipping & Delivery Policy',
    doc_type: 'policy',
    department: 'shipping',
    storage_path: 'policies/shipping-delivery.md',
    url: null,
    status: 'indexed',
  },
  'pol-routing-000': {
    id: 'pol-routing-000',
    title: 'Department Routing Matrix',
    doc_type: 'policy',
    department: 'qa',
    storage_path: 'policies/department-routing-matrix.md',
    url: null,
    status: 'indexed',
  },
};

export interface MockAnswer {
  match: RegExp;
  answer: string;
  citations: Citation[];
}

export const MOCK_ANSWERS: MockAnswer[] = [
  {
    match: /err-?22|blender|motor|thermal/i,
    answer: `**ERR-22** on the ProBlend 300 indicates a **motor thermal cutoff fault** — the motor overheated and the unit shut itself down to prevent damage.

This is covered under warranty:

- Error codes **ERR-20 through ERR-29** are motor/thermal faults, covered for **24 months from purchase**.
- Ask the customer for the purchase date and serial number to confirm coverage.
- If within 24 months: issue a **replacement unit**, no repair attempt needed for this code range.
- If outside 24 months: offer the **20% loyalty discount** on a replacement as a goodwill gesture.

Let the customer know the replacement ships within 2 business days once the claim is confirmed.`,
    citations: [
      {
        doc_id: 'pol-warranty-001',
        chunk_id: 'pol-warranty-001#3',
        title: 'Small Appliance Warranty Policy v2 — §3.1 Motor faults',
        snippet:
          'Motor and thermal faults (error codes ERR-20 through ERR-29) are covered for 24 months from purchase. Confirmed cases in this range should be resolved with a direct replacement rather than a repair attempt...',
      },
      {
        doc_id: 'case-4521',
        chunk_id: 'case-4521#1',
        title: 'Resolved Case #4521 — ProBlend 300 ERR-22',
        snippet:
          'Customer reported ERR-22 after 8 months of use. Confirmed under warranty, replacement unit shipped, case closed with positive follow-up feedback.',
      },
    ],
  },
  {
    match: /smok|burn|fire|spark|hazard|smell/i,
    answer: `A smoking or burning smell from an appliance is a **safety issue**, not a standard warranty claim — handle this one carefully.

**Immediate steps for the customer:**
1. Unplug the unit immediately and do not use it again.
2. Do not attempt any repair or further troubleshooting.

**Your steps:**
- Escalate to the **Product Safety team** (not general warranty) using the safety-incident tag.
- Offer a **prepaid return shipping label** so the unit can be inspected.
- Issue an immediate replacement or refund — do not make the customer wait on the safety review for their remedy.

This matches the incident criteria in the safety escalation policy, so treat it as priority regardless of warranty status.`,
    citations: [
      {
        doc_id: 'pol-safety-002',
        chunk_id: 'pol-safety-002#1',
        title: 'Product Safety Escalation Policy — §1 Incident criteria',
        snippet:
          'Any report of smoke, burning odor, sparking, or visible heat damage must be routed to Product Safety regardless of warranty status. Do not instruct the customer to continue troubleshooting a unit exhibiting these symptoms...',
      },
    ],
  },
  {
    match: /refund|delay|late|shipping|delivery/i,
    answer: `For a **delayed delivery refund request**, here's the applicable policy:

- Orders delayed **more than 5 business days** past the quoted delivery window qualify for a **shipping fee refund** automatically.
- Orders delayed **more than 14 days** qualify for the customer to choose between a **full refund** or **expedited reshipment** at no cost.
- If the customer has already disputed the charge with their bank, do not process a refund — route to Billing to avoid a double-refund/chargeback conflict.

Check the order's tracking status first — if it shows "delivered" but the customer disputes receipt, that's a different flow (lost-package investigation), not a delay refund.`,
    citations: [
      {
        doc_id: 'pol-shipping-004',
        chunk_id: 'pol-shipping-004#2',
        title: 'Shipping & Delivery Policy — §2 Delay remedies',
        snippet:
          'Deliveries exceeding the quoted window by more than 5 business days qualify for automatic shipping fee refund. Exceeding 14 days escalates to full refund or free expedited reshipment, customer\'s choice...',
      },
    ],
  },
  {
    match: /escalat|route|department|which team/i,
    answer: `Complaint routing is based on the **12-department taxonomy**. Here's how to decide:

| Signal | Route to |
|---|---|
| Product malfunction, error codes | Tech Support |
| Billing dispute, duplicate charge | Billing |
| Late/lost package | Shipping |
| Smoke, fire, injury risk | Product Safety |
| Item doesn't match description | Returns |
| Manufacturing defect pattern (3+ reports) | Manufacturing |

If a complaint touches more than one department (e.g. a safety issue tied to a billing dispute), route to the **higher-priority** department first — Product Safety and Legal always take precedence over the others.

When confidence in the routing is low, it's safer to widen retrieval to the top 2 candidate departments than to guess.`,
    citations: [
      {
        doc_id: 'pol-routing-000',
        chunk_id: 'pol-routing-000#1',
        title: 'Department Routing Matrix — 12 departments',
        snippet:
          'The routing matrix maps complaint signals to one of twelve departments: warranty, billing, shipping, product_safety, returns, tech_support, qa, legal, sales, manufacturing, retention, spare_parts...',
      },
    ],
  },
];

export const MOCK_FALLBACK_ANSWER = `I couldn't find a specific policy or case that matches this question directly.

Rather than guess, here's what I'd suggest:
- Double-check the product name, error code, or department involved and try rephrasing.
- If this looks like a new issue type, it may be worth flagging for the knowledge base team to add coverage.

I'd rather tell you I don't have a grounded answer than make one up.`;

export const SUGGESTED_PROMPTS: string[] = [
  'My ProBlend 300 is showing ERR-22 and won\'t start — is this covered?',
  'Customer says their toaster started smoking, what do I do?',
  'A customer wants a refund because their order arrived 9 days late.',
  'How do I decide which department a complaint should be routed to?',
];
