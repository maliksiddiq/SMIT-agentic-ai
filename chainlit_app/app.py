"""Streaming Chainlit surface for Code Review Desk."""

from __future__ import annotations

import chainlit as cl

from src.agents_.reviewers import build_reviewers
from src.config.settings import ConfigurationError, load_settings
from src.context.review_context import ReviewContext
from src.guardrails.secret_guardrail import inspect_report
from src.services.concurrency import run_reviewers_concurrently
from src.services.diff_splitter import split_unified_diff
from src.agents_.merge_specialist import merge_findings
from src.services.report_builder import build_final_report, render_report


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
    results = await run_reviewers_concurrently(
        reviewers,
        context=context,
        files=list(chunks),
        max_turns=settings.turn_ceiling,
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
    report = build_final_report(results, merged.findings)
    rendered = render_report(report)
    guardrail = inspect_report(rendered)
    if guardrail.tripwire_triggered:
        await cl.Message(content=f"Refusal: {guardrail.reason}").send()
        return
    await cl.Message(content=rendered).send()
    cl.user_session.set("last_report", report)
