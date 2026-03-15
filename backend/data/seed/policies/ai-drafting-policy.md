---
title: AI-Assisted Drafting & Human Review Policy
ref_prefix: ai
version: 1.0
effective_date: 2026-07-30
---

# AI-Assisted Drafting & Human Review Policy

This policy is company-wide and governs the assistant that retrieves from the knowledge base and drafts replies. It exists because a fluent, confident, wrong answer is more dangerous than an obviously incomplete one, and because the person who presses send owns what it says.

## 1. The Assistant Drafts; a Human Sends

No customer-facing message is sent without a person reading it in full and choosing to send it. There is no auto-send, no send-if-confidence-is-high, no silent sending of routine categories, and no bulk send across a cohort — including during a declared incident (incident §5). The assistant may also classify, route, prioritise and summarise; it may not resolve a ticket, close a ticket, or issue a remedy (intake §10).

## 2. Grounded or Removed

Every factual and normative claim in a draft must trace to a retrieved policy clause or case, and the citation is retained with the draft so the reviewer can check it rather than trust it. If a claim cannot be traced — an amount, a window, an eligibility rule, a promise about what happens next — it is **removed before sending**, not softened and not hedged. This applies with no exception to statutory entitlements: a draft may state a grievance-officer timeline, a DPDP right, or an MRP rule only where the corresponding clause (grievance §1–§2, privacy §4, sales §1) was actually retrieved, never inferred from general awareness that such rights exist. Plausibility is not grounding: an assistant that has read a 30-day return window and a 12-month warranty will produce a confident 60-day exchange window if the corpus is silent, and it will read exactly as authoritative as the true clauses beside it.

## 3. When the Corpus Does Not Answer

The correct behaviour when retrieval finds nothing adequate is to say so — to the agent, not to the customer — and stop. The assistant must not infer a threshold from a neighbouring one, average two cases into a rule, generalise from a single case to a policy, or reason from what a reasonable company would probably do. Where the corpus is silent, the ticket is referred under escalation §1, and the gap itself is recorded so the corpus can be fixed (kb §5). A visible "I don't have a basis for this" is the most valuable output this system produces, because it is the one an agent can act on safely.

## 4. Where a Draft May Not Go Out on an Agent's Judgement Alone

A lead reviews before sending on any ticket that:

- **Meets a legal trigger** — legal §1. On these, the freeze in legal §3 means most of what a draft would offer must not be offered at all.
- **Involves a safety symptom or an injury** — product_safety §1.
- **Touches recall, batch or investigation language** — product_safety §3.1, qa §6.
- **Carries a remedy above the agent's authority** — authority §3.
- **Concerns a customer in distress or at risk** — vulnerable §7.

On these tickets the assistant is a research tool. Its draft may inform the reply; it should not be the reply.

## 5. What May Be Sent to the Model

The ticket text, the retrieved corpus documents, and the ticket's own history. Nothing listed in privacy §2, ever. No more of the customer's personal narrative than the drafting actually needs (privacy §1). Corpus documents reaching a prompt are already redacted, because redaction happens at admission (privacy §6, kb §7) — which is what makes retrieval safe by construction rather than by care at each call.

## 6. Review Is Recorded

Every draft records what the reviewer did with it — accepted, edited, or rejected — and an edit or rejection records why: the wrong case was retrieved, the wrong policy was cited, the tone was wrong, or something else. This is not administrative overhead; it is the only systematic signal about where retrieval and generation fail, and a review culture that accepts everything produces a system nobody can improve. Reviewers are measured on the quality of what they send, never on how fast they clear drafts.

## 7. Traceability

Every draft records the model and the prompt version that produced it. **A prompt change is a change of record**, versioned like a policy (kb §6): a reply we cannot reproduce is a reply we cannot defend, and "the wording changed at some point" is not an answer to a customer asking why they were told something different from their neighbour — or to a Consumer Commission asking the same question.

## 8. Accountability Does Not Transfer

The agent who sends a message owns it. "The assistant drafted it" is not an explanation to a customer, a regulator or a colleague, and the fact that a draft was generated never reduces the obligation to have read it. Where an agent sends a draft they knew was ungrounded, that is a policy breach with the same weight as writing the claim themselves.

## 9. Watching for Drift

Groundedness failures, edit reasons and rejection rates are reviewed monthly against the previous period. A sustained rise in ungrounded claims, in wrong-policy citations, or in rejections after a model or prompt change is grounds to **pause assisted drafting** and fall back to unassisted handling until the cause is found. The fallback must stay viable for exactly this reason: agents who can no longer resolve a complaint without a draft in front of them are a single outage away from being unable to work.
