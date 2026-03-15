# Seed corpus

Synthetic data for the walking-skeleton ingest (build.md §0.8 D7, steps.md Step 4). Not real
customer data — every name, order number, and product is fabricated for structure/variety,
not privacy compliance testing.

The business modelled here is an **Indian D2C e-commerce brand**: own-brand appliances
(X200, AV-450, ProBlend 300, SmartHub Pro) sold on our own website and app, delivered by
courier partners, and serviced by an authorized service network. All monetary values are in
₹ and the corpus assumes Indian payment methods (UPI, cards, netbanking, wallets, EMI, COD),
GST invoicing, reverse pickup, and the statutory obligations that apply to Indian e-commerce
(Consumer Protection Act 2019, E-Commerce Rules 2020, DPDP Act 2023, Legal Metrology).

- **`cases.json`** — 20 resolved complaint cases across the 12 departments (build.md §0.4 `case` doc_type: **not chunked**, one JSON object → one Qdrant point). Mirrors the `kb_cases` shape from lld.md §3.2: `complaint_text` + optional `dept_guidance` (Path B only) + `resolution_text`.
- **`policies/*.md`** — 34 policy documents (build.md §0.4 `policy` doc_type: **header-aware chunked**, ~800 tokens/chunk). Section headers use `## N. Title` and clause references like `§2.3` — the same ref format the case resolutions cite (e.g. "per warranty §2.3"), so retrieval can be checked for realistic citations.

54 rows total, upserted on `source_ref` (`C-1001` for cases, the filename for policies).

## `cases.json` schema

```jsonc
{
  "id": "C-1001",                 // matches lld.md ticket-adjacent numbering, not a DB id
  "department": "warranty",       // one of the 12 taxonomy slugs (build.md D3)
  "category": "faulty_product",   // free-text sub-category
  "resolution_path": "direct",    // "direct" (Path A) | "escalated" (Path B)
  "complaint_text": "...",
  "dept_guidance": null,          // populated only when resolution_path = "escalated"
  "resolution_text": "..."
}
```

`seed.py` concatenates `complaint_text` + `dept_guidance` (if present) + `resolution_text` with section labels into the single chunk text per build.md §0.4, and sets Qdrant payload `department`/`category` accordingly. Every ₹ amount in `cases.json` is consistent with the policy thresholds it cites — see the ledger below.

## Policy frontmatter

```yaml
---
department: warranty        # OMIT ENTIRELY for a company-wide policy — see below
title: Product Warranty Policy
ref_prefix: warranty        # the §-citation namespace; unique per document
version: 1.0
effective_date: 2026-07-30
---
```

Parsed by `parse_frontmatter()` in `ingestion/extract/policy_extractor.py` — a hand-rolled
splitter, not pyyaml. Two consequences:

- **No quotes.** `version: "1.0"` stores the literal `"1.0"`, quotes included.
- **Omit a key you don't have; never leave it blank.** A key present with an empty value
  yields `""`, which is a FK violation on `department_id` and a cast error on the
  `effective_date` DATE column. `seed_policy()` maps empty to NULL defensively, but the
  files should not rely on it.

`department`, `title`, `version` and `effective_date` become `policies` columns.
`ref_prefix` is not yet read by any code — it documents the citation namespace the case
resolutions already use.

## Coverage

**18 department-scoped policies over the 12 departments.** `billing`, `sales` and `shipping`
each own more than one — see "Multi-policy department boundaries" below for how they divide.

| Department | Policy file(s) |
| --- | --- |
| `warranty` | `warranty-policy.md` |
| `billing` | `billing-refunds-policy.md`, `payment-failures-policy.md`, `stored-value-policy.md` |
| `shipping` | `shipping-delivery-policy.md`, `delivery-exceptions-policy.md` |
| `product_safety` | `product-safety-policy.md` |
| `returns` | `returns-policy.md`, `reverse-logistics-policy.md` |
| `tech_support` | `tech-support-policy.md` |
| `qa` | `quality-assurance-policy.md` |
| `legal` | `legal-escalation-policy.md` |
| `sales` | `sales-pricing-policy.md`, `order-lifecycle-policy.md`, `catalog-accuracy-policy.md` |
| `manufacturing` | `manufacturing-quality-policy.md` |
| `retention` | `retention-goodwill-policy.md` |
| `spare_parts` | `spare-parts-policy.md` |

