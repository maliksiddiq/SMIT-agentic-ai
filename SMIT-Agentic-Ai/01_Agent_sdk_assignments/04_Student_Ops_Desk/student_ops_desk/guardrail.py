class GuardrailTripwire(RuntimeError):
    """Raised before the Desk when a question is outside the bootcamp domain."""


def check_bootcamp_scope(question: str) -> None:
    terms = {
        "course", "class", "bootcamp", "assignment", "deadline", "submission",
        "career", "job", "skill", "schedule", "batch", "attendance", "scholarship",
        "policy", "student", "mentor", "enrol", "enroll",
    }
    if not isinstance(question, str) or not question.strip():
        raise GuardrailTripwire("Please ask a bootcamp-related question.")
    if not any(term in question.lower() for term in terms):
        raise GuardrailTripwire("I can only help with questions about the bootcamp.")

