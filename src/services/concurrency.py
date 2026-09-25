"""Concurrent reviewer execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

from agents import Agent, Runner
from agents.exceptions import MaxTurnsExceeded
from agents.run_context import RunContextWrapper

from src.context.review_context import ReviewContext
from src.models.finding import Finding


@dataclass(frozen=True)
class ReviewerResult:
    agent_name: str
    findings: list[Finding]
    duration_ms: int
    tokens_used: int
    partial: bool = False
    error: str | None = None


async def run_one_reviewer(
    agent: Agent[ReviewContext],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
) -> ReviewerResult:
    started = monotonic()
    prompt = (
        "Review these diff files using the tools, then return typed findings: "
        + ", ".join(files)
    )
    try:
        result = await Runner.run(
            agent,
            prompt,
            context=context,
            max_turns=max_turns,
        )
        output = result.final_output
        findings = output if isinstance(output, list) else []
        usage = getattr(result, "context_wrapper", None)
        tokens = int(getattr(getattr(usage, "usage", None), "total_tokens", 0) or 0)
        return ReviewerResult(
            agent_name=agent.name,
            findings=findings,
            duration_ms=int((monotonic() - started) * 1000),
            tokens_used=tokens,
        )
    except MaxTurnsExceeded:
        return ReviewerResult(
            agent_name=agent.name,
            findings=[],
            duration_ms=int((monotonic() - started) * 1000),
            tokens_used=0,
            partial=True,
            error="Reviewer reached the turn ceiling; this is a partial review.",
        )
    except Exception as exc:
        return ReviewerResult(
            agent_name=agent.name,
            findings=[],
            duration_ms=int((monotonic() - started) * 1000),
            tokens_used=0,
            error=f"Reviewer failed: {exc}",
        )


async def run_reviewers_concurrently(
    agents: tuple[Agent[ReviewContext], Agent[ReviewContext], Agent[ReviewContext]],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
) -> list[ReviewerResult]:
    """Start all reviewer runs before awaiting any result."""

    return list(
        await asyncio.gather(
            *(
                run_one_reviewer(
                    agent,
                    context=context,
                    files=files,
                    max_turns=max_turns,
                )
                for agent in agents
            )
        )
    )

