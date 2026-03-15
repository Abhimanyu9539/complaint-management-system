---
department: qa
title: Quality Investigation Policy
ref_prefix: qa
version: 1.0
effective_date: 2026-07-30
---

# Quality Investigation Policy

This policy governs how product-quality defects are investigated once the customer in front of us has been made whole. It covers non-safety quality patterns across our own-brand production and our contract manufacturers; anything with a hazard or an injury in it belongs to the product safety policy, which sets a lower and faster threshold.

## 1. What Opens an Investigation

A single quality complaint is a data point, not a pattern: resolve it under the owning department's policy and record the batch. An investigation opens when **five or more reports of the same defect on the same SKU arrive within 60 days**, or immediately on the first report where the defect involves contamination, foreign material, or anything that reaches food, skin or breathing air. Safety-related reports have their own, much lower trigger — three reports sharing a batch prefix in 30 days, per product_safety §2 — and that trigger always wins where both could apply.

A **return-reason spike** is the earliest and most reliable signal an e-commerce quality function has: a sudden rise in "item not as expected", "defective on arrival" or "stopped working" as the stated reason for a specific SKU, visible in the reverse-logistics data days or weeks before enough individual complaints accumulate to trip the count above. QA reviews return-reason trends by SKU weekly and may open an investigation on that trend alone, without waiting for five direct complaints. Review text mentioning a defect (reviews §5) is a secondary signal worth the same attention.

## 2. Capture the Batch at First Contact

Every quality complaint must record the serial number and the batch or date-code prefix before the ticket is resolved. This is the only thing that distinguishes "one unlucky unit" from "one bad production run", and it cannot be recovered later once the unit has been refunded and discarded. Ask for it while the customer still has the unit in their hands. If the customer cannot find it, the order ID is an acceptable fallback — the batch can be recovered from fulfilment records — but a resolved ticket with neither is a permanent blind spot.

## 3. Contamination and Foreign-Material Defects

Foreign material in or on a product that contacts food, skin or breathing air is treated as a stop-use defect regardless of whether anyone was harmed. Tell the customer to stop using the unit, do not ask them to send the material back before resolving, and do not characterise the risk as small even if it appears to be. A customer who reports finding a plastic shaving in their food has not had a minor experience. These reports open an investigation on the first occurrence under §1, and any report where the customer describes having ingested, inhaled or been physically affected by the material is an injury report and belongs to legal §1.

## 4. Never Replace From the Suspect Batch

Where a defect is plausibly batch-related, a like-for-like replacement from the same batch is not a resolution — it is the same defect shipped twice at our expense, and it destroys the customer's confidence far more than the original fault did. Offer a refund, a different product line, or a replacement verified to be from a different batch and confirmed against the fulfilment centre's quarantine record (manufacturing §3). If no verified-good stock exists, say so and offer the refund; do not ship hopefully. Where the customer has asked specifically not to receive another unit of the same product, that preference is binding.

## 5. Investigation States and Closure

An investigation is **open** (reports accumulating, cause unknown), **root-caused** (mechanism identified, corrective action defined), or **closed** (corrective action verified, or the pattern disproved as coincidental). An investigation may not sit in `open` for more than 30 days without a written status: either it advances, or it is closed as unsubstantiated with the reasoning recorded, so that the same reports can reopen it later if they resume. A root-caused investigation that traces to production or an inbound component hands the corrective action to manufacturing §7; qa does not close it until the verification there is complete.

## 6. What a Customer May Be Told

Customers may be told their report has been logged for quality investigation and that the batch information they provided is going to the team that inspects it — that is true, useful, and reassuring. They may not be told a defect is confirmed before it is, given a cause we have not established, or told anything using recall language, which is reserved and defined in product_safety §3.1. Internal identifiers, supplier names and investigation numbers never appear in customer-facing text (comms §3). If the customer asks whether other people have reported the same thing, the honest answer is that we do not discuss other customers' reports, and that theirs is being investigated.

## 7. Feeding the Rest of the System

Quality findings are only worth the investigation if they change something. A root-caused defect updates the known-issue register that support diagnoses from (tech_support §2), and where the fix changes what we are willing to offer a customer, it triggers a policy revision under kb §5. An investigation that concludes without either of those outcomes should say explicitly why no change was warranted.
