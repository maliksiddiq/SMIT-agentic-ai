"""Safe lookup of repository rulesets from local context."""

from __future__ import annotations

from pathlib import Path

from agents import function_tool
from agents.run_context import RunContextWrapper
from src.context.review_context import ReviewContext


def lookup_ruleset(
    context: ReviewContext,
    *,
    rulesets_dir: str | Path = "rulesets",
) -> str:
    """Read the context-selected ruleset without raising into a runner."""

    try:
        path = Path(rulesets_dir) / f"{context.ruleset_id}.md"
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, TypeError):
        return (
            f"No ruleset found for id '{context.ruleset_id}'. "
            "Proceeding with general best practices."
        )


def make_ruleset_tool(*, rulesets_dir: str | Path = "rulesets"):
    """Create a context-backed tool with no model-visible arguments."""

    @function_tool
    def read_ruleset(ctx: RunContextWrapper[ReviewContext]) -> str:
        return lookup_ruleset(ctx.context, rulesets_dir=rulesets_dir)

    read_ruleset.name = "lookup_ruleset"
    read_ruleset.description = "Look up the applicable repository ruleset from local context."
    return read_ruleset
