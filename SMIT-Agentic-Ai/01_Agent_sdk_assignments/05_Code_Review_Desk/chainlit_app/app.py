"""Streaming Chainlit surface for Code Review Desk."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import chainlit as cl
import openai
from agents.exceptions import (
    ModelBehaviorError,
    ModelTimeoutError,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents_.reviewers import build_reviewers
from src.config.settings import ConfigurationError, load_settings
from src.context.review_context import ReviewContext
from src.guardrails.secret_guardrail import inspect_report
from src.services.diff_splitter import split_unified_diff
from src.agents_.merge_specialist import merge_findings
from src.services.report_builder import build_final_report
from src.services.desk_flow import run_full_review


def _severity_badge(severity: str) -> str:
    return {
        "critical": "🔴 **CRITICAL**",
        "major": "🟠 **MAJOR**",
        "minor": "🔵 **MINOR**",
    }.get(severity.lower(), f"**{severity.upper()}**")


def _format_finding(finding) -> str:
    return (
        f"{_severity_badge(finding.severity)}  \n"
        f"**Location:** `{finding.file}:{finding.line}`  \n"
        f"**Finding:** {finding.message}"
    )


def _format_status(title: str, message: str, *, icon: str) -> str:
    return f"## {icon} {title}\n\n> {message}"


def _format_reviewer_result(result) -> str:
    reviewer_label = result.agent_name.replace("Reviewer", " Reviewer")
    title = f"### {reviewer_label}"
    if result.error:
        return f"{title}\n\n> ⚠️ Reviewer unavailable: {result.error}"
    if result.partial:
        return f"{title}\n\n> ⚠️ Partial result: the turn ceiling was reached."
    if not result.findings:
        return f"{title}\n\n> ✅ **Clear review** · No findings reported."
    return title + f"\n\n> **{len(result.findings)} finding(s)** identified\n\n" + "\n\n".join(
        _format_finding(finding) for finding in result.findings
    )


def _format_final_report(report, remediation_text: str | None = None) -> str:
    counts = {severity: 0 for severity in ("critical", "major", "minor")}
    for finding in report.findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    lines = [
        "# Review report",
        "",
        "## Executive summary",
        "",
        (
            "**Status:** "
            + ("Action recommended" if report.findings else "No action required")
        ),
        "",
        (
            f"**{len(report.findings)} finding(s)** · "
            f"🔴 {counts['critical']} critical · "
            f"🟠 {counts['major']} major · "
            f"🔵 {counts['minor']} minor"
        ),
        "",
        "---",
    ]
    if report.partial:
        lines.extend(
            [
                "",
                "> ⚠️ **Partial review:** one or more reviewers reached the turn ceiling.",
            ]
        )
    if remediation_text:
        lines.extend(
            [
                "",
                "## Remediation handoff",
                "",
                remediation_text,
            ]
        )
    lines.extend(["", "## Findings", ""])
    if report.findings:
        for index, finding in enumerate(report.findings, start=1):
            lines.extend([f"### {index}. {finding.file}:{finding.line}", ""])
            lines.append(_format_finding(finding))
            lines.append("")
    else:
        lines.append("> ✅ No actionable findings were reported.")
    lines.extend(["", "---", "", "## Reviewer metrics", ""])
    lines.append("| Reviewer | Duration | Tokens |")
    lines.append("|---|---:|---:|")
    for row in report.footer:
        lines.append(
            f"| {row.agent_name} | {row.duration_ms} ms | {row.total_tokens} |"
        )
    if report.footer:
        slowest = max(report.footer, key=lambda row: row.duration_ms)
        lines.extend(
            [
                "",
                (
                    f"> ⏱️ **Slowest reviewer:** {slowest.agent_name} "
                    f"({slowest.duration_ms} ms)"
                ),
            ]
        )
    return "\n".join(lines)


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "# Code Review Desk\n\n"
            "### Concurrent AI code review\n"
            "Paste a **unified diff** below to receive Security, Tests, and "
            "Style findings with live progress, remediation guidance, and "
            "reviewer metrics.\n\n"
            "> Tip: include the complete `git diff` output for the most useful review."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        await cl.Message(
            content=_format_status(
                "Configuration required",
                str(exc),
                icon="⚙️",
            ),
            author="Review status",
        ).send()
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
        await cl.Message(
            content=(
                "## Unable to start review\n\n"
                f"> ⚠️ {split.error or 'Could not parse the diff.'}\n\n"
                "Please paste a valid unified diff beginning with `diff --git`."
            ),
            author="Review status",
        ).send()
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
                        author=f"{agent_name.replace('Reviewer', ' Reviewer')} · live",
                        content=(
                            f"### {agent_name.replace('Reviewer', ' Reviewer')}\n\n"
                            "> _Analyzing the diff in real time…_\n\n"
                        ),
                    )
                    await message_for_agent.send()
                    stream_messages[agent_name] = message_for_agent
                await message_for_agent.stream_token(str(delta))

    try:
        results, desk_result = await asyncio.wait_for(
            run_full_review(
                reviewers,
                context=context,
                settings=settings,
                files=list(chunks),
                max_turns=settings.turn_ceiling,
                on_event=on_event,
                chunks=chunks,
            ),
            timeout=120,
        )
    except asyncio.TimeoutError:
        await cl.Message(
            content=_format_status(
                "Review timed out",
                (
                    "The Gemini provider did not respond within the review window. "
                    "Please retry when the provider is available."
                ),
                icon="⏱️",
            ),
            author="Review status",
        ).send()
        return
    except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered):
        await cl.Message(
            content=_format_status(
                "Review refused",
                (
                    "Credential-shaped content was blocked by the Agents SDK "
                    "guardrail. No review result was published."
                ),
                icon="🔒",
            ),
            author="Review status",
        ).send()
        return
    except (openai.OpenAIError, ModelBehaviorError, ModelTimeoutError) as exc:
        await cl.Message(
            content=_format_status(
                "Provider unavailable",
                (
                    "The Gemini provider is currently unavailable. No review "
                    "result was produced; please retry later."
                ),
                icon="☁️",
            ),
            author="Review status",
        ).send()
        cl.user_session.set("last_error", type(exc).__name__)
        return
    await cl.Message(
        content=(
            "## Review complete\n\n"
            "The specialist reviewers have finished. Here is the consolidated "
            "result and execution summary."
        ),
        author="Review status",
    ).send()
    for result in results:
        await cl.Message(
            content=_format_reviewer_result(result),
            author="Reviewer result",
        ).send()

    merged = merge_findings(results)
    remediation_triggered = desk_result.last_agent.name == "RemediationSpecialist"
    report = build_final_report(
        results,
        merged.findings,
        remediation_triggered=remediation_triggered,
    )
    rendered = _format_final_report(report)
    guardrail = inspect_report(rendered)
    if guardrail.tripwire_triggered:
        await cl.Message(
            content=_format_status("Review refused", guardrail.reason or "", icon="🔒"),
            author="Review status",
        ).send()
        return
    if report.partial:
        await cl.Message(
            content=_format_status(
                "Partial review",
                (
                    "One or more reviewers reached the turn ceiling. "
                    "Treat this report as incomplete and rerun if needed."
                ),
                icon="⚠️",
            ),
            author="Review status",
        ).send()
    if remediation_triggered:
        rendered = _format_final_report(report, str(desk_result.final_output))
    await cl.Message(content=rendered, author="Final report").send()
    cl.user_session.set("last_report", report)
