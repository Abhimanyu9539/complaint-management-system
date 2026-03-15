---
title: Data Privacy, PII & Records Retention Policy
ref_prefix: privacy
version: 1.0
effective_date: 2026-07-30
---

# Data Privacy, PII & Records Retention Policy

This policy is company-wide and governs personal data in the complaint system: what we collect, what must never be written down, who may see it, how long we keep it, and what has to be removed before a resolved complaint becomes part of the knowledge base. It reflects our obligations as a data fiduciary under the Digital Personal Data Protection (DPDP) Act 2023.

## 1. Collect What the Remedy Needs

Ask for what the decision requires and stop there. A refund needs the order ID and the transaction reference; a warranty claim needs the serial or the order ID; a safety report needs the batch (qa §2). It does not need anything about the customer's household, their reason for being away when a delivery attempt failed, or details beyond what §3 of delivery actually requires to resolve a missed attempt. Where a customer volunteers more than we need — and distressed customers often do — we do not repeat it back into the ticket fields; the narrative stays in their own message and is not summarised into structured data. An adjustment granted for a personal circumstance is recorded as an adjustment, not as the circumstance (vulnerable §8).

## 2. Never in Ticket Text

The following must never be typed, pasted or attached into a ticket, a note, a draft or a chat message, and are removed immediately if a customer sends them:

- **Full card numbers, expiry dates, CVV codes.** We do not store card credentials at all — payments are tokenised at the gateway, and the last four digits of a card are sufficient to identify a charge and are permitted.
- **Aadhaar, PAN, or any other government identifier.**
- **UPI PIN, net-banking passwords, OTPs, or any other authentication credential.** We never ask a customer for one, and never record one they send unprompted — it is deleted from the ticket, and the customer is told never to share it with anyone, including us.
- **Medical records, diagnoses, prescriptions or images of injuries beyond what a safety or injury report requires** — a customer's statement that they depend on the product for a health reason is enough (vulnerable §1), and injury evidence is collected by Legal, not the queue (legal §4).

Where a customer has already sent one of these, tell them it has been removed and why, and never ask them to resend it another way.

## 3. Need to Know

Access follows the ticket, not the customer: a department answering a referral sees the complaint and what the question needs, not the account's full order history, other tickets, or unrelated correspondence. Do not pull an account record to satisfy curiosity about a complaint, and do not quote one customer's history to another in the same household or business. Every access is attributable, and access to a ticket under legal hold is restricted to those Legal names.

## 4. Data-Principal Rights and DPDP Grievances

Under the DPDP Act, a customer (a "data principal") has the right to access a summary of the personal data we hold about them and how it is processed, to correct or complete it, and to have it erased once it is no longer needed for the purpose it was collected for. A request invoking any of these is a data-protection grievance and is routed to Legal under legal §1 and **never actioned from the support queue** — not even the easy-looking ones, and not even deletion of a single ticket. Confirm receipt, tell the customer who is handling it and within what period, and hand over. Deleting a record because a customer asked, without the process, may destroy something under legal hold and cannot be undone.

## 5. Retention Schedule

| Record | Retained |
| --- | --- |
| Tickets and their correspondence | 24 months from resolution |
| Customer attachments (photos, documents) | 12 months from resolution |
| Resolved cases in the knowledge base | Indefinitely, once redacted per §6 |
| Ingestion and audit logs | 24 months |
| Records under legal hold | Until Legal releases the hold |

**A legal hold overrides every row above** (legal §4). Anything else is deleted on schedule rather than kept in case it is useful — data we no longer need is a liability, not an asset, and the DPDP Act's storage-limitation principle makes this a legal obligation as well as a good practice. A resolved case retained indefinitely is retained *because* it has been stripped of the person; that is the trade.

## 6. Redaction Before the Knowledge Base

A resolved complaint enters the case corpus for its reasoning, never for its participants. Before it is admitted (kb §7), remove or replace:

- **Names**, of the customer and of anyone they mention.
- **Contact details** — phone numbers, email addresses, delivery addresses.
- **Order, transaction, account and payment references**, and the last four digits of a card. These are directly re-identifying and are replaced with a placeholder, not shortened.
- **Serial numbers**, replaced with the batch or model prefix, which is what makes the case useful without identifying the unit's owner.
- **Free-text personal circumstances** — the health condition, the bereavement, the address arrangement. The fact that a courtesy exception was granted is retrievable and useful; the reason it was granted is not.

What must survive redaction is the complaint's shape, the policy applied, and the outcome. A case that has to keep a customer's identity to make sense has not been redacted properly and does not belong in the corpus.

## 7. Personal Data and Automated Processing

Ticket text and retrieved corpus documents may be sent to the models that classify and draft, because that is what the system is for. Nothing in §2 may be sent, and no more of the customer's narrative than the drafting needs. Retrieved knowledge-base content is redacted by §6 before it ever reaches a prompt, which is one reason redaction happens at admission rather than at retrieval time. See ai §5 for the drafting-side obligations.

## 8. Suspected Breach

A misdirected reply, an attachment sent to the wrong customer, a ticket visible to someone who should not see it, or any suspected unauthorised access is reported to Legal immediately — the same hour, not at the end of the shift. Do not attempt to recall, delete or quietly correct it first, because the record of what happened is what determines our reporting obligations, including whether the incident must be reported to the Data Protection Board under the DPDP Act. Support does not notify the affected customer, assess severity, or characterise the incident to anyone outside the company; that is Legal's decision under legal §6.
