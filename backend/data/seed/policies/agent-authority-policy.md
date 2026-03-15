---
title: Agent Authority & Approval Matrix
ref_prefix: authority
version: 1.0
effective_date: 2026-07-30
---

# Agent Authority & Approval Matrix

This policy is company-wide and answers one question: what may I do without asking? It **defines no limits of its own** — every value below is set by the policy that owns it, and this document is the single place to read them together. Where this matrix and an owning policy ever disagree, the owning policy is right and this one is out of date.

## 1. Roles

**Agent** — handles the queue, holds standard authority.
**Lead** — approves above-agent remedies, owns disputed and repeatedly referred tickets (escalation §6).
**Admin** — approves above-lead remedies, account restrictions, and anything at partner, batch or systemic-incident scale.

A note on the current system: the user record supports support **agent** and **admin** only. Until a lead role exists in the system, a lead approval is recorded as an admin sign-off note on the ticket, naming who approved it. The three-tier structure below is the policy; the two-role record is the mechanism.

## 2. The Matrix

| Action | Agent | Lead | Admin | Limit defined in |
| --- | --- | --- | --- | --- |
| Refund of a documented charge | up to ₹8,000 | above ₹8,000 | above ₹8,000 | billing §1 |
| Goodwill credit or wallet credit | up to ₹4,000 | ₹4,001–₹15,000 | above ₹15,000 | retention §2 |
| Replacement without return — transit damage | under ₹12,000 value | at or above ₹12,000 | at or above ₹12,000 | shipping §3.1 |
| Replacement without return — safety symptom | any value | — | — | product_safety §4 |
| Repair-or-replace choice on a warranty defect | yes | — | — | warranty §2.3 |
| Warranty remedy without physical inspection | under ₹12,000 value | at or above ₹12,000 | at or above ₹12,000 | warranty §6 |
| On-site service visit authorisation | yes | — | — | warranty §7, §8 |
| RTO/failed-delivery redelivery waiver | yes | — | — | delivery §6 |
| Reverse-pickup self-ship reimbursement | up to ₹500 | above ₹500 | above ₹500 | reverse §3 |
| Oversell automatic inconvenience credit | yes (fixed amount) | — | — | orders §4 |
| Manual payment reversal outside standard reconciliation | no | no | yes | payments §6 |
| Coupon or wallet credit reissue after cancellation/refund | yes | — | — | stored_value §4 |
| Courtesy return outside the window | up to 10 days past, once per account | beyond 10 days | beyond 10 days | returns §1, §3 |
| Restocking consideration on an opened return | yes, at discretion | — | — | returns §2 |
| Free spare part under warranty | yes | — | — | spare_parts §2 |
| Honouring an advertised or coupon price | yes, subject to MRP | — | — | sales §1, §2, §3 |
| Post-purchase price adjustment | inside 14 days | outside 14 days | outside 14 days | sales §4 |
| Competitor price match | no | no | yes | sales §4 |
| Loyalty or save offer | within the published tiers | outside the tiers | outside the tiers | retention §5 |
| Severity upgrade | yes, immediately | — | — | severity §4 |
| Batch quarantine | no | no | manufacturing only | manufacturing §3 |
| Partner or marketplace-channel disruption credit | up to 5% of order | up to 5% | above 5% | partner §4 |
| Account restriction for abuse | no | no | yes | fraud §8 |
| Account unblock/order-block after a compromise report | yes, immediately | — | — | account §5 |
| Bulk remedy across an incident cohort | no | no | incident owner | incident §4 |

Where a customer's situation qualifies under two rows, the more generous applies — a safety symptom overrides the transit-damage value threshold, as shipping §3.1 already states.

## 3. What Always Needs Recorded Sign-Off First

- Anything above the agent column in §2.
- Anything at all on a ticket meeting a legal trigger — the freeze in legal §3 outranks every row above.
- A remedy at partner, wholesale or marketplace-channel scale (partner §4), or one touching quarantined stock (manufacturing §3).
- A goodwill gesture on an account under abuse review (fraud §3).
- A commitment that departs from this corpus rather than merely exceeding a value.

Sign-off is recorded on the ticket, by name, **before the money moves or the promise is made** — not reconstructed afterwards. A remedy that was right but unrecorded is still a control failure, because the next reviewer cannot tell it from one that was never approved.

## 4. Never Permitted, at Any Level

- **Admitting or implying liability**, or attributing harm to the product — legal §2.
- **Selling above MRP**, under any circumstance — sales §1.
- **Using the word "recall"**, or describing an internal review as one — product_safety §3.1.
- **Promising a fix, a feature or a release date** that is not already committed — tech_support §4.
- **Telling a customer a policy prevents something the law requires** — legal §8.
- **Sending an assistant-generated draft unreviewed** — ai §1.
- **Disclosing internal information** — incident identifiers, bug tickets, batch investigations, supplier names, another customer's report — comms §3.
- **Making an external statement** to a regulator, a consumer commission, or the press — legal §6.

These are not thresholds that a senior enough person may cross. They are prohibitions.

## 5. Splitting to Stay Under a Limit

Issuing two remedies where one was needed, splitting a refund across tickets, or pairing a small refund with a small credit to avoid a sign-off is a policy breach regardless of whether the total was reasonable and regardless of intent. The limits exist so that spend above a line is visible; a split hides it. Where the right remedy is above authority, ask — approval is fast, and a well-argued request above a limit is the system working correctly rather than a failure to cope.

## 6. During a Declared Incident

When a systemic incident is declared, the incident owner may pre-authorise one standard remedy for every affected ticket, and agents apply it without individual sign-off. This **replaces** the matrix for that cohort; it does not suspend it. Anything outside the pre-authorised remedy, and any affected ticket that also meets a legal trigger, returns to the rules above. See incident §4.

## 7. Authority Is a Floor, Not a Target

Nothing here obliges an agent to spend up to their limit, and nothing here permits declining something a customer is entitled to because it sits near one. Entitlements under warranty, consumer law or MRP-compliant published pricing are owed at any value (legal §8) — the matrix governs discretion, not obligation.