**16 company-wide policies,** `department_id IS NULL` — the cross-cutting decision rules
that no single department owns:

| `ref_prefix` | Policy file | Answers |
| --- | --- | --- |
| `intake` | `complaint-intake-policy.md` | What we accept, what we capture, which department owns it |
| `severity` | `severity-priority-policy.md` | The four severity levels and who sets them |
| `sla` | `response-sla-policy.md` | How fast we answer and finish, and what a breach obliges |
| `escalation` | `escalation-policy.md` | Direct vs. escalated — the `resolution_path` decision |
| `authority` | `agent-authority-policy.md` | What may be done without asking (a matrix of cross-references) |
| `comms` | `customer-communication-policy.md` | What we send, and what never leaves the company |
| `privacy` | `data-privacy-policy.md` | PII limits, DPDP rights, retention schedule, redaction before the KB |
| `kb` | `knowledge-governance-policy.md` | Policy vs. precedent, conflict precedence, lifecycle |
| `ai` | `ai-drafting-policy.md` | Grounding, no-match behaviour, human review, accountability |
| `fraud` | `fraud-abuse-policy.md` | Repeat-claim review, and what a review may never withhold |
| `partner` | `partner-channel-policy.md` | Wholesale claims, batch remedies, marketplace-channel complaints |
| `incident` | `incident-continuity-policy.md` | One cause, many complaints — cohort handling |
| `vulnerable` | `vulnerable-customer-policy.md` | Adjustments, representation, distress handling |
| `reviews` | `reviews-moderation-policy.md` | Review/Q&A moderation, and reviews as a defect or safety signal |
| `account` | `account-security-policy.md` | Account compromise, verification, unauthorised orders |
| `grievance` | `grievance-redressal-policy.md` | The statutory floor: grievance officer, acknowledgement, redressal |

## Multi-policy department boundaries

Three departments own more than one policy. Each pair/trio has an explicit, non-overlapping
scope — this is what keeps the corpus from restating itself under two filenames:

- **billing** — `billing-refunds` owns *whether we refund a charge already settled, and who
  approves it*. `payment-failures` owns *money that moved, or tried to, before an order
  existed* — debited-no-order, stuck payments, refund routes per instrument. `stored-value`
  owns *money we hold* — wallet, gift cards, coupons, loyalty points.
- **shipping** — `shipping-delivery` owns timing, loss, transit damage, expedited service,
  international, pincode serviceability. `delivery-exceptions` owns fulfilment **accuracy**
  (wrong/missing/partial/tampered) and **access** failures (failed delivery, RTO, OTP
  disputes).
- **sales** — `sales-pricing` owns price, MRP and coupon eligibility. `order-lifecycle` owns
  the order's states (confirmation, cancellation, oversell, COD limits). `catalog-accuracy`
  owns what the listing promised beyond price (description, images, specs, disclosures).
- **returns / sales boundary** — `returns` owns eligibility, condition and refund method;
  `reverse-logistics` owns pickup execution and exactly when the refund is released.

## Retrieval note: NULL department is not a gap

16 of the 34 policies have `department_id IS NULL`, so their Qdrant payload carries
`metadata.department = null`. **A retriever that filters with a strict `must` on
`metadata.department` will silently return zero company-wide policies.** It must match

```
metadata.department == <dept>  OR  metadata.department IS NULL
```

This failure is invisible from the outside: retrieval still returns plausible,
correctly-scoped department clauses, and simply never surfaces the SLA, authority,
escalation, privacy, grievance or AI-governance rules. Every draft would then be reasoning
about remedies with no knowledge of what the agent is allowed to approve, or of the
statutory floor underneath everything else.

## One definition per number

34 documents restating each other's thresholds would make the whole corpus unsafe to cite.
The rule: **every number is defined in exactly one clause; every other mention is a
cross-reference to it.** `agent-authority-policy.md` is the clearest case — it is a matrix
of pointers and introduces no values of its own.

**Values we set:**

