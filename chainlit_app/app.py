"""Streaming Chainlit surface for Code Review Desk."""

from __future__ import annotations

import sys
from pathlib import Path

import chainlit as cl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents_.reviewers import build_reviewers
from src.config.settings import ConfigurationError, load_settings
from src.context.review_context import ReviewContext
from src.guardrails.secret_guardrail import inspect_report
from src.services.concurrency import run_reviewers_concurrently
from src.services.diff_splitter import split_unified_diff
from src.agents_.merge_specialist import merge_findings
from src.services.report_builder import build_final_report, render_report
from src.services.desk_flow import run_full_review


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content="# Code Review Desk\nPaste a unified diff to begin a review."
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        await cl.Message(content=str(exc)).send()
        return

    context = cl.user_session.get("review_context")
    if context is None:
        context = ReviewContext(
            repo="chainlit-session",
            language="unknown",
            ruleset_id="default",
        )
        cl.user_session.set("review_context", context)

    split = split_unified_diff(message.content)
    if not split.ok:
        await cl.Message(content=split.error or "Could not parse the diff.").send()
        return

    chunks = {chunk.file: chunk.text for chunk in split.chunks}
    reviewers = build_reviewers(chunks=chunks, settings=settings)
    stream_messages: dict[str, cl.Message] = {}

    async def on_event(agent_name: str, event) -> None:
        if event.type == "raw_response_event":
            data = event.data
            delta = getattr(data, "delta", None) or getattr(data, "text", None)
            if delta:
                message_for_agent = stream_messages.get(agent_name)
                if message_for_agent is None:
                    message_for_agent = cl.Message(
                        author=agent_name,
                        content=f"### {agent_name} (streaming)\n",
                    )
                    await message_for_agent.send()
                    stream_messages[agent_name] = message_for_agent
                await message_for_agent.stream_token(str(delta))

    results, desk_result = await run_full_review(
        reviewers,
        context=context,
        settings=settings,
        files=list(chunks),
        max_turns=settings.turn_ceiling,
        on_event=on_event,
    )
    for result in results:
        if result.findings:
            await cl.Message(
                content="\n".join(
                    f"**{finding.severity}** `{finding.file}:{finding.line}` — "
                    f"{finding.message}"
                    for finding in result.findings
                )
            ).send()

    merged = merge_findings(results)
    remediation_triggered = desk_result.last_agent.name == "RemediationSpecialist"
    report = build_final_report(
        results,
        merged.findings,
        remediation_triggered=remediation_triggered,
    )
    rendered = render_report(report)
    guardrail = inspect_report(rendered)
    if guardrail.tripwire_triggered:
        await cl.Message(content=f"Refusal: {guardrail.reason}").send()
        return
    if report.partial:
        await cl.Message(
            content="⚠️ Partial review: one or more reviewers reached the turn ceiling.",
            author="Review status",
        ).send()
    if remediation_triggered:
        rendered = (
            "## Remediation handoff\n\n"
            + str(desk_result.final_output)
            + "\n\n"
            + rendered
        )
    await cl.Message(content=rendered, author="Final report").send()
    cl.user_session.set("last_report", report)
