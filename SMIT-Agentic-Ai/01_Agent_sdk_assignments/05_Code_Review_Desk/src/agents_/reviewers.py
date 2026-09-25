"""Specialized reviewer clones."""

from __future__ import annotations

from agents import Agent
from agents.model_settings import ModelSettings
from agents.run_context import RunContextWrapper

from src.agents_.base_reviewer import build_base_reviewer
from src.config.settings import Settings
from src.context.review_context import ReviewContext
from src.hooks.agent_hooks import TestsReviewerHooks


def _instructions(focus: str):
    def build(
        ctx: RunContextWrapper[ReviewContext],
        agent: Agent[ReviewContext],
    ) -> str:
        del agent
        return (
            "You are a specialist code reviewer. "
            f"Language: {ctx.context.language}. Strictness: {ctx.context.strictness}. "
            f"Focus only on {focus}. Use the supplied diff and ruleset tools. "
            "Return only the typed findings list."
        )

    return build


def build_reviewers(
    *,
    chunks: dict[str, str],
    settings: Settings,
    rulesets_dir: str = "rulesets",
) -> tuple[Agent[ReviewContext], Agent[ReviewContext], Agent[ReviewContext]]:
    base = build_base_reviewer(
        chunks=chunks,
        settings=settings,
        rulesets_dir=rulesets_dir,
    )
    security = base.clone(
        name="SecurityReviewer",
        instructions=_instructions(
            "injection, secrets, unsafe deserialization, authentication, and dependency risk"
        ),
        model_settings=ModelSettings(temperature=0.2, tool_choice="required"),
    )
    tests = base.clone(
        name="TestsReviewer",
        instructions=_instructions(
            "test coverage, edge cases, and tests broken or skipped by the diff"
        ),
        hooks=TestsReviewerHooks(),
    )
    style = base.clone(
        name="StyleReviewer",
        instructions=_instructions(
            "readability, naming, formatting, and ruleset-defined conventions"
        ),
    )
    return security, tests, style
