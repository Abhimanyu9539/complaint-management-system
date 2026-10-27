"""Fixed text shown to agents and customers, kept here so the wording is tunable without a deploy."""

from pydantic import BaseModel


class MessageSettings(BaseModel):
    # --- Drafts and answers ---
    # What we say when retrieval found nothing. Kept here rather than inline in
    # the node so the wording is tunable without a deploy.
    no_match_message: str = (
        "I couldn't find a policy section that covers this complaint, so I have "
        "nothing to base a response on. Please check the policy library directly "
        "or escalate to the responsible department — I'd rather say this than "
        "guess at an entitlement the customer may not have."
    )
    lookup_no_match_message: str = (
        "I couldn't find a policy or past case that answers this. Try rewording the "
        "question, or check the policy library directly."
    )
    # The ticket draft when no policy matches. No model call, so no claim to check.
    holding_reply_message: str = (
        "Dear customer,\n\n"
        "Thank you for contacting us. We have received your complaint (reference "
        "T-{ticket_no}) and a specialist is looking into it. We will come back to you "
        "with next steps as soon as we can.\n\n"
        "Kind regards,\nCustomer Care"
    )
    blocked_input_message: str = (
        "This complaint was not processed: it contains instructions aimed at the "
        "assistant, abusive content, or text the checks could not accept. Please "
        "read it and handle it manually."
    )
    # Worded for both branches: a complaint draft gets here after one retry, a
    # lookup answer on its first failure.
    grounding_caveat: str = (
        "CAUTION — this answer failed the guardrail checks. Verify every claim "
        "against the cited sources before using any of it:"
    )

    # --- Chat ---
    # Sent as the SSE `error` event when the graph raises mid-stream. The real
    # cause is logged; the browser gets something a user can act on.
    chat_error_message: str = (
        "The assistant could not finish this answer. Please try again."
    )

    # --- API errors (sent as `detail`; the real cause is logged) ---
    api_unavailable_message: str = (
        "The server could not finish this request. Try again in a moment, or check the server log."
    )
    # The email did not leave, so a retry is safe.
    email_send_failed_message: str = (
        "The email could not be sent. Nothing was recorded — try again in a moment."
    )
    # Shown to the customer on the complaint form, whose text is still in it.
    ticket_create_failed_message: str = (
        "We could not record your complaint just now. Your message has not been lost — "
        "please try again in a moment."
    )
    dept_question_failed_message: str = (
        "Could not draft a question. Write it yourself, or try again in a moment."
    )
    seed_corpus_unavailable_message: str = (
        "The seed corpus directory is not readable. Set SEED_DATA_DIR — see the server log "
        "for the paths tried."
    )
