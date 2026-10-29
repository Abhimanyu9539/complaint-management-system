"""The live version of every prompt, in one place so a bump is easy to find and eval."""

from pydantic import BaseModel


class PromptSettings(BaseModel):
    # --- Chat graph ---
    # v6 adds the earlier conversation as background; v5 adds the remedy-freeze
    # override and the intake risk flags; v4 revises the failed draft on a retry;
    # v3 (feedback only), v2 (no feedback) and v1 (policies only) are kept as the
    # record and eval baselines.
    generate_prompt_version: str = "v6"
    # v5 also rewrites a follow-up into a standalone question, in the same call (the
    # ticket graph uses this prompt too, with no conversation); v4 sends questions
    # about the conversation itself to smalltalk_or_meta; v3 adds the knowledge_lookup
    # intent and its lookup_target; v2 adds risk flags.
    analyze_query_prompt_version: str = "v5"
    # v3 adds the earlier conversation, so it can recap it; v2 mentions policy and
    # case lookups in the "what can you do?" answer.
    smalltalk_prompt_version: str = "v3"
    # Knowledge lookup (the agent's own policy and case questions).
    # v2 adds the earlier conversation as background.
    lookup_prompt_version: str = "v2"

    # --- Chat memory ---
    compact_history_prompt_version: str = "v1"

    # --- Ticket graph ---
    # Ticket triage: department candidates, suggested severity, category, entities.
    # v2 takes the subject and body as one masked text; v1 took them separately.
    classify_ticket_prompt_version: str = "v2"
    # The ticket graph's reply written to the customer (the chat's `generate` writes to the agent).
    # v4 adds the remedy-freeze override and the intake risk flags; v3 adds a department's
    # answer from a similar past case; v2 the ticket's own answer.
    customer_reply_prompt_version: str = "v4"
    # The question emailed to a department when a ticket is escalated.
    dept_question_prompt_version: str = "v1"

    # --- Email ---
    # The model check on a new email: is it a customer writing?
    email_screen_prompt_version: str = "v1"

    # --- Guardrails ---
    # When NeMo's fact check blocks, a cheap model names the unsupported claims.
    fact_check_prompt_version: str = "v1"

    # --- Flywheel ---
    # The internal summary of what was sent, stored as the case's resolution.
    case_resolution_prompt_version: str = "v1"
    # The judge that decides whether a new case duplicates a past one.
    case_duplicate_prompt_version: str = "v1"
