---
department: billing
title: Payment Failure & Reversal Policy
ref_prefix: payments
version: 1.0
effective_date: 2026-07-30
---

# Payment Failure & Reversal Policy

This policy governs money that moved, or tried to move, before an order existed to attach it to. Once a payment has successfully settled against a confirmed order, a dispute over that charge is billing §1–§6, not this policy.

## 1. Debited but No Order Confirmed

This is the single most common payment complaint in e-commerce: the customer's bank shows a debit, but no order confirmation was received. Treat this as real and urgent from the first message — never as the customer being mistaken, and never by asking them to "wait and see if the order appears." Check the payment gateway and bank reference immediately: if the debit is confirmed but no corresponding order exists in our system, the amount is either auto-reversed under the timelines in §5, or if it has genuinely reached us without a matching order, refunded manually within 2 business days regardless of general refund authority in billing §1 — this is not a discretionary refund, it is money we cannot show a reason to hold.

## 2. Failed or Dropped Payment Mid-Checkout

Where a payment fails, times out, or the customer's session drops mid-checkout, no order is created and nothing should be charged. Where a charge did occur despite the failure message shown to the customer, treat it as §1. Never tell a customer to "just try again" without first checking whether an earlier attempt actually succeeded — this is how duplicate orders under orders §3 happen.

## 3. Authorisation Hold vs. Settled Charge

A card authorisation hold (sometimes shown as "payment pending" on a bank statement) is not a completed charge — it is a reservation that releases automatically, typically within 5–7 business days, whether or not the order proceeds. Explain this distinction plainly to a customer who sees a pending amount: it is not money taken, and it does not need us to "release" it on our end unless our systems show we captured it. Where a hold has not cleared well beyond the normal release window, escalate to the payment gateway for confirmation rather than asking the customer to keep waiting indefinitely.

## 4. Refund Route and Turnaround Per Instrument

A refund returns to the instrument the payment was made with, and each has its own turnaround once we initiate it:

| Instrument | Turnaround once initiated |
| --- | --- |
| UPI | Instant to 2 business days |
| Debit or credit card | 5–7 working days (billing §4) |
| Net banking | 3–5 working days |
| Wallet | Instant to 1 business day |
| EMI (card or no-cost) | 1–2 billing cycles, per the issuing bank's EMI reversal process |
| COD (no payment on file) | Bank transfer or UPI collected from the customer, or wallet credit if they prefer, within 5 business days of the refund decision |

Store credit, where the customer chooses it over a refund to source, posts immediately per stored_value §1. Agents state the applicable turnaround for the customer's specific instrument when confirming a refund, not a generic figure, so a refund still processing does not read as a refund that never happened.

## 5. Prescribed Auto-Reversal Turnaround and Compensation

For a failed transaction where money was debited and the order could not be completed, the payment ecosystem's operating rules prescribe an automatic reversal to the customer's account within a fixed turnaround (T+1 to T+5 working days depending on the payment rail and failure type), and compensation for each day of delay beyond that turnaround, credited automatically by the bank or gateway rather than by us. Where a customer reports a delay beyond the prescribed turnaround, escalate to the payment gateway immediately rather than treating it as routine — this window is a regulatory obligation on the payment ecosystem, not a target we set, and support does not need to calculate the compensation itself, only ensure the case is pursued.

## 6. Manual Reversal Outside Standard Reconciliation

A manual reversal initiated outside the standard automated reconciliation path — moving money directly rather than through the normal refund or auto-reversal mechanism — is never performed by an agent or a lead. It requires admin approval and is logged with the gateway reference, because this path bypasses the controls that make every other reversal auditable by design.

## 7. E-Mandate Pre-Debit Notification

For any recurring payment set up as an e-mandate (CarePlan+ and other subscriptions billed via auto-debit), the customer must receive advance notification before each debit above the regulatory threshold, with the ability to cancel the mandate before it processes. Where a customer disputes a recurring charge on the grounds that they received no such notification, treat the notification failure itself as the fault under billing §2 — refund the charge in full and fix the mandate, rather than defending the charge because the service was technically still active.

## 8. GST Credit Note on Refund

Every refund against a GST invoice is accompanied by a credit note referencing the original invoice, issued automatically by billing systems and never something a customer needs to separately request. Where a customer or a GST-registered business customer asks for the credit note and cannot find it, treat this as an invoice-correction request under sales §6, not as a payments matter.
