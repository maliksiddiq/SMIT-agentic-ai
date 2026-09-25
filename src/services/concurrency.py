"""Concurrent reviewer execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

from agents import Agent, Runner
from agents.exceptions import MaxTurnsExceeded
from src.hooks.run_hooks import clear_metrics, registered_run_hooks
from src.config.settings import record_run

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
            hooks=registered_run_hooks(),
        )
        output = result.final_output
        findings = output if isinstance(output, list) else []
        metrics = {
            metric.agent_name: metric
            for metric in registered_run_hooks().metrics()
        }
        tokens = metrics.get(agent.name).total_tokens if agent.name in metrics else 0
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

    clear_metrics()
    results = list(
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
    from src.runners.ledger_runner import new_request_id

    request_id = new_request_id()
    for result in results:
        record_run(result, request_id=request_id)
    return results


async def run_reviewers_sequentially(
        agents: tuple[Agent[ReviewContext], Agent[ReviewContext], Agent[ReviewContext]],
        *,
        context: ReviewContext,
        files: list[str],
        max_turns: int,
) -> list[ReviewerResult]:
    clear_metrics()
    results = []
    for agent in agents:
        results.append(
            await run_one_reviewer(
                agent,
                context=context,
                files=files,
                max_turns=max_turns,
            )
        )
    return results


async def run_one_reviewer_streamed(
    agent: Agent[ReviewContext],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
    on_event=None,
) -> ReviewerResult:
    """Run one reviewer through the SDK streaming API."""

    started = monotonic()
    prompt = (
        "Review these diff files using the tools, then return typed findings: "
        + ", ".join(files)
    )
    try:
        streamed = Runner.run_streamed(
            agent,
            prompt,
            context=context,
            max_turns=max_turns,
            hooks=registered_run_hooks(),
        )
        async for event in streamed.stream_events():
            if on_event is not None:
                await on_event(agent.name, event)
        output = streamed.final_output
        findings = output if isinstance(output, list) else []
        metrics = {
            metric.agent_name: metric
            for metric in registered_run_hooks().metrics()
        }
        tokens = metrics.get(agent.name).total_tokens if agent.name in metrics else 0
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


async def run_reviewers_concurrently_streamed(
    agents: tuple[Agent[ReviewContext], Agent[ReviewContext], Agent[ReviewContext]],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
    on_event=None,
) -> list[ReviewerResult]:
    clear_metrics()
    results = await asyncio.gather(
        *(
            run_one_reviewer_streamed(
                agent,
                context=context,
                files=files,
                max_turns=max_turns,
                on_event=on_event,
            )
            for agent in agents
        )
    )
    from src.config.settings import record_run
    from src.runners.ledger_runner import new_request_id

    request_id = new_request_id()
    for result in results:
        record_run(result, request_id=request_id)
    return list(results)
