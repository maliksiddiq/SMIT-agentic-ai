"""Shared Gemini-backed reviewer definition."""

from __future__ import annotations

from agents import Agent, Runner
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.run_context import RunContextWrapper
from openai import AsyncOpenAI

from src.config.settings import Settings, load_settings
from src.context.review_context import ReviewContext
from src.models.finding import Finding
from src.tools.diff_tools import make_diff_chunk_tool
from src.tools.ruleset_tool import lookup_ruleset, make_ruleset_tool
from src.services.instructions import build_reviewer_instructions


def create_gemini_model(settings: Settings, model_name: str | None = None):
    """Create an explicit agent-level Gemini model."""

    client = AsyncOpenAI(
        api_key=settings.gemini_api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    return OpenAIChatCompletionsModel(
        model=model_name or settings.gemini_model_primary,
        openai_client=client,
    )


def build_base_reviewer(
    *,
    chunks: dict[str, str],
    settings: Settings | None = None,
    rulesets_dir: str = "rulesets",
) -> Agent[ReviewContext]:
    """Build the common reviewer with explicit model and typed output."""

    active_settings = settings or load_settings()
    diff_tool = make_diff_chunk_tool(chunks)
    ruleset_tool = make_ruleset_tool(rulesets_dir=rulesets_dir)

    def instructions(
        ctx: RunContextWrapper[ReviewContext],
        agent: Agent[ReviewContext],
    ) -> str:
        del agent
        ruleset = lookup_ruleset(ctx.context, rulesets_dir=rulesets_dir)
        return build_reviewer_instructions(
            ctx.context,
            specialist_focus="general correctness, safety, and maintainability",
            ruleset_text=ruleset,
        )

    return Agent(
        name="BaseReviewer",
        model=create_gemini_model(active_settings),
        instructions=instructions,
        tools=[diff_tool, ruleset_tool],
        output_type=list[Finding],
    )


async def run_base_reviewer(
    agent: Agent[ReviewContext],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
):
    """Run one reviewer with an explicit per-call turn ceiling."""

    prompt = (
        "Review the supplied diff files. Use read_diff_chunk for each file: "
        + ", ".join(files)
        + ". Return only the typed findings list."
    )
    return await Runner.run(
        agent,
        prompt,
        context=context,
        max_turns=max_turns,
    )
