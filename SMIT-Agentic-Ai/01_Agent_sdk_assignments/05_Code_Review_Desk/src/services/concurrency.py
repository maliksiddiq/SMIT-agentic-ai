"""Concurrent reviewer execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import replace
from time import monotonic
from collections.abc import Mapping

from agents import Agent, Runner
from agents.exceptions import MaxTurnsExceeded
from agents.model_settings import ModelSettings
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


async def _prepare_runtime_agent(
    agent: Agent[ReviewContext],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
    chunks: Mapping[str, str] | None = None,
) -> Agent[ReviewContext]:
    """Satisfy Security's required tool contract before typed Gemini output.

    Gemini's OpenAI-compatible endpoint rejects forced tool choice together
    with JSON response MIME types. Run the required ruleset call as a
    provider-compatible preflight, then use an automatic tool choice for the
    typed response turn.
    """

    if agent.name == "SecurityReviewer":
        preflight = agent.clone(output_type=None)
        await Runner.run(
            preflight,
            (
                "You must call lookup_ruleset exactly once now. "
                "After the tool returns, reply DONE and do not call another tool."
            ),
            context=context,
            max_turns=max_turns,
            hooks=registered_run_hooks(),
        )
    if chunks is None:
        return agent
    settings = agent.model_settings or ModelSettings()
    return agent.clone(
        tools=[],
        model_settings=replace(settings, tool_choice=None),
    )


async def run_one_reviewer(
    agent: Agent[ReviewContext],
    *,
    context: ReviewContext,
    files: list[str],
    max_turns: int,
    chunks: Mapping[str, str] | None = None,
) -> ReviewerResult:
    started = monotonic()
    prompt = (
        "Review these diff files. Call read_diff_chunk exactly once for each "
        "listed file, consult the ruleset once if needed, then return typed "
        "findings: " + ", ".join(files)
    )
    if chunks is not None:
        prompt += "\n\nDiff contents:\n" + "\n\n".join(
            f"--- {file} ---\n{text}" for file, text in chunks.items()
        )
    try:
        runtime_agent = await _prepare_runtime_agent(
            agent,
            context=context,
            files=files,
            max_turns=max_turns,
            chunks=chunks,
        )
        result = await Runner.run(
            runtime_agent,
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
    chunks: Mapping[str, str] | None = None,
) -> list[ReviewerResult]:
    """Start all reviewer runs before awaiting any result."""

    clear_metrics()
    reviewer_kwargs = {
        "context": context,
        "files": files,
        "max_turns": max_turns,
    }
    if chunks is not None:
        reviewer_kwargs["chunks"] = chunks
    results = list(
        await asyncio.gather(
            *(
                run_one_reviewer(
                    agent,
                    **reviewer_kwargs,
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
        chunks: Mapping[str, str] | None = None,
) -> list[ReviewerResult]:
    clear_metrics()
    results = []
    reviewer_kwargs = {
        "context": context,
        "files": files,
        "max_turns": max_turns,
    }
    if chunks is not None:
        reviewer_kwargs["chunks"] = chunks
    for agent in agents:
        results.append(
            await run_one_reviewer(
                agent,
                **reviewer_kwargs,
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
    chunks: Mapping[str, str] | None = None,
) -> ReviewerResult:
    """Run one reviewer through the SDK streaming API."""

    started = monotonic()
    prompt = (
        "Review these diff files. Call read_diff_chunk exactly once for each "
        "listed file, consult the ruleset once if needed, then return typed "
        "findings: " + ", ".join(files)
    )
    if chunks is not None:
        prompt += "\n\nDiff contents:\n" + "\n\n".join(
            f"--- {file} ---\n{text}" for file, text in chunks.items()
        )
    try:
        runtime_agent = await _prepare_runtime_agent(
            agent,
            context=context,
            files=files,
            max_turns=max_turns,
            chunks=chunks,
        )
        streamed = Runner.run_streamed(
            runtime_agent,
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
    chunks: Mapping[str, str] | None = None,
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
                chunks=chunks,
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