| Value | Defined in |
| --- | --- |
| 12-month warranty; 24 months on CarePlan+ | warranty §1, §4.1 |
| ₹4,000 part-cost replace-don't-repair default | warranty §2.3 |
| ₹12,000 no-inspection claim ceiling | warranty §6 |
| Service ladder and on-site visit TAT; pincode fallback | warranty §7, §8 |
| Refund authority ₹8,000; above needs sign-off | billing §1 |
| Card refunds 5–7 working days | billing §4 |
| 5–7 / 1–2 day delivery windows; +2 days = late | shipping §1 |
| ₹12,000 transit-damage write-off threshold | shipping §3.1 |
| 30-day return window; +10 day courtesy grace | returns §1, §3 |
| 3 reports / batch / 30 days → safety investigation | product_safety §2 |
| Safety reports never >1 business day in review | product_safety §1 |
| Repeat-contact rule: 3rd contact on one issue | tech_support §3 |
| Legacy software support: 24 months post-discontinuation | tech_support §5 |
| Non-safety quality pattern: 5 reports / SKU / 60 days | qa §1 |
| Price-match window: 14 days · quote validity: 30 days | sales §4, §5 |
| Goodwill ladder: agent ≤₹4,000, lead ≤₹15,000, admin above | retention §2 |
| Save-offer tiers (≥6 months, ≥12 months) | retention §5 |
| Parts availability: 5 years post-discontinuation | spare_parts §3 |
| Classifier confidence floor: 0.60 (matches `settings.py`) | intake §7 |
| First response 1h/4h/1d/2d; resolution same-day/2d/5d/10d | sla §2, §3 |
| Awaiting-customer: 2 chases, close at 10 days | sla §5 |
| Department referral answered in 2 business days | sla §6 |
| Abuse review: 3+ discretionary claims / 12 months | fraud §2 |
| Partner claim window 10 business days; disruption credit ≤5% | partner §2, §4 |
| Retention: tickets 24 months, attachments 12 months | privacy §5 |
| Post-incident review within 10 business days | incident §7 |
| COD ceiling ₹20,000; automatic oversell credit ₹500 | orders §4, §6 |
| Refund route and TAT per payment instrument | payments §4 |
| Manual reversal: admin-only | payments §6 |
| Failed delivery attempts before RTO: 3 | delivery §5 |
| Reverse-pickup attempts (2), then self-ship; reimbursement cap ₹500 | reverse §2, §3 |
| Refund release: pickup scan below ₹5,000, else warehouse QC | reverse §5 |
| Listing correction turnaround: 1 business day | catalog §5 |
| Reported-review moderation turnaround: 2 business days | reviews §7 |
| Promotional-credit expiry 12 months; gift card 3 years; points 24 months | stored_value §2, §3, §6 |

**Statutory, not ours to set** — cited as external and re-verified at each review (kb §5):

| Obligation | Cited in |
| --- | --- |
| Grievance officer; 48-hour acknowledgement; one-month redressal | grievance §1, §2 |
| Consumer Commission tiers and their effect on handling | legal §7, grievance §6 |
| MRP, net quantity, country of origin, consumer-care disclosure; never above MRP | sales §1, catalog §4 |
| DPDP data-principal rights; breach notification | privacy §4, §8 |
| No storage of card credentials; e-mandate pre-debit notification | privacy §2, payments §7 |
| Prescribed failed-transaction auto-reversal TAT and per-day compensation | payments §5 |
| GST tax invoice and credit note on refund | payments §8 |
| BIS marking; producer take-back for e-waste | product_safety §6 |

Two choices worth knowing before editing:

- **Goodwill caps at ₹4,000 for an agent, below the ₹8,000 refund authority.** A refund
  reverses a documented charge; goodwill is discretionary spend. ₹4,000 keeps every gesture
  in `cases.json` inside normal agent authority.
- **`lead` is a policy role, not a database role.** `profiles.role` is `agent | admin`, while
  billing §1 already refers to a lead sign-off. `authority §1` states the gap: a lead
  approval is recorded as an admin sign-off note on the ticket.

## Do not add a README to `policies/`

`find_seed_policies()` globs `*.md` in that directory, so any markdown file dropped there
is ingested as a policy. Corpus documentation belongs in this file, one level up.
