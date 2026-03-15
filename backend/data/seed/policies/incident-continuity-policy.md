---
title: Systemic Incident & Continuity Policy
ref_prefix: incident
version: 1.0
effective_date: 2026-07-30
---

# Systemic Incident & Continuity Policy

This policy is company-wide and governs the case where one cause produces many complaints. Handling those complaints one at a time is the expensive failure mode: the same investigation is repeated by every agent, customers get inconsistent answers, and nobody notices the shape of the problem until it is in the press.

## 1. What Makes It Systemic

An incident is one root cause producing complaints across unrelated customers. In practice it looks like: a payment-gateway outage causing widespread debited-but-not-confirmed orders, an app or website release that breaks checkout or order status, a coupon left misconfigured and applied thousands of times before anyone notices, a courier hub disruption stalling deliveries across a region, an oversell event where inventory sync failed and many orders were confirmed for stock we did not have, or a batch defect in circulation. The signal is not volume alone — a single report can be systemic if the cause obviously affects everyone exposed to it, and a hundred unrelated complaints are not an incident. The question is whether one fix resolves them all.

## 2. Declaring It

Any agent may raise a suspected incident; a lead or admin declares it. Declaration creates an incident record with a cause, a named owner, the affected population as far as it is known, and the remedy being applied, and **every affected ticket references that record**. This is what turns twenty separate investigations into one, and what lets the twenty-first ticket be answered in a minute. Under-declaring is the more common error: a suspected incident that turns out to be three coincidences costs an hour, while three unnoticed coincidences that were an incident cost weeks.

## 3. Tell Customers Before They Complain

Where the affected population can be identified, notify them before they contact us — the notification is cheaper than the complaints, and vastly cheaper than the trust. It says what happened, what it means for them specifically, what we are doing, and when it will be done. It does not blame a named third party, does not include internal identifiers, and does not go out in language the customer must decode (comms §3, §4). Where the population cannot be identified, prepare the answer so every agent gives the same one. A safety-related notification is never sent from here: whether and how affected customers are contacted about a hazard is decided under product_safety §3, and recall language remains reserved (product_safety §3.1).

## 4. Bulk Remediation Authority

The incident owner may pre-authorise one standard remedy for every affected ticket — a refund of erroneous charges, a price honour, a replacement, a credit — and agents apply it without individual sign-off. This **replaces** the matrix in authority §2 for that cohort rather than suspending it: the pre-authorised remedy is written into the incident record with its value and its scope, and anything outside that scope goes back to the normal limits. Any affected ticket that also meets a legal trigger leaves the cohort entirely and is handled under legal §1, where the remedy freeze in legal §3 applies regardless of what the cohort is receiving.

## 5. Working the Cohort

Severity is set once for the cohort under severity §2 and applies to every ticket in it, so that customers with the same problem are not served in the order they happened to write in. A standard response may be prepared for the cohort — and it is still read by a person before each send, because the assistant does not send and neither does a macro (ai §1). A customer whose situation differs from the cohort in a way that matters leaves it and is handled individually; the cost of the cohort approach is that the exceptions must actually be spotted.

## 6. Never "Known Issue" Without a Remedy

Telling a customer their problem is a known issue, with no fix and no date, converts one complaint into two: the original fault plus the discovery that we knew and did nothing. Where a cause is known and a fix is not yet available, the message must carry what the customer gets in the meantime — a workaround (tech_support §4), a remedy, or a date. "This is a known issue" is background, never an answer.

## 7. Closing and Learning

An incident closes when the cause is fixed, the affected population has been remediated, and the fix is verified — not when the complaints stop, which usually happens earlier. A post-incident review follows within **10 business days**, covering the cause, why detection took as long as it did, and what the complaint handling revealed. Where the review finds that a policy was missing, wrong, or unfindable, that is a review trigger under kb §5 — an incident that produces no change to the corpus has taught us nothing and will be handled just as slowly next time.

## 8. Volume Does Not Suspend the Targets

An incident is not a defence for missing response and resolution targets across the rest of the queue, and it does not extend the statutory acknowledgement and redressal windows in grievance §2 either. Where volume threatens them, the response is capacity and the pre-authorised remedy that makes each ticket fast — not silence. Any target that will be missed is communicated to that customer in advance under sla §4, and the ordinary breach obligations, including goodwill under retention §3, apply exactly as they would on a quiet week. The queue outside the incident keeps its ageing limits (sla §7): a low-severity complaint does not disappear because something larger happened.
