---
department: billing
title: Billing & Refunds Policy
ref_prefix: billing
version: 1.0
effective_date: 2026-07-30
---

# Billing & Refunds Policy

This policy governs charge disputes, subscription billing, and refund handling once a payment has been successfully captured against a confirmed order. Where the payment itself failed, was stuck, or debited without an order being created, that is a payment-failure case and is handled under payments §1–§4, not here.

## 1. General Refund Authority

Support agents may issue refunds up to ₹8,000 without additional approval when the underlying cause (duplicate charge, pricing error, confirmed billing system fault) is clearly documented. Refunds above ₹8,000 require a billing-team lead sign-off, logged in the ticket before the refund is processed.

## 2. Subscription Cancellations

Cancellation requests take effect from the date the request was made, not the date it is processed. If a system or process failure causes a subscription to continue billing after a valid cancellation request was logged (email, in-app, or support ticket), every erroneous charge from the cancellation date forward must be refunded in full — this is a system fault, not a customer-initiated late cancellation, and the standard "no refunds for partial billing periods" rule does not apply. When resolving these cases, cancel the subscription directly in the billing platform rather than relying on the failed sync path, to avoid repeat billing.

## 3. Promotional Pricing Errors

If a promotional price was live and advertised at the time of an order but did not apply correctly at checkout — including cases where a coupon fails on bundle SKUs, multi-item carts, or due to a configuration gap not reflected on the public promotions page — the order should be manually adjusted to the intended promotional price and the difference refunded. The customer should never be asked to cancel and re-order to receive advertised pricing they were eligible for at time of purchase; see sales §2 for eligibility, and catalog §4 for what counts as published.

## 4. Refund Timelines

Refunds to a card post within 5–7 working days once initiated, depending on the issuing bank. This is the card-specific figure; for the route and turnaround on UPI, netbanking, wallet, EMI and COD orders — including the faster, sometimes statutory, turnarounds those carry — see payments §4. Where store credit is offered as an alternative to a card refund, it posts immediately, per stored_value §1. Agents should proactively state the applicable window when confirming a refund so customers don't file a second complaint for a refund that is simply still processing.

## 5. Duplicate Charges

Duplicate charges caused by payment gateway retries, double-submission, or checkout errors are refunded in full without requiring the customer to prove they were charged twice — payment gateway logs are the source of truth and should be checked before responding. Where the duplicate arose from a genuine second order rather than a processing error, order-cancellation handling in orders §2 applies instead.

## 6. Chargebacks & Disputes

If a customer mentions they have already filed or intend to file a bank or card-network chargeback, do not issue a parallel refund — doing so risks a double refund. Instead, note the chargeback in the ticket and let the standard chargeback process resolve it; inform the customer of this to avoid confusion. A pattern of chargebacks filed without contacting us first is reviewed under fraud §5.
