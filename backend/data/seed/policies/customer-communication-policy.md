---
title: Customer Communication & Tone Policy
ref_prefix: comms
version: 1.0
effective_date: 2026-07-30
---

# Customer Communication & Tone Policy

This policy is company-wide and governs what we send to customers and how it reads. It applies to every outbound message regardless of who or what composed it, including assistant-drafted replies (ai §2).

## 1. Decision First, Plainly

Lead with the outcome. A customer opening a reply wants to know what is happening to their problem, not to read a paragraph of reconstruction before finding out. "We're refunding the duplicate charge of ₹7,499 today" comes before the explanation of the gateway retry that caused it. Write in ordinary language: no internal jargon, no department names as though the customer knows them, no passive constructions used to avoid saying who did something. Short sentences. No blame — not of the customer, not of a colleague, not of a named third party (§4).

## 2. What Every Reply Contains

1. **What we found** — the specific problem, in terms that show we read what they wrote.
2. **What we are doing** — the remedy, stated as a decision already taken where it has been.
3. **When** — a date or a window, not "shortly" or "as soon as possible".
4. **What the customer must do**, if anything — one clear action, or explicitly nothing.
5. **How to come back** — how to reply or reopen if the outcome is not right.

A reply missing the date, or missing the customer's actual question, will produce a second contact and start the repeat-contact clock in tech_support §3.

## 3. Internal Information Stays Internal

Departmental guidance is written for colleagues and is never forwarded verbatim. The following do not appear in customer-facing text under any circumstances:

- **Incident and bug identifiers**, and internal ticket references of any kind.
- **Open investigations** — batch reviews, quality investigations, root-cause work in progress (qa §6).
- **Contract manufacturer, plant and component identifiers** (manufacturing §5).
- **Internal agent notes, guidance text and approval discussions.**
- **Any reference to another customer's report**, including counts of similar reports.
- **Employee names beyond the agent handling the ticket**, and never a name attached to a fault.

The customer-facing version of "known integration gap, see INC-2291" is "a system fault on our side stopped your cancellation from reaching billing" — the same truth, without the internal record. Say what is true and useful about *their* case; say nothing about our internals.

## 4. Restricted Words and Claims

- **"Recall"** — reserved to Product Safety and Legal, and never used for an internal review (product_safety §3.1). The correct phrase is "under internal review".
- **"Defective", "faulty", "failed"** about a product on a ticket with a legal trigger — legal §2.
- **A price above MRP**, in any form — sales §1.
- **"Guarantee"**, and any promise of a future fix, feature or release date not already committed — tech_support §4.
- **A specific delivery date we do not control** — a courier's window is an estimate, not a promise; state it as the carrier's current estimate, not as our commitment (delivery §7).
- **Naming a third party as the cause** — a courier, a payment gateway, a phone manufacturer. The cause may be described without the name.
- **"As soon as possible", "shortly", "in the next update"** — commitments without dates, which read as evasion and produce chase contacts.
- **"Unfortunately, our policy is…"** as a reason for declining. Give the reason itself, or reconsider the decision.

## 5. Commitments Are Specific and Inside Policy

Only commit to what this corpus authorises and what we can deliver: an amount, a date, a next step, a named owner. Do not soften a decline into an implied maybe, and do not commit on another department's behalf while a referral is open (escalation §4). Where we cannot yet commit, say what we are doing to be able to and when the customer will hear next. A commitment made in error is honoured to the customer and corrected internally afterwards (sales §7) — never withdrawn mid-conversation.

## 6. Silence Is the Worst Message

Acknowledge before resolving, and update on the cadence in sla §6 whether or not there is progress. Where a target will be missed, the customer hears it from us first, with a new date (sla §4). "We don't have an answer yet, here is when we will" is a complete and acceptable message; nothing at all is not.

## 7. Channel, Identification and Language

Reply on the channel the customer used unless they ask otherwise, and keep one thread per issue (intake §8). Sign with a name the customer can ask for again. Identify the customer by order ID rather than by demanding account details they may not have to hand. Reply in the customer's preferred language and script — including regional languages and transliterated text where that is how the customer wrote to us — and never rely on the customer to translate a policy or a safety instruction back into a language we support; where translation is unavailable for a safety message, escalate rather than sending English and hoping (vulnerable §6). Safety instructions are given in plain imperative sentences: stop using it, unplug it, do not put it in household waste.

## 8. Repeat Contacts and Complaints About Us

Never restart from the beginning with a customer who has already explained their problem twice — reference what they told us and pick up from there (tech_support §3). When the complaint is about our handling rather than the product, acknowledge that specifically before addressing the underlying issue; a customer who is angry about being ignored is not reassured by a reply that ignores it. Match their register without matching their temperature: an apology for the experience is always available, an apology that attributes fault to the product on a live claim is not (legal §2).
