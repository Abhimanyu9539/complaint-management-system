---
title: Complaint Intake & Classification Policy
ref_prefix: intake
version: 1.0
effective_date: 2026-07-30
---

# Complaint Intake & Classification Policy

This policy is company-wide and governs the first minute of every complaint: what we accept, what we must capture, and which department the ticket belongs to. Getting this wrong is expensive in a way that is hard to see later — a misrouted ticket is not just delayed, it is answered by people whose policy does not apply to it.

## 1. Complaint or Enquiry

A complaint is a customer telling us that something we sold or did has fallen short: a fault, a charge, a delivery, a service failure, a broken promise. An enquiry is a customer asking us something. The distinction matters because complaints carry response obligations (sla §2) and enquiries do not, so when the two are mixed in one message — and they often are — the message is a complaint and the enquiry is answered inside the reply. A customer who does not use the word "complaint" has still made one, and a customer who says "this isn't a complaint, but…" almost always has.

## 2. Channels

Complaints reach us through the app, the website, email, phone, in-app chat, social media, and — as a formal escalation route rather than a routine one — the National Consumer Helpline (NCH/INGRAM), which is handled per grievance §3. Every channel gets the same acknowledgement and response obligations under sla §2; a complaint is not treated as lower priority because it arrived on social media, and it is not treated as automatically urgent because it did either — severity is assessed the same way regardless of channel (severity §3).

## 3. What We Capture, and What We Never Wait For

Every ticket needs a subject, the customer's account of what happened in their own words, and a way to reach them. Beyond that, capture what the remedy will need: the **order ID** for anything order- or product-related (this is the primary identifier — orders §1), the batch code for a quality or safety report (qa §2), the transaction reference for a payment dispute (payments §2). Ask for what is missing — but **never delay acknowledging a complaint because a field is empty.** Acknowledgement is not conditional on the customer having filled in our form correctly, and a first response that only asks for information the customer already gave us is worse than none. Collect the minimum the remedy requires and no more (privacy §1).

## 4. The Routing Question

There are twelve departments and they are a closed set. The routing question is not "what is this complaint about?" — a burning smell is about a product, a charge and a warranty all at once — it is **"who can decide the remedy?"** A blender that smells of burning is a safety report because Product Safety decides what happens next, even though the customer framed it as a warranty question. Route to the department whose policy authorises the outcome, and mention the rest in the ticket rather than splitting it.

## 5. Tie-Breaks

Where more than one department could own it, this order decides:

1. **Injury, illness or a legal claim** → legal §1, ahead of everything.
2. **A safety symptom** — smoke, burning, sparking, overheating, mechanical failure in use → product_safety §1.
3. **Account compromise or an unauthorised order** → account §1.
4. **A named product fault** → warranty for physical failure, tech_support for behaviour that may be configuration or firmware.
5. **Money debited with no order confirmed, or a stuck payment** → payments §1, ahead of a routine billing dispute.
6. **Money already charged on a confirmed order, with no product fault** → billing for charges already taken, sales for what the price should have been, stored_value for wallet, coupon or gift-card balances.
7. **The order itself is wrong** — never arrived, arrived incomplete, arrived as the wrong item, was cancelled by us → orders or delivery, per §7 below.
8. **The customer wants to leave** → retention, unless a fault is the reason, in which case fix the fault first (retention §5).

A ticket raising several genuine issues stays whole and is owned by the department handling the most severe one; the others are referred under escalation §7 rather than opened as duplicate tickets against the same customer.

## 6. Order-Related Routing

Because so much of an e-commerce complaint volume is order-shaped, the specific symptom decides the owner: a payment that failed or debited without a confirmed order goes to payments; an order that oversold or was cancelled by us goes to orders; a shipment that is simply late, lost or damaged goes to shipping; a shipment that is wrong, incomplete, tampered, or failed to deliver goes to delivery; a customer-initiated return goes to returns for eligibility and reverse for the pickup itself; and a defect in what arrived goes to warranty. An agent unsure which of these applies routes to the one matching the customer's primary complaint and lets escalation §1 handle the rest if it turns out to be wrong.

## 7. Automated Classification and the Confidence Floor

Where a department is predicted automatically, a confidence of **0.60 or above** is routed to that department directly. Below 0.60, the ticket goes to human review rather than to the most likely department — a wrong confident route costs more than a short queue, because the receiving department reads it against the wrong policy and answers accordingly. A near-tie between two departments above the floor goes to the higher-priority one under §5, not to the marginally higher score. Automated classification never sets severity: that is assessed under severity §3, and it never closes or resolves anything (§9).

## 8. Duplicates and Multiple Channels

One customer, one issue, one ticket — regardless of whether they wrote in twice, wrote and then called, or replied to an old thread about the same fault. Merge into the earliest ticket so the age of the complaint reflects when the customer first raised it, not when we noticed the pattern; the response clock runs from the first contact. Two genuinely different issues from the same customer stay as two tickets. A duplicate is merged, never closed unread — the second message often contains what was missing from the first.

## 9. Misrouted Tickets Move Once, Forwards

A department that receives a ticket which is not theirs re-routes it directly to the department that owns it, records why, and does not return it to the queue or hand it back to the sender to try again. One re-route is normal; a second on the same ticket means the routing question in §4 has no clear answer and the ticket goes to a lead. Bouncing a complaint between departments is invisible internally and extremely visible to the customer, who is waiting through all of it.

## 10. Nothing Closes Itself

A ticket is resolved when the customer has an outcome, or when they have told us they no longer need one. Silence is not consent: an unanswered customer is chased under sla §5 before any close, and a ticket closed for non-response is closed with a message saying so and how to reopen it. Automated processes may classify, route, prioritise and draft; they may not resolve, and they may not send (ai §1).
