"""Input and output guards: Guardrails AI checks, PII masking, NeMo rails and the fact check."""

from pydantic import BaseModel


class GuardrailSettings(BaseModel):
    # --- Guardrails ---
    # Kill switches. The Guardrails AI checks run locally; the NeMo rails are LLM calls.
    guardrails_enabled: bool = True
    nemo_rails_enabled: bool = False
    # Fits `CreateTicketRequest`: the ticket graph guards subject (200) + body (8000) as one text.
    query_min_chars: int = 1
    query_max_chars: int = 8300
    # Presidio entities masked out of the complaint and flagged in drafts (privacy §2).
    pii_entities: list[str] = [
        "CREDIT_CARD",
        "IN_AADHAAR",
        "IN_PAN",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
    ]
    # Credentials Presidio has no recognizer for: an OTP, UPI PIN or CVV and its digits.
    credential_pattern: str = r"(?i)\b(?:otp|one[- ]time password|upi pin|cvv)\b\D{0,15}\d{3,8}\b"

    # --- NeMo judge and fact check ---
    # Model for NeMo's output rails (fact check, tone). Measured on the 30 eval goldens
    # with the material-claims prompt: gpt-5.4-nano blocked 2 of 5 invented remedies,
    # gpt-5.4-mini blocked 5 of 5 with 5/30 drafts caveated. gpt-6-luna is not measured
    # yet. The input rail stays on `openrouter_model_cheap`.
    guard_judge_model: str = "openai/gpt-6-luna"
    # Claims the fact check names when NeMo blocks.
    # Enough to act on; more turns the retry feedback into a second draft.
    fact_check_max_claims: int = 5

    # --- Guard reasons and retry feedback ---
    # Recorded when a guard itself errors; the flow fails closed.
    guard_error_reason: str = "A guardrail check could not run."
    # Feedback when Presidio finds personal data in a draft.
    draft_pii_reason: str = (
        "The draft contains personal data (a card, ID, email or phone number). Remove it."
    )
    # Feedback for the regenerated draft, keyed by the NeMo rail that blocked it.
    rail_feedback: dict[str, str] = {
        "self check input": "The complaint contains instructions aimed at the assistant, or abuse.",
        "self check facts": (
            "A reviewer found claims the extracts do not support. State only what the "
            "extracts and past cases say, and cite each claim."
        ),
        "self check output": (
            "The draft is not written to the support agent. Write to the agent, with no "
            "greeting or sign-off, and in a neutral tone about the customer."
        ),
    }
    # The same feedback for a ticket's customer reply, whose rails check the opposite audience.
    customer_rail_feedback: dict[str, str] = {
        "self check facts": (
            "A reviewer found claims the extracts do not support. Tell the customer only "
            "what the extracts say, and cite each claim."
        ),
        "self check output": (
            "The reply is not fit to send to the customer. Write to the customer, never "
            "mention past cases, other customers or internal scores, and do not blame them."
        ),
    }

    @property
    def case_pii_entities(self) -> list[str]:
        """What is masked out of a case before indexing: the input guard's entities plus names."""
        return [*self.pii_entities, "PERSON"]
