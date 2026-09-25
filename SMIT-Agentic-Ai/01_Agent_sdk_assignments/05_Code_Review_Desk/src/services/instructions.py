"""Per-run reviewer instruction construction."""

from src.context.review_context import ReviewContext


def build_reviewer_instructions(
    context: ReviewContext,
    *,
    specialist_focus: str,
    ruleset_text: str,
) -> str:
    """Build model-visible instructions without exposing the repository name."""

    return (
        "You are a code review specialist. Review only the supplied unified "
        "diff chunks and return a list of typed findings. "
        f"Language: {context.language}. Strictness: {context.strictness}. "
        f"Specialist focus: {specialist_focus}. "
        f"Applicable ruleset: {ruleset_text}"
    )

