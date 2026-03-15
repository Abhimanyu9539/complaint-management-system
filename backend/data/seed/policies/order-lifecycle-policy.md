---
department: sales
title: Order Lifecycle Policy
ref_prefix: orders
version: 1.0
effective_date: 2026-07-30
---

# Order Lifecycle Policy

This policy governs the order itself: when it becomes binding, how it may change, and what happens when we cannot fulfil what we confirmed. It does not cover price or promotions (sales), payment mechanics (payments), or what happens after dispatch (shipping, delivery, returns, reverse).

## 1. Order Confirmation Is the Binding Moment

An order is confirmed once payment is authorised (or, for COD, once the order is accepted) and a confirmation is issued with an order ID. From that point, the price, the items and the delivery address quoted are binding on us subject to §4 and §5. A cart, a saved-for-later list, or an item merely added to cart creates no obligation on either side — only a confirmed order does.

## 2. Modification and Cancellation Before Dispatch

Any order may be changed or cancelled at no cost until it is dispatched: address, quantity, variant, or cancellation in full. The dispatch scan is the cut-off, not the order date and not a warehouse's claim that an order is "already being packed". After dispatch the request becomes a return once the item arrives, handled under returns §1, and the customer should be told that plainly along with what it means for them — that they will receive the item and send it back, rather than that we cannot help. Where an address change arrives after dispatch and the shipment is still in the courier's network, attempt a re-route as a courtesy; if it fails, standard delivery-exception handling in delivery §1–§5 applies. Any refund arising from a pre-dispatch cancellation follows the route and timeline in payments §4.

## 3. Duplicate Orders From a Retry

Where a checkout retry, a double-tap, or a payment-gateway timeout results in two confirmed orders for what was clearly meant to be one purchase, the customer is never made to receive and return both to get a refund. Cancel the duplicate before dispatch wherever possible; where both have already dispatched, the second is treated as a company-caused return under returns §4 — reverse pickup at no cost, full refund including any shipping charged on it. This is distinct from a genuine second order the customer separately intended to place, which is handled normally.

## 4. Oversell and Stock-Out After Confirmation

Occasionally an order is confirmed against stock that inventory sync shows as available but that does not actually exist — an oversell. Where this happens, the customer is told **immediately**, not left to discover it when the shipment fails to move, and is offered the choice of waiting for restock with a committed date, switching to an equivalent product at no price difference, or a full and immediate refund. A fixed inconvenience credit of ₹500 is issued automatically to every affected order regardless of which option the customer chooses — no approval needed, per authority §2. Where the delay or disruption cost the customer materially more than that, additional goodwill is available under retention §2, assessed on the specifics rather than capped by the automatic amount.

## 5. Price Change Between Cart and Checkout

Where the price shown when an item was added to cart differs from the price at checkout because of a genuine, time-stamped price change, the checkout price applies — customers are not entitled to a price that expired before they completed the purchase. Where the difference is instead a system error (a promotion that should have applied and did not, a price that reverted incorrectly mid-checkout), sales §2 and billing §3 apply and the customer receives the correct price.

## 6. Pre-Orders, Backorders and COD Availability

A pre-order or backorder commits to a delivery window given at the time of order; where that window will be missed, the customer is told before it passes (comms §5) and may cancel for a full and immediate refund at any point while still waiting, not only after the missed date. Cash on delivery is offered on orders up to **₹20,000**; above that value, a prepaid payment method is required, and this is disclosed at checkout rather than discovered as a rejected order. Where COD eligibility has been withdrawn from a specific account under fraud §3, that is a decision recorded there, not a general policy exception created here.

## 7. Unserviceable Pincode After Order Placement

Where a delivery pincode becomes temporarily unserviceable after an order is confirmed, the customer is told promptly and given the choice to wait, provide an alternative serviceable address, or cancel for a full and immediate refund — see shipping §6 for the underlying serviceability rule.

## 8. What Order Status May and May Not Be Said to Mean

Order status shown to the customer (confirmed, packed, shipped, out for delivery, delivered) must match what has actually happened in our systems; a status is never advanced to make a delayed order look on track. "Shipped" means a courier has taken physical possession, not that a label has been generated. Where a status appears stuck for longer than the delivery window in shipping §1 allows, that is treated as a potential delivery exception under delivery §1–§5, not explained away as a system delay without checking.
