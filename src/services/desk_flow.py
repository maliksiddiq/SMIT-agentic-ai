"""Single-trace Desk orchestration."""

from __future__ import annotations

from dataclasses import asdict
import json

from agents import RunConfig, Runner, trace

from src.agents_.desk import build_desk, desk_input
from src.config.settings import Settings, record_run
from src.context.review_context import ReviewContext
from src.models.report import RemediationHandoffInput
from src.services.concurrency import ReviewerResult
from src.hooks.run_hooks import registered_run_hooks
from src.runners.ledger_runner import new_request_id


async def run_desk_orchestration(
    results: list[ReviewerResult],
    *,
    settings: Settings,
    context: ReviewContext,
    max_turns: int,
):
    request_id = new_request_id()
    serialized = [
        {
            "agent_name": result.agent_name,
            "findings": [finding.model_dump() for finding in result.findings],
            "partial": result.partial,
        }
        for result in results
    ]
    desk = build_desk(settings)
    result = await Runner.run(
        desk,
        desk_input(serialized),
        context=context,
        max_turns=max_turns,
        hooks=registered_run_hooks(),
        run_config=RunConfig(workflow_name="Code Review Desk"),
    )
    record_run(
        ReviewerResult(
            agent_name=result.last_agent.name,
            findings=[],
            duration_ms=0,
            tokens_used=0,
        ),
        request_id=request_id,
    )
    return result


async def run_full_review(
    agents,
    *,
    context: ReviewContext,
    settings: Settings,
    files: list[str],
    max_turns: int,
    on_event=None,
):
    """Run fan-out, Desk tool/handoff orchestration, and assembly in one trace."""

    from src.services.concurrency import run_reviewers_concurrently_streamed

    request_id = new_request_id()
    with trace(
        "code-review-desk",
        metadata={"request_id": request_id},
        disabled=not settings.tracing_enabled,
    ):
        results = await run_reviewers_concurrently_streamed(
            agents,
            context=context,
            files=files,
            max_turns=max_turns,
            on_event=on_event,
        )
        desk_result = await run_desk_orchestration(
            results,
            settings=settings,
            context=context,
            max_turns=max_turns,
        )
    return results, desk_result
