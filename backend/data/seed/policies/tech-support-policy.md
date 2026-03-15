---
department: tech_support
title: Technical Support & Troubleshooting Policy
ref_prefix: tech_support
version: 1.0
effective_date: 2026-07-30
---

# Technical Support & Troubleshooting Policy

This policy governs how a product that is not working as expected is diagnosed, and where the boundary sits between a support problem, a hardware defect, and a software bug we already know about. It does not set remedy values — a defect that survives this process is handled under the warranty policy and its service ladder (warranty §7).

## 1. Diagnose Remotely Before Booking a Visit

A reported malfunction is treated as diagnosable remotely until the documented steps for that symptom have been tried and recorded. Support should complete the reset, re-pair, power-cycle and firmware checks over chat, call or video before booking a technician visit, because a wasted on-site visit costs far more than the call itself and roughly half of reported "broken" units are a configuration or firmware state rather than a fault. Two rounds of remote troubleshooting is the limit: if the symptom persists after a second attempt, stop diagnosing and move to the service ladder in warranty §7 rather than asking the customer for a third round of the same steps. Never ask a customer to repeat a step a previous agent already recorded as tried.

## 2. Known Issues, Error Codes and Firmware

The known-issue register is authoritative for any error code the product reports. An error code with a documented cause and a shipped fix is a **known issue, not a defect** — the correct outcome is to apply the fix, not to book a service visit. Where a firmware release resolves the symptom, walk the customer through triggering the update rather than dispatching a technician who would arrive to a unit on the same firmware. Where the code has a documented reset procedure (a safety interlock reporting as a fault, for example), perform the procedure before treating the unit as failed. If an error code is not in the register, that itself is reportable: send it to qa so the register stays worth trusting.

## 3. Repeat Contacts on the Same Issue

A customer contacting us a third time about one unresolved issue is a process failure on our side, not a difficult customer. On the third contact the ticket gets a named owner who stays with it until closure, the diagnostic ladder is not restarted from step one, and a goodwill gesture is issued under the retention policy §3 without the customer having to ask for it. Repeat-contact tickets are re-assessed for severity on arrival (severity §4) — three failed attempts at a fix is itself evidence that the original severity was too low.

## 4. Faults Outside the Product

Some failures are real for the customer but are not device defects: a phone operating-system update that breaks Bluetooth pairing, a home WiFi router configuration that blocks the device, a third-party app permission change. A fault in **our own** shopping app or website — checkout errors, order status not updating, login failures — is a different problem entirely and belongs to account §3 or orders §8, not to a device diagnosis. Where the fault genuinely sits outside the product, support must offer a workaround that gets the customer working today — manual pairing, an alternative connection path, a configuration change — and must say plainly that the cause is external, without blaming a named third party (comms §4). A fix date may only be given if the release containing it is already committed; "in the next update" and "soon" are not acceptable commitments (comms §5).

## 5. Support Window for Older Products

Firmware and software support continues for 24 months after a product is discontinued, covering security and compatibility fixes but not new features. Outside that window, support is limited to documented troubleshooting and spare-parts availability (spare_parts §3); there is no obligation to produce a firmware fix, and support should say so rather than leaving the customer waiting for a release that will not come. A product outside its software support window still carries every safety obligation in this corpus, without exception.

## 6. When to Stop Troubleshooting

Three things end diagnosis immediately and take priority over any remaining step in the ladder:

- **A safety symptom** — smoke, burning smell, sparking, overheating, or a mechanical failure during use. Stop, tell the customer to stop using the unit, and hand the ticket to product_safety §1. Never ask a customer to reproduce a safety symptom for diagnostic purposes.
- **A physical failure** — a cracked housing, a snapped component, a dead charging circuit. Nothing in software will fix it; route to warranty §2.
- **A reported injury or a legal claim** — hand off under legal §1 and stop offering remedies of any kind.

## 7. Recording the Diagnosis

Whatever the outcome, the steps attempted and the result of each go on the ticket before it moves. This is what makes the next contact cheap rather than a restart, what lets qa see a pattern across accounts, and what the knowledge base inherits when the ticket is resolved (kb §7). A ticket that changes hands without a recorded diagnosis is incomplete regardless of how it is resolved.
