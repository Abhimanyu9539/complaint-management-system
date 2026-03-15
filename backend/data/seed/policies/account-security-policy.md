---
title: Account Security & Unauthorised Order Policy
ref_prefix: account
version: 1.0
effective_date: 2026-07-30
---

# Account Security & Unauthorised Order Policy

This policy is company-wide and governs a customer's account itself: signs it has been compromised, how support verifies identity before acting, and what happens when an order was placed by someone other than the account holder.

## 1. Recognising a Compromised Account

Signals include an order the customer says they did not place, a delivery or contact address changed without the customer's knowledge, a login from an unfamiliar device the customer is asking about, or a customer reporting they can no longer access their own account. Any one of these is treated as a possible compromise from the first message, not dismissed as the customer forgetting an order they placed.

## 2. Verification Before Any Account Action

No account detail is changed, no order is cancelled or modified, and no sensitive information is disclosed until the person contacting us is verified as the account holder or someone verified to act for them (vulnerable §4). Verification uses information only the account holder should have — order history details, registered contact information matched against what is on file — and **never** a password, an OTP, or a UPI PIN, which support must never ask a customer to share (privacy §2). Where verification cannot be completed, err toward protecting the account: decline the action and offer the customer an alternative path (a password reset through the app's own flow, escalation to a lead) rather than acting on an unverified request.

## 3. Login and OTP Failures

Where a customer cannot log in or is not receiving OTPs, first confirm whether this is a faulty app/website issue rather than an account problem — see tech_support §4 for the boundary between our systems and the customer's device. Where the account itself is the issue (locked, OTP going to an old number, forgotten credentials), guide the customer through the in-app recovery flow rather than resetting credentials manually on their behalf, which would itself be a verification risk under §2.

## 4. Address-Book and Contact Tampering

Where a customer reports a saved address or contact number in their account that they did not add, this is treated as a compromise signal under §1 regardless of whether any order has yet been placed against it. Remove the unrecognised entry once the customer is verified under §2, and check the account's recent order history for anything shipped to it.

## 5. Immediate Order-Block on a Reported Compromise

Any agent may place an immediate hold on an account's pending orders and block new orders from processing the moment a compromise is reported and the reporter is verified as the account holder — this does not wait for lead approval, because the cost of a brief hold is far lower than the cost of a fraudulent order shipping while we deliberate.

## 6. Liability for Orders Placed on a Compromised Account

Where an order is confirmed to have been placed by someone other than the account holder through account compromise rather than through the account holder's own action, the account holder is not liable for it: the order is cancelled if not yet dispatched, or treated as a full-refund case if it has shipped, without requiring the account holder to prove they did not place it beyond the verification already completed under §2. Where the payment method itself was also compromised (a saved card used fraudulently), that is escalated to payments §6 and the customer's bank or card issuer in parallel.

## 7. The Boundary With Abuse Review

A compromised account is a customer being victimised and is handled generously and quickly under this policy. This is the opposite of the abuse-review pattern in fraud §2, where the account holder's own claim pattern is the thing being reviewed — the two must not be confused. Where clustered claims across accounts share a device or address in a way that looks coordinated rather than like one victim, that is a fraud §2 signal instead, and the two policies may both apply to a single case: verify and protect the account under this policy first, then let fraud review run in parallel if the pattern warrants it.
